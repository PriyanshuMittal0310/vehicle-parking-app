"""
Vehicle Parking Management System - Main Application
A comprehensive web-based solution for managing parking operations with real-time tracking,
automated billing, and intelligent space allocation.

This application provides:
- Customer self-service parking reservations
- Real-time parking space management
- Automated billing and cost calculation
- Administrative dashboard with comprehensive analytics
- Multi-role access control system

Author: Priyanshu Mittal
Roll no: 23F2002327
"""

from pathlib import Path
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import or_, and_, func

from models.models import (
    engine, create_db,
    User, Admin, ParkingLot, ParkingSpot, Reservation, SpotStatus
)

# Application Configuration & Initialization

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = "dev-key-change-me"
SessionLocal = sessionmaker(bind=engine, future=True)

# Ensure database exists on first run
if not Path("models/models.db").exists():
    create_db()

# System Administrator Setup

def ensure_default_admin():
    """
    Initialize the system with a default administrator account.
    This ensures the system is accessible immediately after deployment.
    """
    with SessionLocal() as db:
        # Check if any administrator exists
        existing_admin = db.query(Admin).first()
        if existing_admin:
            return
        
        # Create default administrator account
        default_admin = Admin(
            email="admin@vps.local",
            password="admin123",
            full_name="Super Admin"
        )
        db.add(default_admin)
        db.commit()

# Initialize default administrator
ensure_default_admin()

# Business Logic & Utility Functions

def calculate_cost(reservation):
    """
    Calculate the total parking fee based on duration and hourly rate.
    Implements minimum billing of 1 hour and rounds to 2 decimal places.
    
    Args:
        reservation: The parking reservation object
        
    Returns:
        total_fee: Calculated parking fee
    """
    if not reservation.end_time:
        # For active sessions, calculate current fee
        current_time = datetime.now()
    else:
        current_time = reservation.end_time
    
    # Calculate duration in hours
    session_duration = current_time - reservation.start_time
    total_hours = max(1, session_duration.total_seconds() / 3600)
    
    # Get hourly rate and calculate total fee
    hourly_rate = float(reservation.parking_spot.parking_lot.price_per_hour)
    total_fee = round(total_hours * hourly_rate, 2)
    
    return total_fee

def format_duration(start_time, end_time=None):
    """
    Format the duration between two timestamps in a human-readable format.
    
    Args:
        start_time: Start time
        end_time: End time (uses current time if None)
        
    Returns:
        str: Formatted duration string in "Xh Ym" format
    """
    if not end_time:
        end_time = datetime.now()
    
    duration = end_time - start_time
    total_minutes = int(duration.total_seconds() / 60)
    
    if total_minutes > 0:
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}h {minutes}m"
    else:
        return "0h 0m"

def get_reservation_details(reservation):
    """
    Get detailed information about a parking reservation including
    duration, cost, and current status.
    
    Args:
        reservation: The parking reservation object
        
    Returns:
        details: Comprehensive reservation details
    """
    details = {
        'reservation': reservation,
        'duration_formatted': 'N/A',
        'duration_minutes': 0,
        'cost': 0.00,
        'status': 'Reserved'
    }
    
    if reservation.end_time:
        # Completed parking session
        details['status'] = 'Completed'
        details['duration_formatted'] = format_duration(reservation.start_time, reservation.end_time)
        duration_delta = reservation.end_time - reservation.start_time
        details['duration_minutes'] = int(duration_delta.total_seconds() / 60)
        details['cost'] = calculate_cost(reservation)
    elif reservation.occupy_time:
        # Currently occupied parking space
        details['status'] = 'Occupied'
        details['duration_formatted'] = format_duration(reservation.start_time)
        duration_delta = datetime.now() - reservation.start_time
        details['duration_minutes'] = int(duration_delta.total_seconds() / 60)
        details['cost'] = calculate_cost(reservation)
    else:
        # Reserved but not yet occupied
        details['status'] = 'Reserved'
        details['duration_formatted'] = format_duration(reservation.start_time)
        duration_delta = datetime.now() - reservation.start_time
        details['duration_minutes'] = int(duration_delta.total_seconds() / 60)
        details['cost'] = calculate_cost(reservation)
    
    return details

# Make utility functions available in templates
app.jinja_env.globals.update(
    format_duration=format_duration,
    calculate_cost=calculate_cost,
    get_reservation_details=get_reservation_details
)

# Access Control Decorators


def login_required(view_function):
    """
    Decorator to ensure user is authenticated before accessing protected routes.
    Redirects to login page if user is not authenticated.
    """
    @wraps(view_function)
    def authentication_wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Authentication required. Please log in to continue.")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return authentication_wrapper

def role_required(required_role):
    """
    Decorator to ensure user has the required role for accessing specific routes.
    
    Args:
        required_role: The role required to access the route
    """
    def role_decorator(view_function):
        @wraps(view_function)
        def role_wrapper(*args, **kwargs):
            if session.get("role") != required_role:
                flash("Access denied. Insufficient privileges.")
                return redirect(url_for("login"))
            return view_function(*args, **kwargs)
        return role_wrapper
    return role_decorator

# Authentication Routes


@app.route("/")
def root():
    """Redirect root URL to login page"""
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Handle customer account registration with comprehensive validation.
    Creates new customer accounts and automatically logs them in.
    """
    if request.method == "POST":
        form_data = request.form
        
        with SessionLocal() as db:
            # Check for existing email address
            existing_customer = db.query(User).filter_by(email=form_data["email"]).first()
            if existing_customer:
                flash("Email address is already registered. Please use a different email.")
                return redirect(url_for("register"))
            
            # Create new customer account
            new_customer = User(
                email=form_data["email"],
                password=form_data["password"],
                full_name=form_data["full_name"],
                address=form_data.get("address"),
                phone=form_data.get("phone"),
                pin_code=form_data.get("pin_code"),
            )
            db.add(new_customer)
            db.commit()
            
            # Automatically log in the new customer
            session["user_id"] = new_customer.id
            session["role"] = "user"
            flash(f"Welcome {new_customer.full_name}! Your account has been created successfully.")
            return redirect(url_for("user_dashboard"))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handle user authentication for both customers and administrators.
    Supports role-based login and session management.
    """
    if request.method == "POST":
        email_address = request.form["email"]
        password_attempt = request.form["password"]
        
        with SessionLocal() as db:
            # Check for administrator login
            administrator = db.query(Admin).filter_by(
                email=email_address, password=password_attempt
            ).first()
            
            if administrator:
                session["user_id"] = administrator.id
                session["role"] = "admin"
                flash(f"Welcome back, {administrator.full_name}!")
                return redirect(url_for("admin_dashboard"))
            
            # Check for customer login
            customer = db.query(User).filter_by(
                email=email_address, password=password_attempt
            ).first()
            
            if customer:
                session["user_id"] = customer.id
                session["role"] = "user"
                flash(f"Welcome back, {customer.full_name}!")
                return redirect(url_for("user_dashboard"))
        
        flash("Invalid email or password. Please try again.")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Handle user logout and session cleanup"""
    session.clear()
    flash("You have been successfully logged out.")
    return redirect(url_for("login"))


# Dashboard Routes


@app.route("/dashboard")
@login_required
@role_required("user")
def user_dashboard():
    """
    Customer dashboard showing current parking session and relevant information.
    Displays active reservations and current costs.
    """
    with SessionLocal() as db:
        # Get current active parking session
        active_reservation = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"], end_time=None)
            .options(selectinload(Reservation.parking_spot)
                    .selectinload(ParkingSpot.parking_lot))
            .first()
        )
        
        # Calculate current session cost
        current_cost = 0
        if active_reservation:
            current_cost = calculate_cost(active_reservation)
        
        return render_template("user_dashboard.html",
                             current_reservation=active_reservation,
                             current_cost=current_cost)

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    """
    Administrator dashboard with comprehensive system statistics.
    Provides overview of users, facilities, and parking operations.
    """
    with SessionLocal() as db:
        # Gather comprehensive system statistics
        total_users = db.query(User).count()
        total_lots = db.query(ParkingLot).count()
        active_reservations = db.query(Reservation).filter(
            Reservation.end_time.is_(None)
        ).count()
        total_spots = db.query(ParkingSpot).count()
        available_spots = db.query(ParkingSpot).filter_by(
            status=SpotStatus.AVAILABLE
        ).count()
        
        dashboard_stats = {
            'total_users': total_users,
            'total_lots': total_lots,
            'active_reservations': active_reservations,
            'total_spots': total_spots,
            'available_spots': available_spots
        }
        
        return render_template("admin_dashboard.html", stats=dashboard_stats)

# User parking functionalities

@app.route("/user/lots")
@login_required
@role_required("user")
def user_view_lots():
    """
    Display available parking facilities with real-time availability information.
    Shows capacity and current availability for each facility.
    """
    with SessionLocal() as db:
        all_lots = db.query(ParkingLot).all()
        
        # Calculate availability for each lot
        lots_with_availability = []
        for lot in all_lots:
            available_spots_count = (
                db.query(ParkingSpot)
                .filter_by(parking_lot_id=lot.id, status=SpotStatus.AVAILABLE)
                .count()
            )
            
            lots_with_availability.append({
                'lot': lot,
                'available_spots': available_spots_count
            })
        
        return render_template("user/lots.html", lots_data=lots_with_availability)

@app.route("/user/reserve/<int:lot_id>", methods=["POST"])
@login_required
@role_required("user")
def reserve_spot(lot_id):
    """
    Reserve a parking space in the specified facility.
    Validates availability and prevents multiple active reservations.
    """
    with SessionLocal() as db:
        # Check for existing active reservation
        existing_active_reservation = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"], end_time=None)
            .first()
        )
        
        if existing_active_reservation:
            flash("You already have an active parking session. Please complete it before making a new reservation.")
            return redirect(url_for("user_view_lots"))
        
        # Find available parking space
        available_spot = (
            db.query(ParkingSpot)
            .filter_by(parking_lot_id=lot_id, status=SpotStatus.AVAILABLE)
            .first()
        )
        
        if not available_spot:
            flash("No available parking spaces in this facility at the moment.")
            return redirect(url_for("user_view_lots"))
        
        # Create new parking session
        new_reservation = Reservation(
            user_id=session["user_id"],
            parking_spot_id=available_spot.id,
            vehicle_number="",  # Default to empty string
            start_time=datetime.now(),
            occupy_time=None,
            end_time=None
        )
        
        # Update space status to reserved
        available_spot.status = SpotStatus.RESERVED
        db.add(new_reservation)
        db.commit()
        
        flash(f"Parking space {available_spot.spot_number} has been reserved successfully!")
        return redirect(url_for("user_dashboard"))

@app.route("/user/occupy/<int:reservation_id>", methods=["POST"])
@login_required
@role_required("user")
def occupy_spot(reservation_id):
    """
    Mark a reserved parking space as occupied.
    Updates session status, vehicle number, and space availability.
    """
    with SessionLocal() as db:
        reservation = (
            db.query(Reservation)
            .filter_by(id=reservation_id, user_id=session["user_id"])
            .first()
        )
        
        if not reservation:
            flash("Parking session not found.")
            return redirect(url_for("user_dashboard"))
        
        if reservation.end_time is not None:
            flash("This parking session has already been completed.")
            return redirect(url_for("user_dashboard"))
        
        # Get vehicle number from form
        vehicle_number = request.form.get("vehicle_number", "").strip()
        if not vehicle_number:
            flash("Vehicle number is required to occupy the spot.")
            return redirect(url_for("user_dashboard"))
        
        # Update reservation with vehicle number
        reservation.vehicle_number = vehicle_number
        
        # Update space status to occupied
        parking_spot = db.get(ParkingSpot, reservation.parking_spot_id)
        parking_spot.status = SpotStatus.OCCUPIED
        reservation.occupy_time = datetime.now()
        db.commit()
        
        flash("Parking space is now occupied. Your session has started!")
        return redirect(url_for("user_dashboard"))

@app.route("/user/release/<int:reservation_id>", methods=["POST"])
@login_required
@role_required("user")
def release_spot(reservation_id):
    """
    Complete a parking session and calculate final charges.
    Updates space availability and session end time.
    """
    with SessionLocal() as db:
        reservation = (
            db.query(Reservation)
            .filter_by(id=reservation_id, user_id=session["user_id"])
            .first()
        )
        
        if not reservation:
            flash("Parking session not found.")
            return redirect(url_for("user_dashboard"))
        
        if reservation.end_time is not None:
            flash("This parking session has already been completed.")
            return redirect(url_for("user_dashboard"))
        
        # Update space status to available
        parking_spot = db.get(ParkingSpot, reservation.parking_spot_id)
        parking_spot.status = SpotStatus.AVAILABLE
        reservation.end_time = datetime.now()
        
        # Calculate final charges
        final_cost = calculate_cost(reservation)
        db.commit()
        
        flash(f"Parking session completed successfully! Total charge: ₹{final_cost}")
        return redirect(url_for("user_dashboard"))

@app.route("/user/history")
@login_required
@role_required("user")
def parking_history():
    """
    Display comprehensive parking history for the customer.
    Shows all past and current parking sessions with detailed information.
    """
    with SessionLocal() as db:
        all_reservations = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"])
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .order_by(Reservation.start_time.desc())
            .all()
        )
        
        # Process reservation details
        history_data = []
        total_spent = 0
        
        for reservation in all_reservations:
            reservation_details = get_reservation_details(reservation)
            history_data.append(reservation_details)
            total_spent += reservation_details['cost']
        
        # Calculate summary statistics
        summary_statistics = {
            'total_reservations': len(all_reservations),
            'completed_reservations': len([r for r in all_reservations if r.end_time]),
            'total_spent': round(total_spent, 2),
            'average_cost': round(
                total_spent / max(1, len([r for r in all_reservations if r.end_time])), 2
            )
        }
        
        return render_template("user/history.html",
                             history_data=history_data,
                             summary=summary_statistics)

@app.route("/user/summary")
@login_required
@role_required("user")
def user_summary():
    """
    Display customer summary with comprehensive parking statistics.
    Shows usage patterns, costs, and session information.
    """
    with SessionLocal() as db:
        user_id = session["user_id"]
        all_reservations = (
            db.query(Reservation)
            .filter_by(user_id=user_id)
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .all()
        )
        
        # Analyze reservation data
        completed_reservations = [r for r in all_reservations if r.end_time]
        active_reservations = [r for r in all_reservations if not r.end_time]
        
        total_spent = 0
        total_minutes = 0
        current_session_cost = 0
        
        # Calculate statistics for completed reservations
        for reservation in completed_reservations:
            reservation_cost = calculate_cost(reservation)
            total_spent += reservation_cost
            duration = reservation.end_time - reservation.start_time
            total_minutes += int(duration.total_seconds() / 60)
        
        # Calculate current session costs
        for reservation in active_reservations:
            current_session_cost += calculate_cost(reservation)
        
        # Prepare summary data
        summary_data = {
            'total_reservations': len(all_reservations),
            'completed_reservations': len(completed_reservations),
            'active_reservations': len(active_reservations),
            'total_spent': round(total_spent, 2),
            'current_session_cost': round(current_session_cost, 2),
            'total_duration': f"{total_minutes // 60}h {total_minutes % 60}m",
            'average_cost_per_session': round(
                total_spent / max(1, len(completed_reservations)), 2
            )
        }
        
        return render_template("user/summary.html",
                             summary=summary_data,
                             current_date=datetime.now())


# Administrative Facility Management


@app.route("/admin/lots")
@login_required
@role_required("admin")
def list_lots():
    """Display all parking facilities for administrative management"""
    with SessionLocal() as db:
        all_lots = db.query(ParkingLot).all()
        return render_template("admin/lots.html", lots=all_lots)

@app.route("/admin/lots/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_lot():
    """
    Add new parking facility with comprehensive validation.
    Handles facility creation and automatic space allocation.
    """
    if request.method == "POST":
        form_data = request.form
        
        with SessionLocal() as db:
            try:
                new_lot = ParkingLot(
                    name=form_data["name"],
                    address_line_1=form_data["addr1"],
                    address_line_2=form_data.get("addr2"),
                    address_line_3=form_data.get("addr3"),
                    pin_code=form_data["pin"],
                    price_per_hour=form_data["price"],
                    number_of_spots=int(form_data["capacity"]),
                )
                db.add(new_lot)
                db.flush()  # This ensures the lot gets an ID
                
                # Manually create parking spots if automatic creation doesn't work
                capacity = int(form_data["capacity"])
                for i in range(1, capacity + 1):
                    new_spot = ParkingSpot(
                        spot_number=str(i).zfill(3),
                        parking_lot_id=new_lot.id,
                        status=SpotStatus.AVAILABLE
                    )
                    db.add(new_spot)
                
                db.commit()
                
                flash(f"Parking facility '{new_lot.name}' created successfully with {new_lot.number_of_spots} spaces.")
                return redirect(url_for("list_lots"))
                
            except Exception as error:
                db.rollback()
                flash(f"Error creating parking facility: {str(error)}")
                return redirect(url_for("add_lot"))
    
    return render_template("admin/lot_form.html", action="Add")

@app.route("/admin/lots/<int:lot_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_lot(lot_id):
    """
    Edit existing parking facility with capacity validation.
    Handles space management and facility updates.
    """
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Parking facility not found.")
            return redirect(url_for("list_lots"))
        
        if request.method == "POST":
            form_data = request.form
            
            try:
                original_capacity = lot.number_of_spots
                new_capacity = int(form_data["capacity"])
                
                # Validate capacity reduction
                if new_capacity < original_capacity:
                    spots_to_check = (
                        db.query(ParkingSpot)
                        .filter_by(parking_lot_id=lot.id)
                        .order_by(ParkingSpot.spot_number.desc())
                        .limit(original_capacity - new_capacity)
                        .all()
                    )
                    
                    unavailable_spots = [
                        f"{spot.spot_number}({spot.status.value})" 
                        for spot in spots_to_check 
                        if spot.status != SpotStatus.AVAILABLE
                    ]
                    
                    if unavailable_spots:
                        flash(f"Cannot reduce capacity to {new_capacity}. These spaces are in use: {', '.join(unavailable_spots)}")
                        return render_template("admin/lot_form.html", lot=lot, action="Edit")
                
                # Update facility properties
                lot.name = form_data["name"]
                lot.address_line_1 = form_data["addr1"]
                lot.address_line_2 = form_data.get("addr2")
                lot.address_line_3 = form_data.get("addr3")
                lot.pin_code = form_data["pin"]
                lot.price_per_hour = form_data["price"]
                lot.number_of_spots = new_capacity
                
                db.commit()
                
                if new_capacity > original_capacity:
                    flash(f"Facility updated. Added {new_capacity - original_capacity} new spaces.")
                elif new_capacity < original_capacity:
                    flash(f"Facility updated. Reduced capacity by {original_capacity - new_capacity} spaces.")
                else:
                    flash("Facility updated successfully.")
                    
                return redirect(url_for("list_lots"))
                
            except Exception as error:
                db.rollback()
                flash(f"Error updating facility: {str(error)}")
                return render_template("admin/lot_form.html", lot=lot, action="Edit")
        
        return render_template("admin/lot_form.html", lot=lot, action="Edit")

@app.route("/admin/lots/<int:lot_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_lot(lot_id):
    """
    Delete parking facility with validation.
    Ensures no active sessions before deletion.
    """
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Parking facility not found.")
            return redirect(url_for("list_lots"))
        
        # Check for active sessions
        if any(spot.status != SpotStatus.AVAILABLE for spot in lot.spots):
            flash("Cannot delete facility - one or more spaces are currently in use.")
            return redirect(url_for("list_lots"))
        
        db.delete(lot)
        db.commit()
        flash("Parking facility deleted successfully.")
        return redirect(url_for("list_lots"))


# Space Management & Monitoring


@app.route("/admin/lots/<int:lot_id>/spots")
@login_required
@role_required("admin")
def lot_spots(lot_id):
    """
    Display detailed overview of all spaces in a facility.
    Shows current status and session information for each space.
    """
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Parking facility not found.")
            return redirect(url_for("list_lots"))
        
        all_spots = (
            db.query(ParkingSpot)
            .filter_by(parking_lot_id=lot.id)
            .order_by(ParkingSpot.spot_number)
            .options(selectinload(ParkingSpot.reservations))
            .all()
        )
        
        return render_template("admin/spots.html",
                             lot=lot,
                             spots=all_spots,
                             SpotStatus=SpotStatus)

@app.route("/admin/lots/<int:lot_id>/sync-spots", methods=["POST"])
@login_required
@role_required("admin")
def sync_lot_spots(lot_id):
    """
    Synchronize parking spots for a lot to match the expected capacity.
    Creates missing spots or removes excess spots as needed.
    """
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Parking facility not found.")
            return redirect(url_for("list_lots"))
        
        try:
            # Get current spot count
            current_spots_count = (
                db.query(ParkingSpot)
                .filter_by(parking_lot_id=lot.id)
                .count()
            )
            
            expected_spots = lot.number_of_spots
            
            if current_spots_count < expected_spots:
                # Add missing spots
                spots_to_add = expected_spots - current_spots_count
                for i in range(current_spots_count + 1, expected_spots + 1):
                    new_spot = ParkingSpot(
                        spot_number=str(i).zfill(3),
                        parking_lot_id=lot.id,
                        status=SpotStatus.AVAILABLE
                    )
                    db.add(new_spot)
                
                flash(f"Added {spots_to_add} missing parking spots.")
                
            elif current_spots_count > expected_spots:
                # Remove excess spots (only if available)
                spots_to_remove = current_spots_count - expected_spots
                excess_spots = (
                    db.query(ParkingSpot)
                    .filter_by(parking_lot_id=lot.id)
                    .order_by(ParkingSpot.spot_number.desc())
                    .limit(spots_to_remove)
                    .all()
                )
                
                removed_count = 0
                for spot in excess_spots:
                    if spot.status == SpotStatus.AVAILABLE:
                        db.delete(spot)
                        removed_count += 1
                
                if removed_count > 0:
                    flash(f"Removed {removed_count} excess parking spots.")
                else:
                    flash("Could not remove excess spots - they are in use.")
            else:
                flash("Parking spots are already synchronized.")
            
            db.commit()
            
        except Exception as error:
            db.rollback()
            flash(f"Error synchronizing spots: {str(error)}")
        
        return redirect(url_for("lot_spots", lot_id=lot.id))


# Customer Management


@app.route("/admin/users")
@login_required
@role_required("admin")
def list_users():
    """
    Display all customer accounts with current parking status.
    Shows active sessions and customer information.
    """
    with SessionLocal() as db:
        users_with_reservations = (
            db.query(User)
            .outerjoin(
                Reservation,
                and_(
                    Reservation.user_id == User.id,
                    Reservation.end_time.is_(None)
                )
            )
            .add_entity(Reservation)
            .all()
        )
        
        return render_template("admin/users.html", users=users_with_reservations)


# Parking Records & Analytics


@app.route("/admin/parking-records")
@login_required
@role_required("admin")
def admin_parking_records():
    """
    Comprehensive parking records management with filtering capabilities.
    Displays all parking sessions with detailed information and analytics.
    """
    with SessionLocal() as db:
        # Base query for all parking sessions
        base_query = (
            db.query(Reservation)
            .options(
                selectinload(Reservation.user),
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .order_by(Reservation.start_time.desc())
        )
        
        # Apply filters
        status_filter = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        if status_filter:
            if status_filter == 'active':
                base_query = base_query.filter(Reservation.end_time.is_(None))
            elif status_filter == 'completed':
                base_query = base_query.filter(Reservation.end_time.isnot(None))
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                base_query = base_query.filter(Reservation.start_time >= date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                base_query = base_query.filter(Reservation.start_time <= date_to_obj)
            except ValueError:
                pass
        
        # Get all records
        all_records = base_query.all()
        total_records_count = len(all_records)
        
        # Process record details
        records_data = []
        for record in all_records:
            duration_minutes = 0
            session_cost = 0
            session_status = "Reserved"
            
            if record.end_time:
                # Completed reservation
                duration_delta = record.end_time - record.start_time
                duration_minutes = int(duration_delta.total_seconds() / 60)
                session_cost = calculate_cost(record)
                session_status = "Completed"
            elif record.occupy_time:
                # Currently occupied reservation
                session_status = "Occupied"
                duration_delta = datetime.now() - record.start_time
                duration_minutes = int(duration_delta.total_seconds() / 60)
                session_cost = calculate_cost(record)
            else:
                # Reserved but not yet occupied
                session_status = "Reserved"
                duration_delta = datetime.now() - record.start_time
                duration_minutes = int(duration_delta.total_seconds() / 60)
                session_cost = calculate_cost(record)
            
            # Improved duration formatting
            if duration_minutes > 0:
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                formatted_duration = f"{hours}h {minutes}m"
            else:
                formatted_duration = "0h 0m"
            
            record_data = {
                'reservation': record,
                'duration_minutes': duration_minutes,
                'formatted_duration': formatted_duration,
                'cost': session_cost,
                'status': session_status
            }
            
            records_data.append(record_data)
        
        return render_template("admin/parking_records.html",
                             records=records_data,
                             total_records=total_records_count,
                             filters={
                                 'status': status_filter,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })

@app.route("/admin/summary")
@login_required
@role_required("admin")
def admin_summary():
    """
    Comprehensive system analytics and reporting.
    Provides detailed statistics and revenue analysis.
    """
    with SessionLocal() as db:
        # Basic system statistics
        total_users = db.query(User).count()
        total_reservations = db.query(Reservation).count()
        completed_reservations_count = db.query(Reservation).filter(
            Reservation.end_time.isnot(None)
        ).count()
        active_reservations_count = db.query(Reservation).filter(
            Reservation.end_time.is_(None)
        ).count()
        
        # Revenue calculation
        completed_reservations = (
            db.query(Reservation)
            .filter(Reservation.end_time.isnot(None))
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .all()
        )
        
        total_revenue = sum(calculate_cost(reservation) for reservation in completed_reservations)
        
        # Potential revenue from active sessions
        active_reservations = (
            db.query(Reservation)
            .filter(Reservation.end_time.is_(None))
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .all()
        )
        
        potential_revenue = sum(calculate_cost(reservation) for reservation in active_reservations)
        
        summary_data = {
            'total_users': total_users,
            'total_reservations': total_reservations,
            'completed_reservations': completed_reservations_count,
            'active_reservations': active_reservations_count,
            'total_revenue': round(total_revenue, 2),
            'potential_revenue': round(potential_revenue, 2),
            'average_revenue_per_session': round(
                total_revenue / max(1, completed_reservations_count), 2
            )
        }
        
        return render_template("admin/summary.html", summary=summary_data)

@app.route("/admin/search", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_search():
    """
    Unified search interface for administrative operations.
    Searches across customers, facilities, spaces, and sessions.
    """
    search_results = {
        'users': [],
        'parking_spots': [],
        'reservations': [],
        'parking_lots': []
    }
    
    search_query = ""
    search_type = "all"
    
    if request.method == "POST":
        search_query = request.form.get("search_query", "").strip()
        search_type = request.form.get("search_type", "all")
        
        if search_query:
            with SessionLocal() as db:
                search_results = perform_search(db, search_query, search_type)
    
    return render_template("admin/search.html",
                         results=search_results,
                         search_query=search_query,
                         search_type=search_type)

def perform_search(db, query, search_type):
    """
    Perform comprehensive search across all system entities.
    
    Args:
        db: Database session
        query: Search query string
        search_type: Category to search in
        
    Returns:
        dict: Search results organized by category
    """
    results = {
        'users': [],
        'parking_spots': [],
        'reservations': [],
        'parking_lots': []
    }
    
    # Search users
    if search_type in ["all", "users"]:
        users = db.query(User).filter(
            or_(
                User.full_name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
                User.phone.ilike(f"%{query}%"),
                User.address.ilike(f"%{query}%")
            )
        ).all()
        
        for user in users:
            active_reservation = (
                db.query(Reservation)
                .filter_by(user_id=user.id, end_time=None)
                .options(selectinload(Reservation.parking_spot)
                        .selectinload(ParkingSpot.parking_lot))
                .first()
            )
            results['users'].append({
                'user': user,
                'active_reservation': active_reservation,
                'status': 'Active Parking' if active_reservation else 'No Active Parking'
            })
    
    # Search parking spots
    if search_type in ["all", "spots"]:
        spots = (
            db.query(ParkingSpot)
            .join(ParkingLot)
            .filter(
                or_(
                    ParkingSpot.spot_number.ilike(f"%{query}%"),
                    ParkingLot.name.ilike(f"%{query}%"),
                    ParkingLot.address_line_1.ilike(f"%{query}%")
                )
            )
            .options(
                selectinload(ParkingSpot.parking_lot),
                selectinload(ParkingSpot.reservations)
            )
            .all()
        )
        
        for spot in spots:
            current_reservation = (
                db.query(Reservation)
                .filter_by(parking_spot_id=spot.id, end_time=None)
                .options(selectinload(Reservation.user))
                .first()
            )
            
            results['parking_spots'].append({
                'spot': spot,
                'current_reservation': current_reservation,
                'status_info': get_spot_status_info(spot, current_reservation)
            })
    
    # Search reservations
    if search_type in ["all", "reservations"]:
        reservations = (
            db.query(Reservation)
            .join(User)
            .join(ParkingSpot)
            .join(ParkingLot)
            .filter(
                or_(
                    User.full_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%"),
                    Reservation.vehicle_number.ilike(f"%{query}%"),
                    ParkingSpot.spot_number.ilike(f"%{query}%"),
                    ParkingLot.name.ilike(f"%{query}%")
                )
            )
            .options(
                selectinload(Reservation.user),
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .order_by(Reservation.start_time.desc())
            .all()
        )
        
        for reservation in reservations:
            results['reservations'].append(get_reservation_details(reservation))
    
    # Search parking lots
    if search_type in ["all", "lots"]:
        lots = db.query(ParkingLot).filter(
            or_(
                ParkingLot.name.ilike(f"%{query}%"),
                ParkingLot.address_line_1.ilike(f"%{query}%"),
                ParkingLot.address_line_2.ilike(f"%{query}%"),
                ParkingLot.pin_code.ilike(f"%{query}%")
            )
        ).all()
        
        for lot in lots:
            total_spots = db.query(ParkingSpot).filter_by(parking_lot_id=lot.id).count()
            available_spots = (
                db.query(ParkingSpot)
                .filter_by(parking_lot_id=lot.id, status=SpotStatus.AVAILABLE)
                .count()
            )
            occupied_spots = (
                db.query(ParkingSpot)
                .filter_by(parking_lot_id=lot.id, status=SpotStatus.OCCUPIED)
                .count()
            )
            reserved_spots = (
                db.query(ParkingSpot)
                .filter_by(parking_lot_id=lot.id, status=SpotStatus.RESERVED)
                .count()
            )
            
            results['parking_lots'].append({
                'lot': lot,
                'total_spots': total_spots,
                'available_spots': available_spots,
                'occupied_spots': occupied_spots,
                'reserved_spots': reserved_spots,
                'occupancy_rate': round(
                    (occupied_spots + reserved_spots) / max(1, total_spots) * 100, 1
                )
            })
    
    return results

def get_spot_status_info(spot, current_reservation):
    """
    Get detailed status information for a parking spot.
    
    Args:
        spot: Parking spot object
        current_reservation: Current active reservation if any
        
    Returns:
        dict: Detailed status information
    """
    status_info = {
        'status': spot.status.value,
        'status_class': get_status_css_class(spot.status),
        'details': '',
        'user_info': None,
        'duration': None,
        'cost': 0
    }
    
    if current_reservation:
        status_info['user_info'] = current_reservation.user
        status_info['duration'] = format_duration(current_reservation.start_time)
        status_info['cost'] = calculate_cost(current_reservation)
        
        if current_reservation.occupy_time:
            status_info['details'] = f"Occupied since {current_reservation.occupy_time.strftime('%H:%M')}"
        else:
            status_info['details'] = f"Reserved since {current_reservation.start_time.strftime('%H:%M')}"
    else:
        if spot.status == SpotStatus.AVAILABLE:
            status_info['details'] = "Available for booking"
        else:
            status_info['details'] = f"Status: {spot.status.value}"
    
    return status_info

def get_status_css_class(status):
    """
    Get appropriate CSS class for status styling.
    
    Args:
        status: Parking spot status
        
    Returns:
        str: CSS class name
    """
    status_classes = {
        SpotStatus.AVAILABLE: 'success',
        SpotStatus.RESERVED: 'warning',
        SpotStatus.OCCUPIED: 'danger'
    }
    return status_classes.get(status, 'secondary')


# Application Entry Point


if __name__ == "__main__":
    app.run(debug=True)
