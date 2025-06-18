from datetime import datetime
from app import db
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    
    # User role and limits
    role = db.Column(db.String, default='basic')  # basic, premium, vip, creator
    is_creator = db.Column(db.Boolean, default=False)
    daily_message_limit = db.Column(db.Integer, default=50)
    messages_used_today = db.Column(db.Integer, default=0)
    last_message_date = db.Column(db.Date, default=datetime.utcnow().date)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_keys = db.relationship('APIKey', backref='user', lazy=True, cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def get_display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.email:
            return self.email.split('@')[0]
        return f"User {self.id[:8]}"
    
    def can_send_message(self):
        today = datetime.utcnow().date()
        if self.last_message_date != today:
            self.messages_used_today = 0
            self.last_message_date = today
            db.session.commit()
        
        if self.role == 'vip' or self.is_creator:
            return True
        return self.messages_used_today < self.daily_message_limit
    
    def increment_message_count(self):
        today = datetime.utcnow().date()
        if self.last_message_date != today:
            self.messages_used_today = 0
            self.last_message_date = today
        
        self.messages_used_today += 1
        db.session.commit()

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)

    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    service = db.Column(db.String, nullable=False)  # 'openrouter' or 'google_ai'
    key_name = db.Column(db.String, nullable=False)
    encrypted_key = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    last_used = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_masked_key(self):
        return f"{'*' * 20}{self.encrypted_key[-4:]}" if len(self.encrypted_key) > 4 else "*" * 24

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String, nullable=False)  # For anonymous users
    message_type = db.Column(db.String, nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    file_data = db.Column(db.JSON)  # Store file metadata if message includes files
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String, unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    updated_by = db.Column(db.String, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserModelPreference(db.Model):
    __tablename__ = 'user_model_preferences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)  # None for anonymous users
    session_id = db.Column(db.String, nullable=True)  # For anonymous users
    preferred_model = db.Column(db.String, default='openai/gpt-3.5-turbo')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
