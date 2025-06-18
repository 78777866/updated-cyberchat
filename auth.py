import os
import jwt
import uuid
from functools import wraps
from flask import g, session, redirect, request, render_template, url_for, current_app, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user
from supabase import create_client, Client
from app import app, db
from models import User

# Initialize Supabase client
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_ANON_KEY')

if supabase_url and supabase_key:
    supabase: Client = create_client(supabase_url, supabase_key)
else:
    supabase = None

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please sign in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.before_request
def before_request():
    """Set up session and check authentication"""
    if '_session_id' not in session:
        session['_session_id'] = str(uuid.uuid4())
    session.permanent = True
    g.session_id = session['_session_id']

def require_login(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            session["next_url"] = request.url
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def require_creator(f):
    """Decorator to require creator privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_creator:
            return render_template('403.html'), 403
        return f(*args, **kwargs)
    return decorated_function

# Auth routes
@app.route('/auth/login')
def login():
    """Login page with Supabase Auth"""
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    return render_template('auth/login.html')

@app.route('/auth/signup')
def signup():
    """Signup page with Supabase Auth"""
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    return render_template('auth/signup.html')

@app.route('/auth/callback', methods=['POST'])
def auth_callback():
    """Handle authentication callback from Supabase"""
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({'error': 'No access token provided'}), 400
        
        # Verify token with Supabase
        if not supabase:
            return jsonify({'error': 'Supabase not configured'}), 500
        
        # Get user info from Supabase
        response = supabase.auth.get_user(access_token)
        
        if response.user:
            user_data = response.user
            
            # Create or update user in local database
            user = User.query.get(user_data.id)
            if not user:
                user = User(
                    id=user_data.id,
                    email=user_data.email,
                    first_name=user_data.user_metadata.get('first_name'),
                    last_name=user_data.user_metadata.get('last_name'),
                    profile_image_url=user_data.user_metadata.get('avatar_url')
                )
                
                # Make first user a creator
                if User.query.count() == 0:
                    user.is_creator = True
                    user.role = 'creator'
                
                db.session.add(user)
            else:
                # Update existing user
                user.email = user_data.email
                user.first_name = user_data.user_metadata.get('first_name')
                user.last_name = user_data.user_metadata.get('last_name')
                user.profile_image_url = user_data.user_metadata.get('avatar_url')
            
            db.session.commit()
            
            # Log in the user
            login_user(user)
            
            # Redirect to next URL or chat
            next_url = session.pop('next_url', None)
            return jsonify({
                'success': True,
                'redirect_url': next_url or url_for('chat')
            })
        
        return jsonify({'error': 'Invalid token'}), 401
        
    except Exception as e:
        current_app.logger.error(f"Auth callback error: {e}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/auth/logout')
def logout():
    """Logout user"""
    logout_user()
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/auth/user')
def get_current_user():
    """Get current user info"""
    if current_user.is_authenticated:
        return jsonify({
            'id': current_user.id,
            'email': current_user.email,
            'display_name': current_user.get_display_name(),
            'role': current_user.role,
            'is_creator': current_user.is_creator,
            'profile_image_url': current_user.profile_image_url
        })
    return jsonify({'user': None})