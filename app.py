from pathlib import Path
from functools import wraps

from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash)

from sqlalchemy.orm import sessionmaker

from models.models import engine, User, Admin 

# Flask & DB bootstrap

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-key-change-me"

SessionLocal = sessionmaker(bind=engine, future=True)

# auto-create DB on first run
if not Path("models.db").exists():
    from models.models import create_db         
    create_db()

def ensure_default_admin() -> None:
    with SessionLocal() as db:
        if not db.query(Admin).first():
            db.add(
                Admin(
                    email="admin@vps.local",
                    password="admin123",       
                    full_name="Super Admin"
                )
            )
            db.commit()
            print("✅  Default administrator inserted.")

# Decorators

def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if session.get("role") != role:
                flash("Access denied.")
                return redirect(url_for("login"))
            return view(*a, **kw)
        return wrapped
    return decorator

# Routes

@app.route("/")
def root():                                
    return redirect(url_for("login"))

# ----- user registration -----
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.form
        db = SessionLocal()
        if db.query(User).filter_by(email=data["email"]).first():
            flash("E-mail already taken.")
            return redirect(url_for("register"))

        user = User(email=data["email"],
                    password=data["password"],  # ⚠ plain text per spec
                    full_name=data["full_name"],
                    address=data.get("address"),
                    phone=data.get("phone"),
                    pin_code=data.get("pin_code"))
        db.add(user)
        db.commit()

        session.update({"user_id": user.id, "role": "user"})
        return redirect(url_for("user_dashboard"))
    return render_template("register.html")

# ----- combined login (admin + user) -----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email, pwd = request.form["email"], request.form["password"]
        db = SessionLocal()

        admin = db.query(Admin).filter_by(email=email, password=pwd).first()
        if admin:
            session.update({"user_id": admin.id, "role": "admin"})
            return redirect(url_for("admin_dashboard"))

        user = db.query(User).filter_by(email=email, password=pwd).first()
        if user:
            session.update({"user_id": user.id, "role": "user"})
            return redirect(url_for("user_dashboard"))

        flash("Invalid credentials.")
    return render_template("login.html")

# ----- dashboards -----
@app.route("/dashboard")
@login_required
@role_required("user")
def user_dashboard():
    return render_template("user_dashboard.html")

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

# ----- logout -----
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

if __name__ == "__main__":
    create_db()         
    ensure_default_admin() 
    app.run(debug=True)