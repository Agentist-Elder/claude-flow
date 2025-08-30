-- InciteRewrite Platform - Initial Database Migration
-- Migration: 001_initial_schema.sql
-- Created: 2024-01-15
-- Description: Create initial database schema with all tables, indexes, and functions

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text similarity and fuzzy matching
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- For query performance monitoring

-- Create custom types
CREATE TYPE user_tier_type AS ENUM ('free', 'pro', 'enterprise');
CREATE TYPE document_status_type AS ENUM ('draft', 'published', 'archived', 'deleted');
CREATE TYPE permission_level_type AS ENUM ('view', 'comment', 'edit', 'admin');
CREATE TYPE token_type_enum AS ENUM ('refresh', 'reset', 'verification');
CREATE TYPE ai_request_status_type AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled');
CREATE TYPE rewrite_type_enum AS ENUM ('improve', 'simplify', 'expand', 'summarize', 'tone_formal', 'tone_casual');
CREATE TYPE device_type_enum AS ENUM ('desktop', 'mobile', 'tablet', 'unknown');
CREATE TYPE severity_level_enum AS ENUM ('low', 'medium', 'high', 'critical');

-- ============================================================================
-- USERS SCHEMA
-- ============================================================================

-- Users table - Core user information and authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    tier user_tier_type DEFAULT 'free',
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
    address JSONB,
    preferences JSONB DEFAULT '{}',
    social_links JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User authentication tokens
CREATE TABLE user_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_type token_type_enum NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    UNIQUE(user_id, token_type) DEFERRABLE INITIALLY DEFERRED
);

-- User sessions
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    device_info JSONB DEFAULT '{}',
    location JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- API keys
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    permissions JSONB DEFAULT '[]',
    rate_limit INTEGER DEFAULT 1000,
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- User usage tracking
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
    
    UNIQUE(user_id, usage_date)
);

-- ============================================================================
-- DOCUMENTS SCHEMA
-- ============================================================================

-- Documents table - Core document information
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    content_type VARCHAR(50) DEFAULT 'text/plain' CHECK (content_type IN ('text/plain', 'text/markdown', 'text/html')),
    status document_status_type DEFAULT 'draft',
    word_count INTEGER DEFAULT 0 CHECK (word_count >= 0),
    character_count INTEGER DEFAULT 0 CHECK (character_count >= 0),
    language VARCHAR(10) DEFAULT 'en',
    reading_time INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    search_vector tsvector,
    
    CONSTRAINT title_not_empty CHECK (LENGTH(TRIM(title)) > 0)
);

-- Document versions
CREATE TABLE document_versions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    word_count INTEGER DEFAULT 0,
    character_count INTEGER DEFAULT 0,
    change_summary TEXT,
    change_type VARCHAR(20) DEFAULT 'manual' CHECK (change_type IN ('manual', 'ai_rewrite', 'collaboration', 'auto_save')),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    UNIQUE(document_id, version_number)
);

-- Document collaborators
CREATE TABLE document_collaborators (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_level permission_level_type NOT NULL DEFAULT 'view',
    invited_by INTEGER REFERENCES users(id),
    invited_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id, user_id)
);

-- Document tags
CREATE TABLE document_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#808080',
    description TEXT,
    created_by INTEGER REFERENCES users(id),
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT tag_name_format CHECK (name ~* '^[a-zA-Z0-9_-]+$'),
    CONSTRAINT color_format CHECK (color ~* '^#[0-9A-Fa-f]{6}$')
);

-- Document tag assignments
CREATE TABLE document_tag_assignments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES document_tags(id) ON DELETE CASCADE,
    assigned_by INTEGER REFERENCES users(id),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id, tag_id)
);

-- Document folders
CREATE TABLE document_folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES document_folders(id) ON DELETE CASCADE,
    path TEXT,
    level INTEGER DEFAULT 0 CHECK (level >= 0),
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT no_self_reference CHECK (id != parent_id),
    UNIQUE(user_id, name, parent_id)
);

-- Document folder assignments
CREATE TABLE document_folder_assignments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    folder_id INTEGER NOT NULL REFERENCES document_folders(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id)
);

-- AI rewrite requests
CREATE TABLE ai_rewrite_requests (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_content TEXT NOT NULL,
    rewrite_type rewrite_type_enum NOT NULL,
    parameters JSONB DEFAULT '{}',
    status ai_request_status_type DEFAULT 'pending',
    rewritten_content TEXT,
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    processing_time_ms INTEGER,
    tokens_used INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- Document activities
CREATE TABLE document_activities (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    activity_type VARCHAR(50) NOT NULL,
    description TEXT,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Real-time collaboration sessions
CREATE TABLE collaboration_sessions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    metadata JSONB DEFAULT '{}'
);

-- Document cursors
CREATE TABLE document_cursors (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES collaboration_sessions(session_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cursor_position INTEGER DEFAULT 0,
    selection_start INTEGER,
    selection_end INTEGER,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(session_id, user_id)
);

-- Document comments
CREATE TABLE document_comments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES document_comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    position_start INTEGER,
    position_end INTEGER,
    is_resolved BOOLEAN DEFAULT false,
    resolved_by INTEGER REFERENCES users(id),
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_position CHECK (position_end IS NULL OR position_end >= position_start)
);

-- ============================================================================
-- ANALYTICS SCHEMA
-- ============================================================================

-- System metrics
CREATE TABLE system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(20),
    service_name VARCHAR(100),
    instance_id VARCHAR(100),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- User analytics
CREATE TABLE user_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50),
    event_action VARCHAR(100),
    event_label VARCHAR(255),
    page_path VARCHAR(500),
    referrer VARCHAR(500),
    user_agent TEXT,
    ip_address INET,
    country_code CHAR(2),
    city VARCHAR(100),
    device_type device_type_enum,
    browser VARCHAR(50),
    operating_system VARCHAR(50),
    screen_resolution VARCHAR(20),
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    properties JSONB DEFAULT '{}'
);

-- Document analytics
CREATE TABLE document_analytics (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- API analytics
CREATE TABLE api_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
    endpoint VARCHAR(255) NOT NULL,
    http_method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,
    ip_address INET,
    user_agent TEXT,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- AI analytics
CREATE TABLE ai_analytics (
    id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES ai_rewrite_requests(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    confidence_score DECIMAL(3,2),
    rewrite_type rewrite_type_enum,
    success BOOLEAN DEFAULT false,
    error_code VARCHAR(50),
    cost_usd DECIMAL(10,6),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Error tracking
CREATE TABLE error_tracking (
    id SERIAL PRIMARY KEY,
    error_id VARCHAR(255) UNIQUE NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    error_type VARCHAR(100),
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    severity severity_level_enum DEFAULT 'medium',
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    request_id VARCHAR(255),
    endpoint VARCHAR(255),
    http_method VARCHAR(10),
    status_code INTEGER,
    user_agent TEXT,
    ip_address INET,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1,
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'
);

-- Daily metrics aggregation
CREATE TABLE daily_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_category VARCHAR(50),
    metric_value DECIMAL(15,4) NOT NULL,
    comparison_value DECIMAL(15,4),
    change_percentage DECIMAL(5,2),
    metadata JSONB DEFAULT '{}',
    
    UNIQUE(metric_date, metric_name, metric_category)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- User indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_last_login ON users(last_login DESC);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;

-- Document indexes  
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_updated_at ON documents(updated_at DESC);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);

-- Version indexes
CREATE INDEX idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX idx_document_versions_created_by ON document_versions(created_by);
CREATE INDEX idx_document_versions_created_at ON document_versions(created_at DESC);

-- Analytics indexes
CREATE INDEX idx_user_analytics_user_time ON user_analytics(user_id, event_timestamp DESC);
CREATE INDEX idx_user_analytics_event_type ON user_analytics(event_type, event_timestamp DESC);
CREATE INDEX idx_api_analytics_endpoint ON api_analytics(endpoint, requested_at DESC);
CREATE INDEX idx_system_metrics_name_time ON system_metrics(metric_name, recorded_at DESC);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Updated timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_folders_updated_at BEFORE UPDATE ON document_folders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Document search vector trigger
CREATE OR REPLACE FUNCTION update_document_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector = to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_search_vector 
    BEFORE INSERT OR UPDATE OF title, content ON documents
    FOR EACH ROW EXECUTE FUNCTION update_document_search_vector();

-- Document counts trigger
CREATE OR REPLACE FUNCTION update_document_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.content IS NOT NULL THEN
        NEW.word_count = array_length(string_to_array(regexp_replace(NEW.content, '\s+', ' ', 'g'), ' '), 1);
        NEW.character_count = LENGTH(NEW.content);
        NEW.reading_time = CEIL(NEW.word_count / 200.0);
    ELSE
        NEW.word_count = 0;
        NEW.character_count = 0;
        NEW.reading_time = 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_document_counts_trigger 
    BEFORE INSERT OR UPDATE OF content ON documents
    FOR EACH ROW EXECUTE FUNCTION update_document_counts();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active users view
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

-- User documents view
CREATE VIEW user_documents AS
SELECT 
    d.*,
    u.email as owner_email,
    u.first_name || ' ' || u.last_name as owner_name,
    COUNT(dv.id) as version_count,
    COUNT(dc.id) as collaborator_count,
    COUNT(dta.id) as tag_count
FROM documents d
JOIN users u ON d.user_id = u.id
LEFT JOIN document_versions dv ON d.id = dv.document_id
LEFT JOIN document_collaborators dc ON d.id = dc.document_id AND dc.is_active = true
LEFT JOIN document_tag_assignments dta ON d.id = dta.document_id
GROUP BY d.id, u.email, u.first_name, u.last_name;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default document tags
INSERT INTO document_tags (name, color, description, is_system) VALUES
('urgent', '#FF4444', 'Urgent priority documents', true),
('draft', '#FFA500', 'Work in progress documents', true),
('review', '#4169E1', 'Documents pending review', true),
('published', '#32CD32', 'Published documents', true),
('archived', '#808080', 'Archived documents', true);

-- Create default root folder for system use
INSERT INTO document_folders (user_id, name, description, is_system, level, path) VALUES
(1, 'System', 'System root folder', true, 0, '1');

-- ============================================================================
-- CLEANUP FUNCTIONS
-- ============================================================================

-- Cleanup expired tokens
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

-- Cleanup expired sessions
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

-- Migration completed successfully
SELECT 'Initial schema migration completed successfully' as status;