from pathlib import Path
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy.orm import sessionmaker, selectinload

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
                password=f["password"],  # plaintext (demo)
                full_name=f["full_name"],
                address=f.get("address"),
                phone=f.get("phone"),
                pin_code=f.get("pin_code"),
            )
            db.add(user)
            db.commit()
            
            session.update({"user_id": user.id, "role": "user"})
            return redirect(url_for("user_dashboard"))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        e, p = request.form["email"], request.form["password"]
        with SessionLocal() as db:
            admin = db.query(Admin).filter_by(email=e, password=p).first()
            if admin:
                session.update({"user_id": admin.id, "role": "admin"})
                return redirect(url_for("admin_dashboard"))
            
            user = db.query(User).filter_by(email=e, password=p).first()
            if user:
                session.update({"user_id": user.id, "role": "user"})
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
        # Fixed: Get current active reservation with proper relationship name
        current_reservation = (
            db.query(Reservation)
            .filter_by(user_id=session["user_id"], end_time=None)
            .options(selectinload(Reservation.parking_spot))  # Fixed: Use parking_spot
            .first()
        )
        return render_template("user_dashboard.html", current_reservation=current_reservation)

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

# ────────────────────────────────────────────────────────────────
# user parking functionalities (Added Missing Routes)
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
            vehicle_number="TEMP-123",  # You might want to collect this from user
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
            .options(selectinload(Reservation.parking_spot))  # Fixed: Use parking_spot
            .order_by(Reservation.start_time.desc())
            .all()
        )
        return render_template("user/history.html", reservations=reservations)

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
                db.flush()  # Flush to get the lot ID
                
                # Manually create spots for new lots
                for i in range(1, lot.number_of_spots + 1):
                    spot = ParkingSpot(
                        spot_number=str(i).zfill(3),
                        parking_lot_id=lot.id,
                        status=SpotStatus.AVAILABLE
                    )
                    db.add(spot)
                
                db.commit()
                flash("Parking lot created with spots.")
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
            lot.name = f["name"]
            lot.address_line_1 = f["addr1"]
            lot.address_line_2 = f.get("addr2")
            lot.address_line_3 = f.get("addr3")
            lot.pin_code = f["pin"]
            lot.price_per_hour = f["price"]
            lot.number_of_spots = int(f["capacity"])
            
            db.commit()
            flash("Parking-lot updated.")
            return redirect(url_for("list_lots"))
        
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

# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
