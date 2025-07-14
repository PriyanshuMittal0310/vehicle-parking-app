"""
Vehicle Parking Management System - Data Models
A comprehensive solution for managing parking operations with real-time tracking
and automated spot allocation.

Author: Priyanshu Mittal
Roll no: 23F2002327
"""

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


# Database Configuration & Setup


DB_PATH = Path(__file__).with_suffix(".db")
engine = create_engine(f"sqlite:///{DB_PATH}?check_same_thread=False", echo=False, future=True, pool_pre_ping=True)
Base = declarative_base()


# Custom Enumerations


class SpotStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"


# Core Data Models


class User(Base):
    """
    Represents a customer account in the parking system.
    Stores personal information and manages parking reservations.
    """
    __tablename__ = "users"
    
    # Primary identification
    id = Column(Integer, primary_key=True)
    
    # Contact and personal information
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    pin_code = Column(String(10))
    
    
    # Relationships
    reservations = relationship(
        "Reservation", back_populates="user", cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User('{self.email}')>"

class Admin(Base):
    """
    Represents a system administrator with full access to all features.
    """
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    
    def __repr__(self):
        return f"<Admin('{self.email}')>"

class ParkingLot(Base):
    """
    Represents a parking facility with multiple parking spots.
    Manages location details and pricing information.
    """
    __tablename__ = "parking_lots"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address_line_1 = Column(String, nullable=False)
    address_line_2 = Column(String)
    address_line_3 = Column(String)
    pin_code = Column(String(10), nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    number_of_spots = Column(Integer, nullable=False)
    
    # Relationships
    spots = relationship(
        "ParkingSpot", back_populates="parking_lot", cascade="all, delete-orphan"
    )
    
    def calculate_occupancy_rate(self):
        """Calculate current occupancy rate as percentage"""
        if not self.spots:
            return 0.0
        
        occupied_spots = sum(1 for spot in self.spots 
                           if spot.status != SpotStatus.AVAILABLE)
        return round((occupied_spots / len(self.spots)) * 100, 2)
    
    def get_available_spots_count(self):
        """Get count of currently available parking spots"""
        return sum(1 for spot in self.spots 
                  if spot.status == SpotStatus.AVAILABLE)
    
    def __repr__(self):
        return f"<ParkingLot('{self.name}')>"

class ParkingSpot(Base):
    """
    Represents an individual parking space within a facility.
    Tracks current state and manages reservations.
    """
    __tablename__ = "parking_spots"
    
    id = Column(Integer, primary_key=True)
    spot_number = Column(String, nullable=False)
    status = Column(PgEnum(SpotStatus), default=SpotStatus.AVAILABLE, nullable=False)
    parking_lot_id = Column(Integer, ForeignKey("parking_lots.id"), nullable=False)
    
    # Relationships
    parking_lot = relationship("ParkingLot", back_populates="spots")
    reservations = relationship(
        "Reservation", back_populates="parking_spot", cascade="all, delete-orphan"
    )
    
    def is_available_for_booking(self):
        """Check if space is available for new reservations"""
        return self.status == SpotStatus.AVAILABLE
    
    def get_current_reservation(self):
        """Get active parking reservation if any"""
        for reservation in self.reservations:
            if reservation.end_time is None:
                return reservation
        return None
    
    def __repr__(self):
        return f"<ParkingSpot('{self.spot_number}')>"

class Reservation(Base):
    """
    Represents a parking session from reservation to completion.
    Tracks timing, vehicle information, and billing details.
    """
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parking_spot_id = Column(Integer, ForeignKey("parking_spots.id"), nullable=False)
    
    # Vehicle information
    vehicle_number = Column(String, nullable=False)
    
    # Timing information
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    occupy_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="reservations")
    parking_spot = relationship("ParkingSpot", back_populates="reservations")
    
    def calculate_session_duration(self):
        """Calculate total session duration in minutes"""
        end_time = self.end_time or datetime.now()
        duration = end_time - self.start_time
        return int(duration.total_seconds() / 60)
    
    def get_session_status(self):
        """Get current status of the parking session"""
        if self.end_time:
            return "completed"
        elif self.occupy_time:
            return "active"
        else:
            return "reserved"
    
    def __repr__(self):
        return f"<Reservation(user_id={self.user_id}, spot_id={self.parking_spot_id})>"


# Automated Space Management System


def _manage_parking_spots(target, value, oldvalue, *_):
    """
    Intelligent space management system that automatically adjusts
    parking spots based on facility capacity changes.
    
    This function handles:
    - Adding new spots when capacity increases
    - Removing unused spots when capacity decreases
    - Validation of spot removal operations
    """
    if not isinstance(value, int) or value <= 0:
        return
    
    previous = oldvalue if isinstance(oldvalue, int) else 0
    if value == previous:  # No changes required
        return
    
    sess = object_session(target)
    if sess is None:  # Facility not yet in session
        return
    
    try:
        # Get current spot count from database
        existing_spots_count = (
            sess.query(ParkingSpot)
            .filter_by(parking_lot_id=target.id)
            .count()
        )
        
        if value > existing_spots_count:
            # Add new parking spots
            spots_to_add = value - existing_spots_count
            
            for spot_number in range(existing_spots_count + 1, value + 1):
                new_spot = ParkingSpot(
                    spot_number=str(spot_number).zfill(3),
                    parking_lot_id=target.id,
                    status=SpotStatus.AVAILABLE
                )
                sess.add(new_spot)
                
        elif value < existing_spots_count:
            # Remove excess spots (only if available)
            spots_to_remove = existing_spots_count - value
            
            # Get spots to potentially remove (highest numbers first)
            excess_spots = (
                sess.query(ParkingSpot)
                .filter_by(parking_lot_id=target.id)
                .order_by(ParkingSpot.spot_number.desc())
                .limit(spots_to_remove)
                .all()
            )
            
            successfully_removed = 0
            blocked_spots = []
            
            for spot in excess_spots:
                if spot.status == SpotStatus.AVAILABLE:
                    sess.delete(spot)
                    successfully_removed += 1
                
                else:
                    blocked_spots.append(f"{spot.spot_number}({spot.status.value})")
                
            # Adjust capacity if we couldn't remove all requested spots
            if blocked_spots:
                actual_capacity = existing_spots_count - successfully_removed
                target.number_of_spots = actual_capacity
        
        # Apply changes to database
        sess.flush()
        
    except Exception as error:
        sess.rollback()
        raise

# Register the automated space management system
event.listen(ParkingLot.number_of_spots, 'set', _manage_parking_spots)


# Database Initialization Helper


def create_db() -> None:
    """
    Initialize the database by creating all tables and setting up
    the initial database structure.
    """
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    create_db()
