-- Add database indexes for performance optimization

-- Chat messages indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_session ON chat_messages(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_type ON chat_messages(message_type);

-- API keys indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_user_service ON api_keys(user_id, service);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_api_keys_last_used ON api_keys(last_used);

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_creator ON users(is_creator);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_last_message_date ON users(last_message_date);

-- User model preferences indexes
CREATE INDEX IF NOT EXISTS idx_user_model_pref_user_id ON user_model_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_model_pref_session_id ON user_model_preferences(session_id);

-- OAuth indexes
CREATE INDEX IF NOT EXISTS idx_oauth_user_id ON oauth(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_provider ON oauth(provider);

-- System settings indexes
CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(setting_key);