# Vehicle Parking Management System

Welcome! This is a simple web app to help you manage parking lots, reserve spots, and keep track of parking sessions—all from your browser. Whether you’re a user looking for a place to park or an admin managing a facility, this app has you covered.

## Features

### For Users
- **Sign Up:** Create your own account in just a minute.
- **Reserve a Spot:** See which parking spots are open and book one before you arrive.
- **Park & Go:** Mark your spot as occupied when you park, and release it when you leave.
- **See Your History:** Check out where you’ve parked and how much you’ve spent.

### For Admins
- **Manage Lots:** Add new parking lots or update details for existing ones.
- **Monitor Spaces:** See which spots are free, reserved, or occupied in real time.
- **User Management:** View all users and their activity.
- **Analytics:** Get reports on usage and revenue.
- **Search:** Quickly find users, lots, or parking records.

---

## Tech Stack

- **Backend:** Python Flask
- **Database:** SQLite (with SQLAlchemy)
- **Frontend:** HTML templates (Bootstrap + a bit of custom CSS)
- **Authentication:** Simple session-based login

---

## Getting Started

### What You’ll Need
- Python 3.7 or newer
- pip (Python’s package installer)

### Setup Steps

1. **Clone the Repo**
   ```bash
   git clone <repository-url>
   cd vehicle-parking-app
   ```

2. **Install the Required Packages**
   ```bash
   pip install flask sqlalchemy
   ```

3. **Set Up the Database**
   ```bash
   python models/models.py
   ```

4. **Run the App**
   ```bash
   python app.py
   ```

5. **Open in Your Browser**
   - Go to [http://localhost:5000](http://localhost:5000)
   - Register as a new user, or log in as admin (see below)

---

## Default Admin Account

- **Email:** admin@vps.local
- **Password:** admin123
- **Access:** Full admin rights

---

## How to Use

### If You’re a Customer

1. **Register:** Fill in your details to create an account.
2. **Browse Lots:** See what’s available and check prices.
3. **Reserve:** Pick a spot and reserve it.
4. **Park:** Mark your spot as occupied when you arrive.
5. **Leave:** Release your spot when you’re done.
6. **History:** See your past parking sessions and costs.

### If You’re an Admin

1. **Dashboard:** Get a quick overview of the system.
2. **Manage Lots:** Add or edit parking lots.
3. **Monitor Spots:** See the status of every spot.
4. **Manage Users:** View all users and their activity.
5. **Analytics:** Dive into reports and revenue stats.

---

## Project Layout

```
vehicle-parking-app/
├── app.py                 # Main Flask app
├── models/
│   ├── models.py         # Database models
│   └── models.db         # The database file
├── templates/            # HTML templates
│   ├── admin/           # Admin pages
│   ├── user/            # User pages
│   ├── base.html        # Base template
│   ├── login.html       # Login page
│   └── register.html    # Registration page
├── static/               # CSS, images, etc.
│   └── style.css        # Main stylesheet
└── README.md            # This file
```

---

## How the Database Works

- **User:** Stores info about each customer
- **Admin:** Admin accounts
- **ParkingLot:** Details about each parking facility
- **ParkingSpot:** Each individual spot in a lot
- **Reservation:** Tracks each parking session

---

## Key Features

- **Live Availability:** See which spots are open right now
- **Automatic Billing:** Charges are calculated based on how long you park
- **Session Management:** From reservation to completion, it’s all tracked
- **Role-Based Access:** Different dashboards for users and admins
- **Data Integrity:** Built-in checks to keep your data safe

---

## How It All Works

- **Minimum Billing:** You’re charged for at least 1 hour, even if you stay less
- **Hourly Rates:** Each lot can have its own price per hour
- **No Double Booking:** You can’t reserve more than one spot at a time
- **Smart Space Management:** The system keeps track of which spots are free or taken

---

## Security

- **Sessions:** Secure login with session timeouts
- **Role Checks:** Only admins can access admin features
- **Input Validation:** Forms are checked for errors
- **SQL Injection Protection:** All database queries are safe

---

## For Developers

### Running in Dev Mode
```bash
python app.py
```
The app will run in debug mode at [http://localhost:5000](http://localhost:5000)

### Customizing Styles

All the CSS is in `static/style.css`. Edit this file to change the look and feel.

### Resetting the Database

If you want to start fresh, delete `models/models.db` and run:
```bash
python models/models.py
```

---

## Troubleshooting

- **Database not found?** Run `python models/models.py` to create it.
- **Import errors?** Make sure you installed everything with `pip install flask sqlalchemy`.
- **Port in use?** Change the port in `app.py` or close whatever else is using 5000.

**Common Error Messages:**
- “Email already registered”: Try a different email.
- “No available spots”: All spots are currently taken.
- “Access denied”: Make sure you’re logged in with the right account.

---

## What’s Next?

- Mobile app support
- Online payments
- More advanced analytics
- API for third-party integrations

---

If you have any questions or want to contribute, feel free to reach out. Happy parking!