from functools import wraps
from flask import request, jsonify, session, current_app
from services.security_service import SecurityService
import logging

security_service = SecurityService()

def validate_csrf_token():
    """Middleware to validate CSRF tokens"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
                session_id = session.get('_browser_session_key', '')
                
                if not token or not security_service.validate_csrf_token(token, session_id):
                    logging.warning(f"CSRF validation failed for {request.endpoint}")
                    return jsonify({'error': 'CSRF token validation failed'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_input():
    """Middleware to sanitize input data"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.is_json and request.get_json():
                data = request.get_json()
                for key, value in data.items():
                    if isinstance(value, str):
                        data[key] = security_service.sanitize_html(value)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_security_event(event_type: str, details: str = ""):
    """Log security events"""
    logging.warning(f"SECURITY EVENT: {event_type} - IP: {request.remote_addr} - {details}")