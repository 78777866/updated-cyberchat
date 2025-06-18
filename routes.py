import os
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.utils import secure_filename

from app import app, db
from models import User, APIKey, ChatMessage, SystemSettings, UserModelPreference, UserActivityLog
from auth import authenticate_user, require_permission, log_user_activity, validate_password_strength
from services.ai_service import AIService
from services.file_service import FileService
from services.search_service import SearchService
from services.encryption_service import EncryptionService

# Make session permanent
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validate input
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        # Authenticate user
        user, error = authenticate_user(username, password)
        
        if error:
            flash(error, 'error')
            return render_template('login.html')
        
        # Login successful
        login_user(user, remember=True)
        
        # Check if password must be changed
        if user.must_change_password:
            flash('You must change your password before continuing.', 'warning')
            return redirect(url_for('change_password'))
        
        # Redirect to next page or chat
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('chat'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_user_activity(current_user.id, 'logout', 'User logged out')
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate current password (skip for forced password change)
        if not current_user.must_change_password:
            if not current_password or not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
                return render_template('change_password.html')
        
        # Validate new password
        if not new_password or not confirm_password:
            flash('Please fill in all password fields.', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('change_password.html')
        
        # Check password strength
        is_strong, message = validate_password_strength(new_password)
        if not is_strong:
            flash(message, 'error')
            return render_template('change_password.html')
        
        # Update password
        current_user.set_password(new_password)
        current_user.must_change_password = False
        db.session.commit()
        
        log_user_activity(current_user.id, 'password_change', 'Password changed successfully')
        flash('Password changed successfully.', 'success')
        return redirect(url_for('chat'))
    
    return render_template('change_password.html')

@app.route('/chat')
def chat():
    # Get or create session ID for anonymous users
    if not current_user.is_authenticated:
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        # Check anonymous message limit
        anonymous_messages = ChatMessage.query.filter_by(
            session_id=session['session_id'],
            user_id=None
        ).count()
        if anonymous_messages >= 10:  # Anonymous limit
            flash('You have reached the message limit. Please sign in to continue.', 'warning')
            return redirect(url_for('login'))
    
    return render_template('chat.html')

@app.route('/settings')
@require_permission('manage_system')
def settings():
    api_keys = APIKey.query.filter_by(user_id=current_user.id).all()
    users = User.query.all()
    return render_template('settings.html', api_keys=api_keys, users=users)

@app.route('/users')
@require_permission('manage_users')
def users():
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/activity_logs')
@require_permission('view_logs')
def activity_logs():
    page = request.args.get('page', 1, type=int)
    logs = UserActivityLog.query.order_by(UserActivityLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('activity_logs.html', logs=logs)

# API Routes
@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        model = data.get('model', 'openai/gpt-3.5-turbo')
        
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Check message limits
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id', str(uuid.uuid4()))
        
        if current_user.is_authenticated:
            if not current_user.can_send_message():
                return jsonify({'error': 'Daily message limit reached'}), 429
            current_user.increment_message_count()
        else:
            # Check anonymous limit
            anonymous_messages = ChatMessage.query.filter_by(
                session_id=session_id,
                user_id=None
            ).count()
            if anonymous_messages >= 10:
                return jsonify({'error': 'Message limit reached. Please sign in to continue.'}), 429
        
        # Save user message
        user_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message_type='user',
            content=message
        )
        db.session.add(user_message)
        db.session.commit()
        
        # Get AI response
        ai_service = AIService()
        response = ai_service.get_chat_response(message, user_id or session_id, model)
        
        # Save AI response
        ai_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message_type='assistant',
            content=response
        )
        db.session.add(ai_message)
        db.session.commit()
        
        return jsonify({
            'response': response,
            'messages_remaining': get_messages_remaining()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check message limits
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id', str(uuid.uuid4()))
        
        if current_user.is_authenticated:
            if not current_user.can_send_message():
                return jsonify({'error': 'Daily message limit reached'}), 429
        else:
            anonymous_messages = ChatMessage.query.filter_by(
                session_id=session_id,
                user_id=None
            ).count()
            if anonymous_messages >= 10:
                return jsonify({'error': 'Message limit reached. Please sign in to continue.'}), 429
        
        file_service = FileService()
        result = file_service.process_file(file)
        
        if 'error' in result:
            return jsonify(result), 400
        
        # Get AI response for file
        ai_service = AIService()
        response = ai_service.process_file_content(result, user_id or session_id)
        
        # Save file message
        file_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message_type='user',
            content=f"Uploaded file: {result['filename']}",
            file_data=result
        )
        db.session.add(file_message)
        
        # Save AI response
        ai_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message_type='assistant',
            content=response
        )
        db.session.add(ai_message)
        db.session.commit()
        
        if current_user.is_authenticated:
            current_user.increment_message_count()
        
        return jsonify({
            'file_info': result,
            'response': response,
            'messages_remaining': get_messages_remaining()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query cannot be empty'}), 400
        
        # Check message limits
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id', str(uuid.uuid4()))
        
        if current_user.is_authenticated:
            if not current_user.can_send_message():
                return jsonify({'error': 'Daily message limit reached'}), 429
            current_user.increment_message_count()
        else:
            anonymous_messages = ChatMessage.query.filter_by(
                session_id=session_id,
                user_id=None
            ).count()
            if anonymous_messages >= 10:
                return jsonify({'error': 'Message limit reached. Please sign in to continue.'}), 429
        
        search_service = SearchService()
        results = search_service.search(query)
        
        # Save search message
        search_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message_type='user',
            content=f"🔍 Search: {query}"
        )
        db.session.add(search_message)
        
        # Save search results
        results_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message_type='assistant',
            content=results
        )
        db.session.add(results_message)
        db.session.commit()
        
        return jsonify({
            'results': results,
            'messages_remaining': get_messages_remaining()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_api_key', methods=['POST'])
@require_permission('manage_api_keys')
def save_api_key():
    try:
        data = request.get_json()
        service = data.get('service')
        key_name = data.get('key_name')
        api_key = data.get('api_key')
        
        if not all([service, key_name, api_key]):
            return jsonify({'error': 'All fields are required'}), 400
        
        # Encrypt the API key
        encryption_service = EncryptionService()
        encrypted_key = encryption_service.encrypt(api_key)
        
        # Check if key already exists
        existing_key = APIKey.query.filter_by(
            user_id=current_user.id,
            service=service,
            key_name=key_name
        ).first()
        
        if existing_key:
            existing_key.encrypted_key = encrypted_key
        else:
            new_key = APIKey(
                user_id=current_user.id,
                service=service,
                key_name=key_name,
                encrypted_key=encrypted_key
            )
            db.session.add(new_key)
        
        db.session.commit()
        log_user_activity(current_user.id, 'api_key_saved', f'API key saved for service: {service}')
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_api_key', methods=['DELETE'])
@require_permission('manage_api_keys')
def delete_api_key():
    try:
        key_id = request.json.get('key_id')
        if not key_id:
            return jsonify({'error': 'Key ID required'}), 400
        
        api_key = APIKey.query.filter_by(id=key_id, user_id=current_user.id).first()
        if not api_key:
            return jsonify({'error': 'API key not found'}), 404
        
        db.session.delete(api_key)
        db.session.commit()
        log_user_activity(current_user.id, 'api_key_deleted', f'API key deleted: {api_key.key_name}')
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/create_user', methods=['POST'])
@require_permission('manage_users')
def create_user():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'user')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        # Check if email already exists (if provided)
        if email and User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Validate password strength
        is_strong, message = validate_password_strength(password)
        if not is_strong:
            return jsonify({'error': message}), 400
        
        # Create new user
        new_user = User(
            username=username,
            email=email if email else None,
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None,
            role=role,
            is_active=True
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        log_user_activity(current_user.id, 'user_created', f'Created user: {username}')
        return jsonify({'success': True, 'user_id': new_user.id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/manage_user', methods=['POST'])
@require_permission('manage_users')
def manage_user():
    try:
        data = request.get_json()
        action = data.get('action')
        user_id = data.get('user_id')
        
        if action == 'update_role':
            new_role = data.get('role')
            new_limit = data.get('daily_limit')
            
            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Prevent changing owner role
            if user.role == 'owner' and current_user.role != 'owner':
                return jsonify({'error': 'Cannot modify owner account'}), 403
            
            user.role = new_role
            if new_limit is not None:
                user.daily_message_limit = new_limit
            
            db.session.commit()
            log_user_activity(current_user.id, 'user_updated', f'Updated user: {user.username}')
            return jsonify({'success': True})
            
        elif action == 'delete_user':
            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if user.role == 'owner':
                return jsonify({'error': 'Cannot delete owner account'}), 400
            
            # Delete user and all related data
            db.session.delete(user)
            db.session.commit()
            log_user_activity(current_user.id, 'user_deleted', f'Deleted user: {user.username}')
            return jsonify({'success': True})
        
        elif action == 'reset_password':
            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Generate temporary password
            temp_password = 'TempPass123!'
            user.set_password(temp_password)
            user.must_change_password = True
            
            db.session.commit()
            log_user_activity(current_user.id, 'password_reset', f'Reset password for user: {user.username}')
            return jsonify({'success': True, 'temp_password': temp_password})
        
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_model_preference', methods=['POST'])
def save_model_preference():
    try:
        data = request.get_json()
        model = data.get('model', 'openai/gpt-3.5-turbo')
        
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id') if not current_user.is_authenticated else None
        
        if user_id:
            preference = UserModelPreference.query.filter_by(user_id=user_id).first()
            if preference:
                preference.preferred_model = model
                preference.updated_at = datetime.utcnow()
            else:
                preference = UserModelPreference(user_id=user_id, preferred_model=model)
                db.session.add(preference)
        elif session_id:
            preference = UserModelPreference.query.filter_by(session_id=session_id).first()
            if preference:
                preference.preferred_model = model
                preference.updated_at = datetime.utcnow()
            else:
                preference = UserModelPreference(session_id=session_id, preferred_model=model)
                db.session.add(preference)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_model_preference')
def get_model_preference():
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id') if not current_user.is_authenticated else None
        
        if user_id:
            preference = UserModelPreference.query.filter_by(user_id=user_id).first()
        elif session_id:
            preference = UserModelPreference.query.filter_by(session_id=session_id).first()
        else:
            preference = None
        
        model = preference.preferred_model if preference else 'openai/gpt-3.5-turbo'
        return jsonify({'model': model})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_chat_history')
def get_chat_history():
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id')
        
        if user_id:
            messages = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.created_at.desc()).limit(50).all()
        elif session_id:
            messages = ChatMessage.query.filter_by(session_id=session_id, user_id=None).order_by(ChatMessage.created_at.desc()).limit(50).all()
        else:
            messages = []
        
        message_data = []
        for msg in reversed(messages):
            message_data.append({
                'type': msg.message_type,
                'content': msg.content,
                'timestamp': msg.created_at.isoformat(),
                'file_data': msg.file_data
            })
        
        return jsonify({
            'messages': message_data,
            'messages_remaining': get_messages_remaining()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear_chat', methods=['POST'])
def clear_chat():
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = session.get('session_id')
        
        if user_id:
            ChatMessage.query.filter_by(user_id=user_id).delete()
        elif session_id:
            ChatMessage.query.filter_by(session_id=session_id, user_id=None).delete()
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_messages_remaining():
    if current_user.is_authenticated:
        if current_user.role in ['owner', 'admin']:
            return -1  # Unlimited
        return max(0, current_user.daily_message_limit - current_user.messages_used_today)
    else:
        session_id = session.get('session_id')
        if session_id:
            used = ChatMessage.query.filter_by(session_id=session_id, user_id=None).count()
            return max(0, 10 - used)
        return 10