-- InciteRewrite Platform - Analytics Schema
-- This file defines the analytics and metrics tables for tracking platform usage and performance

-- System metrics table - Overall platform performance metrics
CREATE TABLE system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(20), -- ms, bytes, count, percentage, etc.
    service_name VARCHAR(100), -- Which service reported this metric
    instance_id VARCHAR(100), -- Service instance identifier
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    -- Index on time and metric name for efficient querying
    UNIQUE(metric_name, service_name, instance_id, recorded_at)
);

-- User analytics - Track user behavior and engagement
CREATE TABLE user_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL, -- login, logout, document_create, etc.
    event_category VARCHAR(50), -- authentication, document, collaboration, etc.
    event_action VARCHAR(100), -- specific action taken
    event_label VARCHAR(255), -- additional context
    page_path VARCHAR(500),
    referrer VARCHAR(500),
    user_agent TEXT,
    ip_address INET,
    country_code CHAR(2),
    city VARCHAR(100),
    device_type VARCHAR(20) CHECK (device_type IN ('desktop', 'mobile', 'tablet', 'unknown')),
    browser VARCHAR(50),
    operating_system VARCHAR(50),
    screen_resolution VARCHAR(20),
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    properties JSONB DEFAULT '{}', -- Additional event properties
    
    -- Composite index for efficient querying
    INDEX idx_user_analytics_composite (user_id, event_timestamp DESC, event_type)
);

-- Document analytics - Track document-specific metrics
CREATE TABLE document_analytics (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    metric_type VARCHAR(50) NOT NULL, -- views, edits, time_spent, ai_rewrites, etc.
    metric_value DECIMAL(15,4) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- API analytics - Track API usage and performance
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

-- AI service analytics - Track AI rewriting performance and usage
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
    rewrite_type VARCHAR(50),
    success BOOLEAN DEFAULT false,
    error_code VARCHAR(50),
    cost_usd DECIMAL(10,6), -- Cost in USD
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Performance benchmarks - Store performance test results
CREATE TABLE performance_benchmarks (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL,
    test_category VARCHAR(100), -- api, database, ai, frontend, etc.
    metric_name VARCHAR(100) NOT NULL, -- response_time, throughput, memory_usage, etc.
    baseline_value DECIMAL(15,4), -- Expected baseline value
    measured_value DECIMAL(15,4) NOT NULL, -- Actual measured value
    variance_percentage DECIMAL(5,2), -- Percentage difference from baseline
    pass_threshold DECIMAL(15,4), -- Threshold for test to pass
    test_passed BOOLEAN,
    environment VARCHAR(50) DEFAULT 'production', -- production, staging, development
    git_commit VARCHAR(40), -- Git commit hash when test was run
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Error tracking - Store application errors and exceptions
CREATE TABLE error_tracking (
    id SERIAL PRIMARY KEY,
    error_id VARCHAR(255) UNIQUE NOT NULL, -- Unique identifier for grouping similar errors
    service_name VARCHAR(100) NOT NULL,
    error_type VARCHAR(100), -- exception_type or error_category
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    severity VARCHAR(20) DEFAULT 'error' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    request_id VARCHAR(255), -- For tracing requests across services
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

-- Feature usage tracking - Track usage of specific features
CREATE TABLE feature_usage (
    id SERIAL PRIMARY KEY,
    feature_name VARCHAR(100) NOT NULL,
    feature_version VARCHAR(20),
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    usage_count INTEGER DEFAULT 1,
    first_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_time_spent_seconds INTEGER DEFAULT 0,
    success_rate DECIMAL(3,2), -- Success rate as percentage
    metadata JSONB DEFAULT '{}',
    
    -- One record per user per feature
    UNIQUE(feature_name, user_id)
);

-- A/B test tracking - Track A/B test assignments and outcomes
CREATE TABLE ab_tests (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(100) NOT NULL,
    test_description TEXT,
    variant_a_name VARCHAR(50) DEFAULT 'control',
    variant_b_name VARCHAR(50) DEFAULT 'treatment',
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN DEFAULT true,
    target_metric VARCHAR(100), -- What we're trying to optimize
    confidence_level DECIMAL(3,2) DEFAULT 0.95,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- A/B test assignments - Track which users are in which variant
CREATE TABLE ab_test_assignments (
    id SERIAL PRIMARY KEY,
    test_id INTEGER NOT NULL REFERENCES ab_tests(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    variant VARCHAR(50) NOT NULL, -- A or B
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    conversion_recorded BOOLEAN DEFAULT false,
    conversion_value DECIMAL(10,2),
    metadata JSONB DEFAULT '{}',
    
    -- One assignment per user per test
    UNIQUE(test_id, user_id)
);

-- Daily aggregated metrics for faster reporting
CREATE TABLE daily_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_category VARCHAR(50), -- users, documents, api, ai, errors, etc.
    metric_value DECIMAL(15,4) NOT NULL,
    comparison_value DECIMAL(15,4), -- Previous period for comparison
    change_percentage DECIMAL(5,2), -- Percentage change
    metadata JSONB DEFAULT '{}',
    
    -- One record per metric per day
    UNIQUE(metric_date, metric_name, metric_category)
);

-- User cohort analysis - Track user retention and behavior over time
CREATE TABLE user_cohorts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cohort_month DATE NOT NULL, -- Month when user first signed up
    period_number INTEGER NOT NULL, -- 0 for signup month, 1 for month 1, etc.
    is_active BOOLEAN DEFAULT false, -- Whether user was active in this period
    documents_created INTEGER DEFAULT 0,
    ai_rewrites_used INTEGER DEFAULT 0,
    revenue_generated DECIMAL(10,2) DEFAULT 0,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- One record per user per period
    UNIQUE(user_id, cohort_month, period_number)
);

-- Indexes for performance optimization
CREATE INDEX idx_system_metrics_name_time ON system_metrics(metric_name, recorded_at DESC);
CREATE INDEX idx_system_metrics_service ON system_metrics(service_name, recorded_at DESC);

CREATE INDEX idx_user_analytics_user_time ON user_analytics(user_id, event_timestamp DESC);
CREATE INDEX idx_user_analytics_event_type ON user_analytics(event_type, event_timestamp DESC);
CREATE INDEX idx_user_analytics_session ON user_analytics(session_id);

CREATE INDEX idx_document_analytics_doc_time ON document_analytics(document_id, recorded_at DESC);
CREATE INDEX idx_document_analytics_user_time ON document_analytics(user_id, recorded_at DESC);
CREATE INDEX idx_document_analytics_metric_type ON document_analytics(metric_type);

CREATE INDEX idx_api_analytics_user_time ON api_analytics(user_id, requested_at DESC);
CREATE INDEX idx_api_analytics_endpoint ON api_analytics(endpoint, requested_at DESC);
CREATE INDEX idx_api_analytics_status ON api_analytics(status_code, requested_at DESC);

CREATE INDEX idx_ai_analytics_user_time ON ai_analytics(user_id, recorded_at DESC);
CREATE INDEX idx_ai_analytics_model ON ai_analytics(model_name, recorded_at DESC);
CREATE INDEX idx_ai_analytics_success ON ai_analytics(success, recorded_at DESC);

CREATE INDEX idx_performance_benchmarks_name_time ON performance_benchmarks(test_name, recorded_at DESC);
CREATE INDEX idx_performance_benchmarks_category ON performance_benchmarks(test_category);

CREATE INDEX idx_error_tracking_service_time ON error_tracking(service_name, last_seen DESC);
CREATE INDEX idx_error_tracking_severity ON error_tracking(severity, last_seen DESC);
CREATE INDEX idx_error_tracking_resolved ON error_tracking(is_resolved, last_seen DESC);

CREATE INDEX idx_feature_usage_feature_time ON feature_usage(feature_name, last_used DESC);
CREATE INDEX idx_feature_usage_user ON feature_usage(user_id);

CREATE INDEX idx_ab_test_assignments_test ON ab_test_assignments(test_id);
CREATE INDEX idx_ab_test_assignments_user ON ab_test_assignments(user_id);

CREATE INDEX idx_daily_metrics_date_category ON daily_metrics(metric_date DESC, metric_category);
CREATE INDEX idx_daily_metrics_name ON daily_metrics(metric_name, metric_date DESC);

CREATE INDEX idx_user_cohorts_cohort ON user_cohorts(cohort_month, period_number);
CREATE INDEX idx_user_cohorts_user ON user_cohorts(user_id);

-- Partitioning for large tables (PostgreSQL 10+)
-- Partition user_analytics by month for better performance
-- This would be implemented based on actual data volume requirements

-- Functions for analytics calculations
CREATE OR REPLACE FUNCTION calculate_retention_rate(
    cohort_date DATE,
    period_num INTEGER
)
RETURNS DECIMAL(5,2) AS $$
DECLARE
    total_users INTEGER;
    active_users INTEGER;
BEGIN
    -- Get total users in cohort
    SELECT COUNT(DISTINCT user_id) INTO total_users
    FROM user_cohorts
    WHERE cohort_month = cohort_date AND period_number = 0;
    
    -- Get active users in specified period
    SELECT COUNT(DISTINCT user_id) INTO active_users
    FROM user_cohorts
    WHERE cohort_month = cohort_date 
      AND period_number = period_num 
      AND is_active = true;
    
    -- Calculate retention rate
    IF total_users > 0 THEN
        RETURN (active_users * 100.0) / total_users;
    ELSE
        RETURN 0;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to aggregate daily metrics
CREATE OR REPLACE FUNCTION aggregate_daily_metrics(target_date DATE)
RETURNS VOID AS $$
BEGIN
    -- Insert daily user metrics
    INSERT INTO daily_metrics (metric_date, metric_name, metric_category, metric_value)
    SELECT 
        target_date,
        'active_users',
        'users',
        COUNT(DISTINCT user_id)
    FROM user_analytics 
    WHERE event_timestamp::DATE = target_date
    ON CONFLICT (metric_date, metric_name, metric_category) 
    DO UPDATE SET metric_value = EXCLUDED.metric_value;
    
    -- Insert daily document metrics
    INSERT INTO daily_metrics (metric_date, metric_name, metric_category, metric_value)
    SELECT 
        target_date,
        'documents_created',
        'documents',
        COUNT(*)
    FROM documents 
    WHERE created_at::DATE = target_date
    ON CONFLICT (metric_date, metric_name, metric_category) 
    DO UPDATE SET metric_value = EXCLUDED.metric_value;
    
    -- Insert daily AI rewrite metrics
    INSERT INTO daily_metrics (metric_date, metric_name, metric_category, metric_value)
    SELECT 
        target_date,
        'ai_rewrites_completed',
        'ai',
        COUNT(*)
    FROM ai_rewrite_requests 
    WHERE completed_at::DATE = target_date AND status = 'completed'
    ON CONFLICT (metric_date, metric_name, metric_category) 
    DO UPDATE SET metric_value = EXCLUDED.metric_value;
END;
$$ LANGUAGE plpgsql;

-- Function to update error occurrence count
CREATE OR REPLACE FUNCTION update_error_occurrence()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if error_id already exists
    UPDATE error_tracking 
    SET 
        occurrence_count = occurrence_count + 1,
        last_seen = CURRENT_TIMESTAMP
    WHERE error_id = NEW.error_id;
    
    -- If no rows were updated, this is a new error
    IF NOT FOUND THEN
        RETURN NEW;
    ELSE
        RETURN NULL; -- Don't insert duplicate
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_error_occurrence_trigger 
    BEFORE INSERT ON error_tracking
    FOR EACH ROW EXECUTE FUNCTION update_error_occurrence();

-- Views for common analytics queries
CREATE VIEW user_engagement_summary AS
SELECT 
    u.id as user_id,
    u.email,
    u.tier,
    u.created_at as signup_date,
    COUNT(DISTINCT d.id) as documents_created,
    COUNT(DISTINCT arr.id) as ai_rewrites_used,
    MAX(ua.event_timestamp) as last_activity,
    COUNT(DISTINCT ua.session_id) as total_sessions,
    EXTRACT(DAYS FROM CURRENT_TIMESTAMP - MAX(ua.event_timestamp)) as days_since_last_activity
FROM users u
LEFT JOIN documents d ON u.id = d.user_id
LEFT JOIN ai_rewrite_requests arr ON u.id = arr.user_id
LEFT JOIN user_analytics ua ON u.id = ua.user_id
GROUP BY u.id, u.email, u.tier, u.created_at;

CREATE VIEW system_health_dashboard AS
SELECT 
    sm.service_name,
    AVG(CASE WHEN sm.metric_name = 'response_time_ms' THEN sm.metric_value END) as avg_response_time,
    AVG(CASE WHEN sm.metric_name = 'cpu_usage_percent' THEN sm.metric_value END) as avg_cpu_usage,
    AVG(CASE WHEN sm.metric_name = 'memory_usage_percent' THEN sm.metric_value END) as avg_memory_usage,
    COUNT(et.id) as error_count,
    MAX(sm.recorded_at) as last_metric_recorded
FROM system_metrics sm
LEFT JOIN error_tracking et ON sm.service_name = et.service_name 
    AND et.first_seen >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
WHERE sm.recorded_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
GROUP BY sm.service_name;

-- Comments on tables and columns
COMMENT ON TABLE system_metrics IS 'System-wide performance and health metrics';
COMMENT ON TABLE user_analytics IS 'User behavior tracking and engagement metrics';
COMMENT ON TABLE document_analytics IS 'Document-specific usage and performance metrics';
COMMENT ON TABLE api_analytics IS 'API usage, performance, and error tracking';
COMMENT ON TABLE ai_analytics IS 'AI service performance and cost tracking';
COMMENT ON TABLE performance_benchmarks IS 'Performance test results and benchmarking data';
COMMENT ON TABLE error_tracking IS 'Application error tracking and monitoring';
COMMENT ON TABLE feature_usage IS 'Feature adoption and usage tracking';
COMMENT ON TABLE ab_tests IS 'A/B testing framework for feature experiments';
COMMENT ON TABLE daily_metrics IS 'Aggregated daily metrics for faster reporting';
COMMENT ON TABLE user_cohorts IS 'User cohort analysis for retention tracking';

COMMENT ON COLUMN ai_analytics.cost_usd IS 'Actual cost in USD for AI processing';
COMMENT ON COLUMN performance_benchmarks.variance_percentage IS 'Percentage difference from baseline performance';
COMMENT ON COLUMN error_tracking.occurrence_count IS 'Number of times this error has occurred';