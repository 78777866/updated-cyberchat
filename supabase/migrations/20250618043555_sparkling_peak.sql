/*
  # Complete Database Schema with Performance Indexes

  1. New Tables
    - `users` - User accounts and authentication
    - `oauth` - OAuth token storage for Replit Auth
    - `api_keys` - Encrypted API keys for AI services
    - `chat_messages` - Chat conversation history
    - `system_settings` - Application configuration
    - `user_model_preferences` - User AI model preferences

  2. Security
    - Enable RLS on all tables
    - Add appropriate policies for data access
    - Secure foreign key relationships

  3. Performance
    - Comprehensive indexing strategy
    - Optimized query patterns
    - Efficient data retrieval
*/

-- Create users table
CREATE TABLE IF NOT EXISTS users (
  id text PRIMARY KEY,
  email text UNIQUE,
  first_name text,
  last_name text,
  profile_image_url text,
  role text DEFAULT 'basic',
  is_creator boolean DEFAULT false,
  daily_message_limit integer DEFAULT 50,
  messages_used_today integer DEFAULT 0,
  last_message_date date DEFAULT CURRENT_DATE,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Create OAuth table for Replit Auth
CREATE TABLE IF NOT EXISTS oauth (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text REFERENCES users(id) ON DELETE CASCADE,
  browser_session_key text NOT NULL,
  provider text NOT NULL,
  token jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT uq_user_browser_session_key_provider UNIQUE (user_id, browser_session_key, provider)
);

-- Create API keys table
CREATE TABLE IF NOT EXISTS api_keys (
  id serial PRIMARY KEY,
  user_id text REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  service text NOT NULL,
  key_name text NOT NULL,
  encrypted_key text NOT NULL,
  is_active boolean DEFAULT true,
  is_default boolean DEFAULT false,
  last_used timestamptz,
  created_at timestamptz DEFAULT now()
);

-- Create chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
  id serial PRIMARY KEY,
  user_id text REFERENCES users(id) ON DELETE CASCADE,
  session_id text NOT NULL,
  message_type text NOT NULL CHECK (message_type IN ('user', 'assistant')),
  content text NOT NULL,
  file_data jsonb,
  created_at timestamptz DEFAULT now()
);

-- Create system settings table
CREATE TABLE IF NOT EXISTS system_settings (
  id serial PRIMARY KEY,
  setting_key text UNIQUE NOT NULL,
  setting_value text NOT NULL,
  updated_by text REFERENCES users(id),
  updated_at timestamptz DEFAULT now()
);

-- Create user model preferences table
CREATE TABLE IF NOT EXISTS user_model_preferences (
  id serial PRIMARY KEY,
  user_id text REFERENCES users(id) ON DELETE CASCADE,
  session_id text,
  preferred_model text DEFAULT 'openai/gpt-3.5-turbo',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_model_preferences ENABLE ROW LEVEL SECURITY;

-- RLS Policies for users table
CREATE POLICY "Users can read own data"
  ON users
  FOR SELECT
  TO authenticated
  USING (auth.uid()::text = id);

CREATE POLICY "Users can update own data"
  ON users
  FOR UPDATE
  TO authenticated
  USING (auth.uid()::text = id);

-- RLS Policies for oauth table
CREATE POLICY "Users can manage own oauth tokens"
  ON oauth
  FOR ALL
  TO authenticated
  USING (auth.uid()::text = user_id);

-- RLS Policies for api_keys table
CREATE POLICY "Users can manage own api keys"
  ON api_keys
  FOR ALL
  TO authenticated
  USING (auth.uid()::text = user_id);

-- RLS Policies for chat_messages table
CREATE POLICY "Users can read own messages"
  ON chat_messages
  FOR SELECT
  TO authenticated
  USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own messages"
  ON chat_messages
  FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Anonymous users can read own session messages"
  ON chat_messages
  FOR SELECT
  TO anon
  USING (user_id IS NULL);

CREATE POLICY "Anonymous users can insert session messages"
  ON chat_messages
  FOR INSERT
  TO anon
  WITH CHECK (user_id IS NULL);

-- RLS Policies for system_settings table
CREATE POLICY "Only creators can manage system settings"
  ON system_settings
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users 
      WHERE id = auth.uid()::text 
      AND is_creator = true
    )
  );

-- RLS Policies for user_model_preferences table
CREATE POLICY "Users can manage own preferences"
  ON user_model_preferences
  FOR ALL
  TO authenticated
  USING (auth.uid()::text = user_id);

CREATE POLICY "Anonymous users can manage session preferences"
  ON user_model_preferences
  FOR ALL
  TO anon
  USING (user_id IS NULL);

-- Performance Indexes

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_creator ON users(is_creator);
CREATE INDEX IF NOT EXISTS idx_users_last_message_date ON users(last_message_date);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- OAuth table indexes
CREATE INDEX IF NOT EXISTS idx_oauth_user_id ON oauth(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_provider ON oauth(provider);
CREATE INDEX IF NOT EXISTS idx_oauth_session_key ON oauth(browser_session_key);

-- API keys table indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_service ON api_keys(service);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_service ON api_keys(user_id, service);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_api_keys_default ON api_keys(is_default);
CREATE INDEX IF NOT EXISTS idx_api_keys_last_used ON api_keys(last_used);

-- Chat messages table indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_session ON chat_messages(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_type ON chat_messages(message_type);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created ON chat_messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON chat_messages(session_id, created_at);

-- System settings table indexes
CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(setting_key);
CREATE INDEX IF NOT EXISTS idx_system_settings_updated_at ON system_settings(updated_at);

-- User model preferences table indexes
CREATE INDEX IF NOT EXISTS idx_user_model_pref_user_id ON user_model_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_model_pref_session_id ON user_model_preferences(session_id);
CREATE INDEX IF NOT EXISTS idx_user_model_pref_updated ON user_model_preferences(updated_at);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_type_created ON chat_messages(user_id, message_type, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_type_created ON chat_messages(session_id, message_type, created_at);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_active_service ON api_keys(user_id, is_active, service);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic updated_at updates
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_oauth_updated_at 
    BEFORE UPDATE ON oauth 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_settings_updated_at 
    BEFORE UPDATE ON system_settings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_model_preferences_updated_at 
    BEFORE UPDATE ON user_model_preferences 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();