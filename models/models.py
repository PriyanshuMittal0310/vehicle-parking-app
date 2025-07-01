from datetime import datetime
from enum import Enum
from pathlib import Path
from sqlalchemy import (
    Column, DateTime, Enum as PgEnum, ForeignKey, Integer,
    Numeric, String, create_engine, event, func
)
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker, object_session
)

# ────────────────────────────────────────────────────────────────
# DB bootstrap
# ────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).with_suffix(".db")
engine = create_engine(f"sqlite:///{DB_PATH}?check_same_thread=False", echo=False, future=True, pool_pre_ping=True)
Base = declarative_base()

# ────────────────────────────────────────────────────────────────
# Enum
# ────────────────────────────────────────────────────────────────

class SpotStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"

# ────────────────────────────────────────────────────────────────
# ORM entities (same as before)
# ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    pin_code = Column(String(10))
    created_at = Column(DateTime, server_default=func.now())
    
    reservations = relationship(
        "Reservation", back_populates="user", cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User('{self.email}')>"

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    
    def __repr__(self):
        return f"<Admin('{self.email}')>"

class ParkingLot(Base):
    __tablename__ = "parking_lots"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address_line_1 = Column(String, nullable=False)
    address_line_2 = Column(String)
    address_line_3 = Column(String)
    pin_code = Column(String(10), nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    number_of_spots = Column(Integer, nullable=False)
    
    spots = relationship(
        "ParkingSpot", back_populates="parking_lot", cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<ParkingLot('{self.name}')>"

class ParkingSpot(Base):
    __tablename__ = "parking_spots"
    id = Column(Integer, primary_key=True)
    spot_number = Column(String, nullable=False)
    status = Column(PgEnum(SpotStatus), default=SpotStatus.AVAILABLE, nullable=False)
    parking_lot_id = Column(Integer, ForeignKey("parking_lots.id"), nullable=False)
    
    parking_lot = relationship("ParkingLot", back_populates="spots")
    reservations = relationship(
        "Reservation", back_populates="parking_spot", cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<ParkingSpot('{self.spot_number}')>"

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parking_spot_id = Column(Integer, ForeignKey("parking_spots.id"), nullable=False)
    vehicle_number = Column(String, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    occupy_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="reservations")
    parking_spot = relationship("ParkingSpot", back_populates="reservations")
    
    def __repr__(self):
        return f"<Reservation(user_id={self.user_id}, spot_id={self.parking_spot_id})>"

# ────────────────────────────────────────────────────────────────
# ✅ FIXED: Complete event listener for spot management
# ────────────────────────────────────────────────────────────────

def _manage_parking_spots(target, value, oldvalue, *_):
    """Enhanced event listener: handles both increasing and decreasing spot counts"""
    if not isinstance(value, int) or value <= 0:
        return
    
    previous = oldvalue if isinstance(oldvalue, int) else 0
    if value == previous:  # No change needed
        return
    
    sess = object_session(target)
    if sess is None:  # lot not yet attached to session
        return
    
    try:
        # Get current spots count from database
        current_spots_count = (
            sess.query(ParkingSpot)
            .filter_by(parking_lot_id=target.id)
            .count()
        )
        
        print(f"🔧 Managing spots for '{target.name}': Current={current_spots_count}, Target={value}")
        
        if value > current_spots_count:
            # ✅ ADD NEW SPOTS
            spots_to_add = value - current_spots_count
            print(f"   ➕ Adding {spots_to_add} new spots")
            
            for i in range(current_spots_count + 1, value + 1):
                new_spot = ParkingSpot(
                    spot_number=str(i).zfill(3),
                    parking_lot_id=target.id,
                    status=SpotStatus.AVAILABLE
                )
                sess.add(new_spot)
                print(f"      ✅ Added spot {new_spot.spot_number}")
                
        elif value < current_spots_count:
            # ✅ REMOVE EXCESS SPOTS (only if available)
            spots_to_remove = current_spots_count - value
            print(f"   ➖ Attempting to remove {spots_to_remove} excess spots")
            
            # Get spots to potentially remove (highest numbers first)
            excess_spots = (
                sess.query(ParkingSpot)
                .filter_by(parking_lot_id=target.id)
                .order_by(ParkingSpot.spot_number.desc())
                .limit(spots_to_remove)
                .all()
            )
            
            removed_count = 0
            blocked_spots = []
            
            for spot in excess_spots:
                if spot.status == SpotStatus.AVAILABLE:
                    sess.delete(spot)
                    removed_count += 1
                    print(f"      ✅ Removed spot {spot.spot_number}")
                else:
                    blocked_spots.append(f"{spot.spot_number}({spot.status.value})")
                    print(f"      ❌ Cannot remove spot {spot.spot_number} - Status: {spot.status.value}")
            
            # If we couldn't remove all requested spots, adjust target
            if blocked_spots:
                actual_capacity = current_spots_count - removed_count
                print(f"   ⚠️  Could only remove {removed_count}/{spots_to_remove} spots")
                print(f"   ⚠️  Blocked spots: {', '.join(blocked_spots)}")
                print(f"   ⚠️  Adjusting capacity to {actual_capacity}")
                target.number_of_spots = actual_capacity
        
        # Commit the changes
        sess.flush()
        print(f"   ✅ Spot management completed for '{target.name}'")
        
    except Exception as e:
        print(f"❌ Error managing spots for '{target.name}': {str(e)}")
        sess.rollback()
        raise

# ✅ Attach the enhanced event listener
event.listen(ParkingLot.number_of_spots, 'set', _manage_parking_spots)

# ────────────────────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────────────────────

def create_db() -> None:
    Base.metadata.create_all(engine)
    print(f"✅ DB ready at {DB_PATH.resolve()}")

if __name__ == "__main__":
    create_db()
