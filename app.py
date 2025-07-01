from pathlib import Path
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import or_  # ✅ FIXED: Added missing import

from models.models import (
    engine, create_db,
    User, Admin, ParkingLot, ParkingSpot, Reservation, SpotStatus
)

# ────────────────────────────────────────────────────────────────
# Flask & DB bootstrap
# ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-key-change-me"
SessionLocal = sessionmaker(bind=engine, future=True)

if not Path("models/models.db").exists():  # build DB first run
    create_db()

# ────────────────────────────────────────────────────────────────
# default admin
# ────────────────────────────────────────────────────────────────

def ensure_default_admin():
    with SessionLocal() as db:
        if db.query(Admin).first():
            return
        db.add(Admin(email="admin@vps.local",
                    password="admin123",
                    full_name="Super Admin"))
        db.commit()

ensure_default_admin()

def calculate_cost(reservation):
    """Calculate cost for a reservation based on duration and hourly rate"""
    if not reservation.end_time:
        # For active reservations, calculate current cost
        end_time = datetime.now()
    else:
        end_time = reservation.end_time
    
    duration = end_time - reservation.start_time
    # Calculate hours (minimum 1 hour billing)
    hours = max(1, duration.total_seconds() / 3600)
    # Get hourly rate and calculate cost
    hourly_rate = float(reservation.parking_spot.parking_lot.price_per_hour)
    total_cost = round(hours * hourly_rate, 2)
    return total_cost

def format_duration(start_time, end_time=None):
    """Format duration between two datetime objects"""
    if not end_time:
        end_time = datetime.now()
    
    duration = end_time - start_time
    total_minutes = int(duration.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def get_reservation_details(reservation):
    """Get comprehensive reservation details including cost and duration"""
    details = {
        'reservation': reservation,
        'duration_formatted': 'N/A',
        'duration_minutes': 0,
        'cost': 0.00,
        'status': 'Reserved'
    }  # ✅ FIXED: Added missing closing brace
    
    if reservation.end_time:
        # Completed reservation
        details['status'] = 'Completed'
        details['duration_formatted'] = format_duration(reservation.start_time, reservation.end_time)
        duration_delta = reservation.end_time - reservation.start_time
        details['duration_minutes'] = int(duration_delta.total_seconds() / 60)
        details['cost'] = calculate_cost(reservation)
    elif reservation.occupy_time:
        # Currently occupied
        details['status'] = 'Occupied'
        details['duration_formatted'] = format_duration(reservation.start_time)
        duration_delta = datetime.now() - reservation.start_time
        details['duration_minutes'] = int(duration_delta.total_seconds() / 60)
        details['cost'] = calculate_cost(reservation)
    
    return details

# Make functions available in templates
app.jinja_env.globals.update(
    format_duration=format_duration,
    calculate_cost=calculate_cost,
    get_reservation_details=get_reservation_details
)

# ────────────────────────────────────────────────────────────────
# decorators
# ────────────────────────────────────────────────────────────────

def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped

def role_required(role):
    def deco(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if session.get("role") != role:
                flash("Access denied.")
                return redirect(url_for("login"))
            return view(*a, **kw)
        return wrapped
    return deco

# ────────────────────────────────────────────────────────────────
# auth
# ────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        with SessionLocal() as db:
            if db.query(User).filter_by(email=f["email"]).first():
                flash("E-mail already taken.")
                return redirect(url_for("register"))
            
            user = User(
                email=f["email"],
                password=f["password"],
                full_name=f["full_name"],
                address=f.get("address"),
                phone=f.get("phone"),
                pin_code=f.get("pin_code"),
            )
            db.add(user)
            db.commit()
            
            # Fixed session assignment
            session["user_id"] = user.id
            session["role"] = "user"
            return redirect(url_for("user_dashboard"))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        e, p = request.form["email"], request.form["password"]
        with SessionLocal() as db:
            admin = db.query(Admin).filter_by(email=e, password=p).first()
            if admin:
                session["user_id"] = admin.id
                session["role"] = "admin"
                return redirect(url_for("admin_dashboard"))
            
            user = db.query(User).filter_by(email=e, password=p).first()
            if user:
                session["user_id"] = user.id
                session["role"] = "user"
                return redirect(url_for("user_dashboard"))
        
        flash("Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

# ────────────────────────────────────────────────────────────────
# dashboards
# ────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
@role_required("user")
def user_dashboard():
    with SessionLocal() as db:
        current_reservation = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"], end_time=None)
            .options(selectinload(Reservation.parking_spot)
                    .selectinload(ParkingSpot.parking_lot))
            .first()
        )
        
        # Calculate current cost if reservation exists
        current_cost = 0
        if current_reservation:
            current_cost = calculate_cost(current_reservation)
        
        return render_template("user_dashboard.html",
                             current_reservation=current_reservation,
                             current_cost=current_cost)

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    with SessionLocal() as db:
        # Get basic stats for dashboard overview
        total_users = db.query(User).count()
        total_lots = db.query(ParkingLot).count()
        active_reservations = db.query(Reservation).filter(Reservation.end_time.is_(None)).count()
        total_spots = db.query(ParkingSpot).count()
        available_spots = db.query(ParkingSpot).filter_by(status=SpotStatus.AVAILABLE).count()
        
        dashboard_stats = {
            'total_users': total_users,
            'total_lots': total_lots,
            'active_reservations': active_reservations,
            'total_spots': total_spots,
            'available_spots': available_spots
        }
        
        return render_template("admin_dashboard.html", stats=dashboard_stats)

# ────────────────────────────────────────────────────────────────
# user parking functionalities (FIXED Routes)
# ────────────────────────────────────────────────────────────────

@app.route("/user/lots")
@login_required
@role_required("user")
def user_view_lots():
    with SessionLocal() as db:
        lots = db.query(ParkingLot).all()
        # Get available spots count for each lot
        lots_with_availability = []
        for lot in lots:
            available_spots = (
                db.query(ParkingSpot)
                .filter_by(parking_lot_id=lot.id, status=SpotStatus.AVAILABLE)
                .count()
            )
            lots_with_availability.append({
                'lot': lot,
                'available_spots': available_spots
            })
        
        return render_template("user/lots.html", lots_data=lots_with_availability)

# ✅ FIXED: Added missing lot_id parameter in route
@app.route("/user/reserve/<int:lot_id>", methods=["POST"])
@login_required
@role_required("user")
def reserve_spot(lot_id):
    with SessionLocal() as db:
        # Check if user already has an active reservation
        active_reservation = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"], end_time=None)
            .first()
        )
        
        if active_reservation:
            flash("You already have an active reservation.")
            return redirect(url_for("user_view_lots"))
        
        # Find first available spot in the lot
        available_spot = (
            db.query(ParkingSpot)
            .filter_by(parking_lot_id=lot_id, status=SpotStatus.AVAILABLE)
            .first()
        )
        
        if not available_spot:
            flash("No available spots in this parking lot.")
            return redirect(url_for("user_view_lots"))
        
        # Create reservation
        reservation = Reservation(
            user_id=session["user_id"],
            parking_spot_id=available_spot.id,
            vehicle_number=request.form.get("vehicle_number", "TEMP-123"),
            start_time=datetime.now(),
            occupy_time=None,
            end_time=None
        )
        
        # Update spot status to reserved
        available_spot.status = SpotStatus.RESERVED
        db.add(reservation)
        db.commit()
        
        flash(f"Spot {available_spot.spot_number} reserved successfully!")
        return redirect(url_for("user_dashboard"))

# ✅ FIXED: Added missing reservation_id parameter in route
@app.route("/user/occupy/<int:reservation_id>", methods=["POST"])
@login_required
@role_required("user")
def occupy_spot(reservation_id):
    with SessionLocal() as db:
        reservation = (
            db.query(Reservation)
            .filter_by(id=reservation_id, user_id=session["user_id"])
            .first()
        )
        
        if not reservation:
            flash("Reservation not found.")
            return redirect(url_for("user_dashboard"))
        
        if reservation.end_time is not None:
            flash("This reservation is already completed.")
            return redirect(url_for("user_dashboard"))
        
        # Update spot status to occupied
        spot = db.get(ParkingSpot, reservation.parking_spot_id)
        spot.status = SpotStatus.OCCUPIED
        # Update reservation with occupy timestamp
        reservation.occupy_time = datetime.now()
        db.commit()
        
        flash("Spot occupied successfully!")
        return redirect(url_for("user_dashboard"))

# ✅ FIXED: Added missing reservation_id parameter in route
@app.route("/user/release/<int:reservation_id>", methods=["POST"])
@login_required
@role_required("user")
def release_spot(reservation_id):
    with SessionLocal() as db:
        reservation = (
            db.query(Reservation)
            .filter_by(id=reservation_id, user_id=session["user_id"])
            .first()
        )
        
        if not reservation:
            flash("Reservation not found.")
            return redirect(url_for("user_dashboard"))
        
        if reservation.end_time is not None:
            flash("This reservation is already completed.")
            return redirect(url_for("user_dashboard"))
        
        # Update spot status to available
        spot = db.get(ParkingSpot, reservation.parking_spot_id)
        spot.status = SpotStatus.AVAILABLE
        # Complete the reservation
        reservation.end_time = datetime.now()
        db.commit()
        
        flash("Spot released successfully!")
        return redirect(url_for("user_dashboard"))

@app.route("/user/history")
@login_required
@role_required("user")
def parking_history():
    with SessionLocal() as db:
        reservations = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"])
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .order_by(Reservation.start_time.desc())
            .all()
        )
        
        history_data = []
        total_spent = 0
        for reservation in reservations:
            details = get_reservation_details(reservation)
            history_data.append(details)
            total_spent += details['cost']
        
        summary = {
            'total_reservations': len(reservations),
            'completed_reservations': len([r for r in reservations if r.end_time]),
            'total_spent': round(total_spent, 2),
            'average_cost': round(total_spent / max(1, len([r for r in reservations if r.end_time])), 2)
        }
        
        return render_template("user/history.html",
                             history_data=history_data,
                             summary=summary)

@app.route("/user/summary")
@login_required
@role_required("user")
def user_summary():
    with SessionLocal() as db:
        user_id = session["user_id"]
        reservations = (
            db.query(Reservation)
            .filter_by(user_id=user_id)
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .all()
        )
        
        # Calculate comprehensive statistics
        completed_reservations = [r for r in reservations if r.end_time]
        active_reservations = [r for r in reservations if not r.end_time]
        total_spent = 0
        total_minutes = 0
        current_session_cost = 0
        
        # Process completed reservations
        for reservation in completed_reservations:
            cost = calculate_cost(reservation)
            total_spent += cost
            duration = reservation.end_time - reservation.start_time
            total_minutes += int(duration.total_seconds() / 60)
        
        # Calculate current session cost
        for reservation in active_reservations:
            current_session_cost += calculate_cost(reservation)
        
        summary_data = {
            'total_reservations': len(reservations),
            'completed_reservations': len(completed_reservations),
            'active_reservations': len(active_reservations),
            'total_spent': round(total_spent, 2),
            'current_session_cost': round(current_session_cost, 2),
            'total_duration': f"{total_minutes // 60}h {total_minutes % 60}m",
            'average_cost_per_session': round(total_spent / max(1, len(completed_reservations)), 2)
        }
        
        return render_template("user/summary.html",
                             summary=summary_data,
                             current_date=datetime.now())

# ────────────────────────────────────────────────────────────────
# parking-lot CRUD
# ────────────────────────────────────────────────────────────────

@app.route("/admin/lots")
@login_required
@role_required("admin")
def list_lots():
    with SessionLocal() as db:
        lots = db.query(ParkingLot).all()
        return render_template("admin/lots.html", lots=lots)

@app.route("/admin/lots/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_lot():
    if request.method == "POST":
        f = request.form
        with SessionLocal() as db:
            try:
                lot = ParkingLot(
                    name=f["name"],
                    address_line_1=f["addr1"],
                    address_line_2=f.get("addr2"),
                    address_line_3=f.get("addr3"),
                    pin_code=f["pin"],
                    price_per_hour=f["price"],
                    number_of_spots=int(f["capacity"]),
                )
                db.add(lot)
                db.flush()  
                
                db.commit()
                flash(f"Parking lot '{lot.name}' created with {lot.number_of_spots} spots.")
                return redirect(url_for("list_lots"))
                
            except Exception as e:
                db.rollback()
                flash(f"Error creating parking lot: {str(e)}")
                return redirect(url_for("add_lot"))
    
    return render_template("admin/lot_form.html", action="Add")

@app.route("/admin/lots/<int:lot_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_lot(lot_id):
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Lot not found.")
            return redirect(url_for("list_lots"))
        
        if request.method == "POST":
            f = request.form
            try:
                original_capacity = lot.number_of_spots
                new_capacity = int(f["capacity"])
                
                # ✅ Check if decreasing and validate
                if new_capacity < original_capacity:
                    # Check if spots to be removed are available
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
                        flash(f"Cannot reduce capacity to {new_capacity}. These spots are in use: {', '.join(unavailable_spots)}")
                        return render_template("admin/lot_form.html", lot=lot, action="Edit")
                
                # Update lot properties
                lot.name = f["name"]
                lot.address_line_1 = f["addr1"]
                lot.address_line_2 = f.get("addr2")
                lot.address_line_3 = f.get("addr3")
                lot.pin_code = f["pin"]
                lot.price_per_hour = f["price"]
                
                # ✅ This triggers the event listener to manage spots
                lot.number_of_spots = new_capacity
                
                db.commit()
                
                if new_capacity > original_capacity:
                    flash(f"Parking lot updated. Added {new_capacity - original_capacity} new spots.")
                elif new_capacity < original_capacity:
                    flash(f"Parking lot updated. Reduced capacity by {original_capacity - new_capacity} spots.")
                else:
                    flash("Parking lot updated.")
                    
                return redirect(url_for("list_lots"))
                
            except Exception as e:
                db.rollback()
                flash(f"Error updating parking lot: {str(e)}")
                return render_template("admin/lot_form.html", lot=lot, action="Edit")
        return render_template("admin/lot_form.html", lot=lot, action="Edit")


@app.route("/admin/lots/<int:lot_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_lot(lot_id):
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Lot not found.")
            return redirect(url_for("list_lots"))
        
        if any(s.status != SpotStatus.AVAILABLE for s in lot.spots):
            flash("Can't delete – one or more spots are still in use.")
            return redirect(url_for("list_lots"))
        
        db.delete(lot)
        db.commit()
        flash("Parking-lot deleted.")
        return redirect(url_for("list_lots"))

# ────────────────────────────────────────────────────────────────
# spot overview
# ────────────────────────────────────────────────────────────────

@app.route("/admin/lots/<int:lot_id>/spots")
@login_required
@role_required("admin")
def lot_spots(lot_id):
    with SessionLocal() as db:
        lot = db.get(ParkingLot, lot_id)
        if not lot:
            flash("Lot not found.")
            return redirect(url_for("list_lots"))
        
        spots = (
            db.query(ParkingSpot)
            .filter_by(parking_lot_id=lot.id)
            .order_by(ParkingSpot.spot_number)
            .options(selectinload(ParkingSpot.reservations))
            .all()
        )
        
        return render_template("admin/spots.html",
                             lot=lot,
                             spots=spots,
                             SpotStatus=SpotStatus)

# ────────────────────────────────────────────────────────────────
# user registry
# ────────────────────────────────────────────────────────────────

@app.route("/admin/users")
@login_required
@role_required("admin")
def list_users():
    with SessionLocal() as db:
        users = (
            db.query(User)
            .outerjoin(
                Reservation,
                (Reservation.user_id == User.id) &
                (Reservation.end_time.is_(None))
            )
            .add_entity(Reservation)
            .all()
        )
        
        return render_template("admin/users.html", users=users)

@app.route("/admin/parking-records")
@login_required
@role_required("admin")
def admin_parking_records():
    with SessionLocal() as db:
        # Base query - removed pagination
        query = (
            db.query(Reservation)
            .options(
                selectinload(Reservation.user),
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .order_by(Reservation.start_time.desc())
        )
        
        # Basic filters
        status_filter = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        if status_filter:
            if status_filter == 'active':
                query = query.filter(Reservation.end_time.is_(None))
            elif status_filter == 'completed':
                query = query.filter(Reservation.end_time.isnot(None))
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Reservation.start_time >= date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(Reservation.start_time <= date_to_obj)
            except ValueError:
                pass
        
        # Get all reservations (no pagination)
        reservations = query.all()
        total_records = len(reservations)
        
        # Process reservations with duration and cost
        records_data = []
        for reservation in reservations:
            duration_minutes = 0
            cost = 0
            status = "Reserved"
            
            if reservation.end_time:
                duration_delta = reservation.end_time - reservation.start_time
                duration_minutes = int(duration_delta.total_seconds() / 60)
                duration_hours = max(1, duration_minutes / 60)
                cost = round(float(duration_hours * float(reservation.parking_spot.parking_lot.price_per_hour)), 2)
                status = "Completed"
            elif reservation.occupy_time:
                status = "Occupied"
                # Show current duration for occupied spots
                duration_delta = datetime.now() - reservation.start_time
                duration_minutes = int(duration_delta.total_seconds() / 60)
            
            records_data.append({
                'reservation': reservation,
                'duration_minutes': duration_minutes,
                'duration_formatted': f"{duration_minutes // 60}h {duration_minutes % 60}m" if duration_minutes > 0 else "N/A",
                'cost': cost,
                'status': status
            })
        
        return render_template("admin/parking_records.html",
                             records=records_data,
                             total_records=total_records,
                             filters={
                                 'status': status_filter,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })

@app.route("/admin/summary")
@login_required
@role_required("admin")
def admin_summary():
    with SessionLocal() as db:
        # Basic statistics
        total_users = db.query(User).count()
        total_reservations = db.query(Reservation).count()
        completed_reservations_count = db.query(Reservation).filter(Reservation.end_time.isnot(None)).count()
        active_reservations = db.query(Reservation).filter(Reservation.end_time.is_(None)).count()
        
        # Get completed reservations for revenue calculation
        completed_reservations = (
            db.query(Reservation)
            .filter(Reservation.end_time.isnot(None))
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .all()
        )
        
        # Calculate total revenue using consistent cost calculation
        total_revenue = sum(calculate_cost(reservation) for reservation in completed_reservations)
        
        # Calculate potential current revenue from active sessions
        active_reservations_data = (
            db.query(Reservation)
            .filter(Reservation.end_time.is_(None))
            .options(
                selectinload(Reservation.parking_spot)
                .selectinload(ParkingSpot.parking_lot)
            )
            .all()
        )
        
        potential_revenue = sum(calculate_cost(reservation) for reservation in active_reservations_data)
        
        summary_data = {
            'total_users': total_users,
            'total_reservations': total_reservations,
            'completed_reservations': completed_reservations_count,
            'active_reservations': active_reservations,
            'total_revenue': round(total_revenue, 2),
            'potential_current_revenue': round(potential_revenue, 2),
            'average_revenue_per_session': round(total_revenue / max(1, completed_reservations_count), 2)
        }
        
        return render_template("admin/summary.html", summary=summary_data)

@app.route("/admin/search", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_search():
    """Unified search interface for admin dashboard"""
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
    """Perform search across different entities based on search type"""
    results = {
        'users': [],
        'parking_spots': [],
        'reservations': [],
        'parking_lots': []
    }
    
    # Search Users
    if search_type in ["all", "users"]:
        users = db.query(User).filter(
            or_(  # ✅ FIXED: Using proper SQLAlchemy or_ function
                User.full_name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
                User.phone.ilike(f"%{query}%"),
                User.address.ilike(f"%{query}%")
            )
        ).all()
        
        for user in users:
            current_reservation = (
                db.query(Reservation)
                .filter_by(user_id=user.id, end_time=None)
                .options(selectinload(Reservation.parking_spot)
                        .selectinload(ParkingSpot.parking_lot))
                .first()
            )
            results['users'].append({
                'user': user,
                'current_reservation': current_reservation,
                'status': 'Active Parking' if current_reservation else 'No Active Parking'
            })
    
    # Search Parking Spots
    if search_type in ["all", "spots"]:
        spots = (
            db.query(ParkingSpot)
            .join(ParkingLot)
            .filter(
                or_(  # ✅ FIXED: Using proper SQLAlchemy or_ function
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
    
    # Search Reservations
    if search_type in ["all", "reservations"]:
        reservations = (
            db.query(Reservation)
            .join(User)
            .join(ParkingSpot)
            .join(ParkingLot)
            .filter(
                or_(  # ✅ FIXED: Using proper SQLAlchemy or_ function
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
    
    # Search Parking Lots
    if search_type in ["all", "lots"]:
        lots = db.query(ParkingLot).filter(
            or_(  # ✅ FIXED: Using proper SQLAlchemy or_ function
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
                'occupancy_rate': round((occupied_spots + reserved_spots) / max(1, total_spots) * 100, 1)
            })
    
    return results

def get_spot_status_info(spot, current_reservation):
    """Get detailed status information for a parking spot"""
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
    """Get CSS class for spot status styling"""
    status_classes = {
        SpotStatus.AVAILABLE: 'success',
        SpotStatus.RESERVED: 'warning',
        SpotStatus.OCCUPIED: 'danger'
    }
    return status_classes.get(status, 'secondary')

# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
