from datetime import datetime
from enum import Enum
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Enum as PgEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DB_PATH = Path(__file__).with_suffix(".db")
engine  = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Base    = declarative_base()

# 2. Enum helpers

class SpotStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED  = "reserved"
    OCCUPIED  = "occupied"

# 3. ORM classes

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True)
    email      = Column(String, unique=True, nullable=False)
    password   = Column(String, nullable=False)         
    full_name  = Column(String, nullable=False)
    address    = Column(String)
    phone      = Column(String)
    pin_code   = Column(String(10))
    created_at = Column(DateTime, server_default=func.now())

    reservations = relationship("Reservation", back_populates="user",
                                cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email!r}>"


class Admin(Base):
    __tablename__ = "admins"

    id        = Column(Integer, primary_key=True)
    email     = Column(String, unique=True, nullable=False)
    password  = Column(String, nullable=False)           
    full_name = Column(String, nullable=False)

    def __repr__(self):
        return f"<Admin {self.email!r}>"


class ParkingLot(Base):
    __tablename__ = "parking_lots"

    id              = Column(Integer, primary_key=True)
    name            = Column(String, nullable=False)
    address_line_1  = Column(String, nullable=False)
    address_line_2  = Column(String)
    address_line_3  = Column(String)
    pin_code        = Column(String(10), nullable=False)
    price_per_hour  = Column(Numeric(10, 2), nullable=False)
    number_of_spots = Column(Integer, nullable=False)

    spots = relationship("ParkingSpot", back_populates="parking_lot",
                         cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ParkingLot {self.name!r} – {self.pin_code}>"


class ParkingSpot(Base):
    __tablename__ = "parking_spots"

    id             = Column(Integer, primary_key=True)
    spot_number    = Column(String, nullable=False)
    status         = Column(PgEnum(SpotStatus),
                            default=SpotStatus.AVAILABLE,
                            nullable=False)
    parking_lot_id = Column(Integer, ForeignKey("parking_lots.id"),
                            nullable=False)

    parking_lot  = relationship("ParkingLot", back_populates="spots")
    reservations = relationship("Reservation", back_populates="parking_spot",
                                cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ParkingSpot {self.spot_number} ({self.status})>"


class Reservation(Base):
    __tablename__ = "reservations"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    parking_spot_id = Column(Integer, ForeignKey("parking_spots.id"),
                             nullable=False)

    vehicle_number = Column(String, nullable=False)
    start_time     = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time       = Column(DateTime)  # NULL → still active

    user         = relationship("User", back_populates="reservations")
    parking_spot = relationship("ParkingSpot", back_populates="reservations")

    def __repr__(self):
        return (f"<Reservation {self.id} User={self.user_id} "
                f"Spot={self.parking_spot_id} Vehicle={self.vehicle_number}>")

# 4. Schema creation helper

def create_db() -> None:
    Base.metadata.create_all(engine)
    print(f"Database ready at {DB_PATH.resolve()}")

# 5. Quick smoke test & default admin seeding

if __name__ == "__main__":
    create_db()

    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        if not session.query(Admin).first():
            session.add(
                Admin(
                    email="admin@vps.local",
                    password="admin123",     
                    full_name="Super Admin",
                )
            )
            session.commit()
            print("Inserted default administrator.")

        print("Schema OK – you can now start developing the REST / UI layer.")
