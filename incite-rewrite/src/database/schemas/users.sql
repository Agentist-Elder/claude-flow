-- InciteRewrite Platform - Users Schema
-- This file defines the core user management tables and related structures

-- Users table - Core user information and authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    tier VARCHAR(20) DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    email_verified BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    timezone VARCHAR(50) DEFAULT 'UTC',
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT email_format_check CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT name_length_check CHECK (LENGTH(first_name) >= 1 AND LENGTH(last_name) >= 1)
);

-- User profiles table - Extended user information
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bio TEXT,
    avatar_url VARCHAR(500),
    website VARCHAR(255),
    company VARCHAR(255),
    job_title VARCHAR(255),
    phone VARCHAR(20),
    address JSONB, -- Flexible address structure
    preferences JSONB DEFAULT '{}', -- UI preferences, notification settings, etc.
    social_links JSONB DEFAULT '{}', -- Social media links
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User authentication tokens for JWT refresh and session management
CREATE TABLE user_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_type VARCHAR(20) NOT NULL CHECK (token_type IN ('refresh', 'reset', 'verification')),
    token_hash VARCHAR(255) NOT NULL, -- SHA-256 hash of the actual token
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    -- Ensure only one active refresh token per user
    UNIQUE(user_id, token_type) DEFERRABLE INITIALLY DEFERRED
);

-- User sessions for tracking active sessions and security
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    device_info JSONB DEFAULT '{}',
    location JSONB DEFAULT '{}', -- Geolocation data
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- API keys for programmatic access
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, -- User-friendly name for the key
    key_hash VARCHAR(255) NOT NULL UNIQUE, -- SHA-256 hash of the actual key
    key_prefix VARCHAR(20) NOT NULL, -- First few characters for identification
    permissions JSONB DEFAULT '[]', -- Array of permission strings
    rate_limit INTEGER DEFAULT 1000, -- Requests per hour
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- User usage tracking for rate limiting and analytics
CREATE TABLE user_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    api_requests INTEGER DEFAULT 0,
    documents_created INTEGER DEFAULT 0,
    documents_rewritten INTEGER DEFAULT 0,
    storage_used_bytes BIGINT DEFAULT 0,
    ai_tokens_consumed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- One record per user per day
    UNIQUE(user_id, usage_date)
);

-- Indexes for performance optimization
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_last_login ON users(last_login DESC);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;

CREATE INDEX idx_user_tokens_user_id ON user_tokens(user_id);
CREATE INDEX idx_user_tokens_type_expires ON user_tokens(token_type, expires_at);
CREATE INDEX idx_user_tokens_hash ON user_tokens(token_hash);

CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX idx_user_sessions_active ON user_sessions(is_active, last_activity);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;

CREATE INDEX idx_user_usage_user_date ON user_usage(user_id, usage_date);
CREATE INDEX idx_user_usage_date ON user_usage(usage_date);

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_usage_updated_at BEFORE UPDATE ON user_usage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to clean up expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions 
    WHERE expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Views for common queries
CREATE VIEW active_users AS
SELECT 
    u.id,
    u.email,
    u.first_name,
    u.last_name,
    u.tier,
    u.created_at,
    u.last_login,
    CASE 
        WHEN u.last_login > (CURRENT_TIMESTAMP - INTERVAL '30 days') THEN 'active'
        WHEN u.last_login > (CURRENT_TIMESTAMP - INTERVAL '90 days') THEN 'inactive'
        ELSE 'dormant'
    END as activity_status
FROM users u
WHERE u.is_active = true;

-- Comment on tables and columns
COMMENT ON TABLE users IS 'Core user information and authentication data';
COMMENT ON COLUMN users.metadata IS 'Flexible JSON storage for additional user attributes';
COMMENT ON COLUMN users.tier IS 'User subscription tier: free, pro, enterprise';

COMMENT ON TABLE user_profiles IS 'Extended user profile information and preferences';
COMMENT ON COLUMN user_profiles.preferences IS 'User UI preferences, notification settings, etc.';

COMMENT ON TABLE user_tokens IS 'Authentication tokens for JWT refresh and password reset';
COMMENT ON COLUMN user_tokens.token_hash IS 'SHA-256 hash of the actual token for security';

COMMENT ON TABLE user_sessions IS 'Active user sessions for security and analytics';
COMMENT ON COLUMN user_sessions.device_info IS 'Device fingerprinting data for security';

COMMENT ON TABLE api_keys IS 'API keys for programmatic access to the platform';
COMMENT ON COLUMN api_keys.permissions IS 'Array of permission strings for fine-grained access control';

COMMENT ON TABLE user_usage IS 'Daily usage tracking for rate limiting and billing';