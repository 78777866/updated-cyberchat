import os
import logging
from functools import wraps
from flask import request, session, redirect, url_for, flash, render_template
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, UserActivityLog, LoginAttempt

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def log_user_activity(user_id, action, details=None):
    """Log user activity"""
    try:
        activity = UserActivityLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log user activity: {e}")

def log_login_attempt(username, success):
    """Log login attempt"""
    try:
        attempt = LoginAttempt(
            username=username,
            ip_address=request.remote_addr,
            success=success,
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(attempt)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log login attempt: {e}")

def require_permission(permission):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission):
                flash('You do not have permission to access this resource.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def create_default_owner():
    """Create default owner account if it doesn't exist"""
    try:
        # Check if owner account exists
        owner = User.query.filter_by(role='owner').first()
        if not owner:
            # Create default owner account
            owner = User(
                username='Kayushan',
                role='owner',
                is_active=True,
                must_change_password=True,
                daily_message_limit=10000  # High limit for owner
            )
            # Set temporary password that must be changed
            owner.set_password('TempPass123!')
            
            db.session.add(owner)
            db.session.commit()
            
            logging.info("Default owner account created: Kayushan")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to create default owner account: {e}")
        return False

def authenticate_user(username, password):
    """Authenticate user with username and password"""
    try:
        # Find user by username
        user = User.query.filter_by(username=username).first()
        
        if not user:
            log_login_attempt(username, False)
            return None, "Invalid username or password"
        
        # Check if account is locked
        if user.is_locked():
            log_login_attempt(username, False)
            return None, "Account is temporarily locked due to multiple failed login attempts"
        
        # Check if account is active
        if not user.is_active:
            log_login_attempt(username, False)
            return None, "Account is disabled"
        
        # Verify password
        if not user.check_password(password):
            user.increment_failed_attempts()
            log_login_attempt(username, False)
            return None, "Invalid username or password"
        
        # Successful login
        user.unlock_account()  # Reset failed attempts
        user.last_login = db.func.now()
        db.session.commit()
        
        log_login_attempt(username, True)
        log_user_activity(user.id, 'login', 'User logged in successfully')
        
        return user, None
        
    except Exception as e:
        logging.error(f"Authentication error: {e}")
        return None, "An error occurred during login"

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"

# Initialize default owner account when module is imported
with app.app_context():
    create_default_owner()