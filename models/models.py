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

# Fixed: Added check_same_thread=False to prevent threading issues
engine = create_engine(f"sqlite:///{DB_PATH}?check_same_thread=False", echo=False, future=True, pool_pre_ping=True )

Base = declarative_base()

# ────────────────────────────────────────────────────────────────
# Enum
# ────────────────────────────────────────────────────────────────

class SpotStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"

# ────────────────────────────────────────────────────────────────
# ORM entities
# ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # plaintext (demo)
    full_name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    pin_code = Column(String(10))
    created_at = Column(DateTime, server_default=func.now())
    
    reservations = relationship(
        "Reservation", back_populates="user", cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User {self.email}>"

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    
    def __repr__(self):
        return f"<Admin {self.email}>"

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
        return f"<ParkingLot {self.name}>"

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
        return f"<ParkingSpot {self.spot_number}>"

class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parking_spot_id = Column(Integer, ForeignKey("parking_spots.id"), nullable=False)
    vehicle_number = Column(String, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    occupy_time = Column(DateTime, nullable=True)  # Added: When user actually parks
    end_time = Column(DateTime, nullable=True)  # NULL → active
    
    user = relationship("User", back_populates="reservations")
    parking_spot = relationship("ParkingSpot", back_populates="reservations")
    
    def __repr__(self):
        return f"<Reservation {self.id}>"

# ────────────────────────────────────────────────────────────────
# Listener: auto-create ParkingSpot rows (Fixed)
# ────────────────────────────────────────────────────────────────

def _create_spots(target, value, oldvalue, *_):
    if not isinstance(value, int) or value <= 0:
        return
    
    previous = oldvalue if isinstance(oldvalue, int) else 0
    if value <= previous:  # capacity didn't grow
        return
    
    sess = object_session(target)
    if sess is None:  # lot not yet attached
        return
    
    # Create additional spots
    for i in range(previous + 1, value + 1):
        sess.add(
            ParkingSpot(
                spot_number=str(i).zfill(3),
                parking_lot=target,
                status=SpotStatus.AVAILABLE,
            )
        )

# Fixed: Properly attach the event listener
event.listen(ParkingLot.number_of_spots, 'set', _create_spots)

# ────────────────────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────────────────────

def create_db() -> None:
    Base.metadata.create_all(engine)
    print(f"✅ DB ready at {DB_PATH.resolve()}")

if __name__ == "__main__":
    create_db()
