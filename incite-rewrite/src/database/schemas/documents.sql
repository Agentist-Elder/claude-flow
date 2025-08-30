-- InciteRewrite Platform - Documents Schema
-- This file defines the document management tables and related structures

-- Documents table - Core document information
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    content_type VARCHAR(50) DEFAULT 'text/plain' CHECK (content_type IN ('text/plain', 'text/markdown', 'text/html')),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived', 'deleted')),
    word_count INTEGER DEFAULT 0 CHECK (word_count >= 0),
    character_count INTEGER DEFAULT 0 CHECK (character_count >= 0),
    language VARCHAR(10) DEFAULT 'en',
    reading_time INTEGER DEFAULT 0, -- Estimated reading time in minutes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    search_vector tsvector, -- Full-text search index
    
    -- Constraints
    CONSTRAINT title_not_empty CHECK (LENGTH(TRIM(title)) > 0)
);

-- Document versions table - Version control for documents
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
    
    -- Ensure version numbers are sequential per document
    UNIQUE(document_id, version_number)
);

-- Document collaborators - Users who can edit/view documents
CREATE TABLE document_collaborators (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_level VARCHAR(20) NOT NULL DEFAULT 'view' CHECK (permission_level IN ('view', 'comment', 'edit', 'admin')),
    invited_by INTEGER REFERENCES users(id),
    invited_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- One collaboration record per user per document
    UNIQUE(document_id, user_id)
);

-- Document tags for organization and filtering
CREATE TABLE document_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#808080', -- Hex color code
    description TEXT,
    created_by INTEGER REFERENCES users(id),
    is_system BOOLEAN DEFAULT false, -- System tags vs user-created tags
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT tag_name_format CHECK (name ~* '^[a-zA-Z0-9_-]+$'),
    CONSTRAINT color_format CHECK (color ~* '^#[0-9A-Fa-f]{6}$')
);

-- Many-to-many relationship between documents and tags
CREATE TABLE document_tag_assignments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES document_tags(id) ON DELETE CASCADE,
    assigned_by INTEGER REFERENCES users(id),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate tag assignments
    UNIQUE(document_id, tag_id)
);

-- Document folders for hierarchical organization
CREATE TABLE document_folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES document_folders(id) ON DELETE CASCADE,
    path TEXT, -- Materialized path for efficient queries
    level INTEGER DEFAULT 0 CHECK (level >= 0),
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent circular references
    CONSTRAINT no_self_reference CHECK (id != parent_id),
    -- Unique folder names per user and parent
    UNIQUE(user_id, name, parent_id)
);

-- Document folder assignments
CREATE TABLE document_folder_assignments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    folder_id INTEGER NOT NULL REFERENCES document_folders(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- One folder per document
    UNIQUE(document_id)
);

-- AI rewrite requests and results
CREATE TABLE ai_rewrite_requests (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_content TEXT NOT NULL,
    rewrite_type VARCHAR(50) NOT NULL CHECK (rewrite_type IN ('improve', 'simplify', 'expand', 'summarize', 'tone_formal', 'tone_casual')),
    parameters JSONB DEFAULT '{}', -- AI model parameters
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    rewritten_content TEXT,
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    processing_time_ms INTEGER,
    tokens_used INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- Document activities log for audit trail
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

-- Active document cursors for real-time collaboration
CREATE TABLE document_cursors (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES collaboration_sessions(session_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cursor_position INTEGER DEFAULT 0,
    selection_start INTEGER,
    selection_end INTEGER,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- One cursor per user per session
    UNIQUE(session_id, user_id)
);

-- Document comments for collaboration feedback
CREATE TABLE document_comments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES document_comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    position_start INTEGER, -- Character position in document
    position_end INTEGER,
    is_resolved BOOLEAN DEFAULT false,
    resolved_by INTEGER REFERENCES users(id),
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure position_end >= position_start
    CONSTRAINT valid_position CHECK (position_end IS NULL OR position_end >= position_start)
);

-- Indexes for performance optimization
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_updated_at ON documents(updated_at DESC);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_documents_word_count ON documents(word_count);
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);

CREATE INDEX idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX idx_document_versions_created_by ON document_versions(created_by);
CREATE INDEX idx_document_versions_created_at ON document_versions(created_at DESC);

CREATE INDEX idx_document_collaborators_document_id ON document_collaborators(document_id);
CREATE INDEX idx_document_collaborators_user_id ON document_collaborators(user_id);
CREATE INDEX idx_document_collaborators_permission ON document_collaborators(permission_level);

CREATE INDEX idx_document_tags_name ON document_tags(name);
CREATE INDEX idx_document_tag_assignments_document ON document_tag_assignments(document_id);
CREATE INDEX idx_document_tag_assignments_tag ON document_tag_assignments(tag_id);

CREATE INDEX idx_document_folders_user_id ON document_folders(user_id);
CREATE INDEX idx_document_folders_parent_id ON document_folders(parent_id);
CREATE INDEX idx_document_folders_path ON document_folders(path);

CREATE INDEX idx_ai_rewrite_requests_document_id ON ai_rewrite_requests(document_id);
CREATE INDEX idx_ai_rewrite_requests_user_id ON ai_rewrite_requests(user_id);
CREATE INDEX idx_ai_rewrite_requests_status ON ai_rewrite_requests(status);
CREATE INDEX idx_ai_rewrite_requests_created_at ON ai_rewrite_requests(created_at DESC);

CREATE INDEX idx_document_activities_document_id ON document_activities(document_id);
CREATE INDEX idx_document_activities_user_id ON document_activities(user_id);
CREATE INDEX idx_document_activities_created_at ON document_activities(created_at DESC);

CREATE INDEX idx_collaboration_sessions_document_id ON collaboration_sessions(document_id);
CREATE INDEX idx_document_cursors_session_id ON document_cursors(session_id);
CREATE INDEX idx_document_comments_document_id ON document_comments(document_id);

-- Triggers for updated_at timestamps
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_folders_updated_at BEFORE UPDATE ON document_folders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_comments_updated_at BEFORE UPDATE ON document_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger to update search vector when content changes
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

-- Trigger to update word and character counts
CREATE OR REPLACE FUNCTION update_document_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.content IS NOT NULL THEN
        NEW.word_count = array_length(string_to_array(regexp_replace(NEW.content, '\s+', ' ', 'g'), ' '), 1);
        NEW.character_count = LENGTH(NEW.content);
        NEW.reading_time = CEIL(NEW.word_count / 200.0); -- Assume 200 words per minute
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

-- Trigger to create document activity log
CREATE OR REPLACE FUNCTION log_document_activity()
RETURNS TRIGGER AS $$
DECLARE
    activity_description TEXT;
    old_vals JSONB;
    new_vals JSONB;
BEGIN
    -- Determine activity type and description
    IF TG_OP = 'INSERT' THEN
        activity_description = 'Document created';
        new_vals = to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        activity_description = 'Document updated';
        old_vals = to_jsonb(OLD);
        new_vals = to_jsonb(NEW);
    ELSIF TG_OP = 'DELETE' THEN
        activity_description = 'Document deleted';
        old_vals = to_jsonb(OLD);
    END IF;
    
    -- Insert activity log
    INSERT INTO document_activities (
        document_id,
        user_id,
        activity_type,
        description,
        old_values,
        new_values
    ) VALUES (
        COALESCE(NEW.id, OLD.id),
        COALESCE(NEW.user_id, OLD.user_id),
        TG_OP,
        activity_description,
        old_vals,
        new_vals
    );
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER document_activity_log 
    AFTER INSERT OR UPDATE OR DELETE ON documents
    FOR EACH ROW EXECUTE FUNCTION log_document_activity();

-- Function to update folder paths when hierarchy changes
CREATE OR REPLACE FUNCTION update_folder_paths()
RETURNS TRIGGER AS $$
DECLARE
    new_path TEXT;
    parent_path TEXT;
BEGIN
    -- Calculate the new path
    IF NEW.parent_id IS NULL THEN
        NEW.path = NEW.id::TEXT;
        NEW.level = 0;
    ELSE
        -- Get parent path and level
        SELECT path, level INTO parent_path, NEW.level 
        FROM document_folders 
        WHERE id = NEW.parent_id;
        
        NEW.path = parent_path || '.' || NEW.id::TEXT;
        NEW.level = NEW.level + 1;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_folder_paths_trigger 
    BEFORE INSERT OR UPDATE OF parent_id ON document_folders
    FOR EACH ROW EXECUTE FUNCTION update_folder_paths();

-- Views for common queries
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

CREATE VIEW document_collaboration_overview AS
SELECT 
    d.id as document_id,
    d.title,
    d.user_id as owner_id,
    ARRAY_AGG(DISTINCT dc.user_id) as collaborator_ids,
    ARRAY_AGG(DISTINCT dc.permission_level) as permission_levels,
    COUNT(DISTINCT dc.user_id) as total_collaborators,
    MAX(dc.invited_at) as last_collaboration_invite
FROM documents d
LEFT JOIN document_collaborators dc ON d.id = dc.document_id AND dc.is_active = true
GROUP BY d.id, d.title, d.user_id;

-- Comments on tables and columns
COMMENT ON TABLE documents IS 'Core document storage with full-text search capabilities';
COMMENT ON COLUMN documents.search_vector IS 'Automatically generated full-text search index';
COMMENT ON COLUMN documents.reading_time IS 'Estimated reading time in minutes based on 200 words/minute';

COMMENT ON TABLE document_versions IS 'Version control system for document changes';
COMMENT ON COLUMN document_versions.change_type IS 'Type of change: manual, ai_rewrite, collaboration, auto_save';

COMMENT ON TABLE document_collaborators IS 'Users who can access and edit documents';
COMMENT ON COLUMN document_collaborators.permission_level IS 'Access level: view, comment, edit, admin';

COMMENT ON TABLE ai_rewrite_requests IS 'AI-powered content rewriting requests and results';
COMMENT ON COLUMN ai_rewrite_requests.confidence_score IS 'AI confidence score between 0 and 1';

COMMENT ON TABLE document_activities IS 'Audit trail for all document changes and activities';

COMMENT ON TABLE collaboration_sessions IS 'Real-time collaboration session management';

COMMENT ON TABLE document_cursors IS 'Real-time cursor positions for collaborative editing';