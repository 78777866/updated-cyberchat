import os
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import current_user
from werkzeug.utils import secure_filename

from app import app, db
from models import User, APIKey, ChatMessage, SystemSettings
from replit_auth import require_login, make_replit_blueprint
from services.ai_service import AIService
from services.file_service import FileService
from services.search_service import SearchService
from services.encryption_service import EncryptionService

# Register auth blueprint
app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

# Make session permanent
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('index.html')

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
            return redirect(url_for('index'))
    
    return render_template('chat.html')

@app.route('/settings')
@require_login
def settings():
    if not current_user.is_creator:
        flash('Access denied. Creator privileges required.', 'error')
        return redirect(url_for('chat'))
    
    api_keys = APIKey.query.filter_by(user_id=current_user.id).all()
    users = User.query.all()
    return render_template('settings.html', api_keys=api_keys, users=users)

@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
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
        response = ai_service.get_chat_response(message, user_id or session_id)
        
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
@require_login
def save_api_key():
    if not current_user.is_creator:
        return jsonify({'error': 'Access denied'}), 403
    
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
        return jsonify({'success': True})
        
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
        if current_user.role == 'vip' or current_user.is_creator:
            return -1  # Unlimited
        return max(0, current_user.daily_message_limit - current_user.messages_used_today)
    else:
        session_id = session.get('session_id')
        if session_id:
            used = ChatMessage.query.filter_by(session_id=session_id, user_id=None).count()
            return max(0, 10 - used)
        return 10
