# Vehicle Parking Management System

A simple web-based parking management system built with Flask and SQLAlchemy. This application allows users to reserve parking spots, manage parking facilities, and track parking sessions with automated billing.

## Features

### For Users
- **Account Registration**: Create customer accounts with personal information
- **Parking Reservations**: Reserve available parking spots in different facilities
- **Session Management**: Occupy and release parking spots with real-time tracking
- **History & Analytics**: View parking history and spending statistics
- **Cost Calculation**: Automatic billing based on duration and hourly rates

### For Administrators
- **Facility Management**: Add, edit, and delete parking facilities
- **Space Management**: Monitor individual parking spot status
- **User Management**: View all customer accounts and their activities
- **Analytics Dashboard**: Comprehensive system statistics and revenue reports
- **Search Functionality**: Search across users, facilities, and parking records

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML templates with Bootstrap styling
- **Authentication**: Session-based login system

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd vehicle-parking-app
   ```

2. **Install dependencies**
   ```bash
   pip install flask sqlalchemy
   ```

3. **Initialize the database**
   ```bash
   python models/models.py
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the system**
   - Open your browser and go to `http://localhost:5000`
   - Register as a new user or login as admin

## Default Accounts

### Administrator Account
- **Email**: admin@vps.local
- **Password**: admin123
- **Access**: Full administrative privileges

## Usage Guide

### For Customers

1. **Registration**: Create a new account with your details
2. **Browse Facilities**: View available parking lots and their rates
3. **Reserve a Spot**: Select a facility and reserve a parking spot
4. **Park Your Vehicle**: Mark the spot as occupied when you arrive
5. **Complete Session**: Mark the spot as released when you leave
6. **View History**: Check your parking history and costs

### For Administrators

1. **Dashboard**: View system overview and statistics
2. **Manage Facilities**: Add new parking lots or modify existing ones
3. **Monitor Spots**: Track the status of all parking spaces
4. **User Management**: View customer accounts and their activities
5. **Analytics**: Access detailed reports and revenue statistics

## Project Structure

```
vehicle-parking-app/
├── app.py                 # Main Flask application
├── models/
│   ├── models.py         # Database models and setup
│   └── models.db         # SQLite database file
├── templates/            # HTML templates
│   ├── admin/           # Admin interface templates
│   ├── user/            # User interface templates
│   ├── base.html        # Base template
│   ├── login.html       # Login page
│   └── register.html    # Registration page
└── README.md            # This file
```

## Database Models

- **User**: Customer accounts with personal information
- **Admin**: Administrator accounts
- **ParkingLot**: Parking facilities with location and pricing
- **ParkingSpot**: Individual parking spaces within facilities
- **Reservation**: Parking sessions from reservation to completion

## Key Features

- **Real-time Availability**: Live tracking of parking spot availability
- **Automated Billing**: Precise cost calculation based on duration
- **Session Management**: Complete lifecycle from reservation to completion
- **Role-based Access**: Separate interfaces for users and administrators
- **Data Integrity**: Robust validation and constraint enforcement

## Business Logic

- **Minimum Billing**: 1-hour minimum charge for all sessions
- **Hourly Rates**: Configurable pricing per facility
- **Conflict Prevention**: Prevents multiple active reservations per user
- **Space Management**: Automatic spot allocation and status updates

## Security Features

- **Session Management**: Secure user sessions with timeout
- **Role-based Access Control**: Different permissions for users and admins
- **Input Validation**: Comprehensive form validation
- **SQL Injection Prevention**: Parameterized queries through SQLAlchemy

## Development

### Running in Development Mode
```bash
python app.py
```
The application will run in debug mode on `http://localhost:5000`

### Database Reset
To reset the database, simply delete `models/models.db` and run:
```bash
python models/models.py
```

## Troubleshooting

### Common Issues

1. **Database not found**: Run `python models/models.py` to create the database
2. **Import errors**: Ensure all dependencies are installed with `pip install flask sqlalchemy`
3. **Port already in use**: Change the port in `app.py` or stop other applications using port 5000

### Error Messages

- **"Email already registered"**: Use a different email address for registration
- **"No available spots"**: All spots in the selected facility are currently occupied
- **"Access denied"**: Ensure you're logged in with the correct role

## Future Enhancements

- Mobile application support
- Online payment integration
- Real-time notifications
- Advanced analytics and reporting
- Multi-language support
- API endpoints for third-party integrations
