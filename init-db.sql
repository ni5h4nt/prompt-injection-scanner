-- Initial database setup for prompt injection scanner
-- This script is run when PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create enum types
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE scan_status AS ENUM ('pending', 'processing', 'completed', 'failed');

-- Scan history table
CREATE TABLE IF NOT EXISTS scan_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash of prompt (for privacy)
    risk_score INTEGER NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_level risk_level NOT NULL,
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    flags TEXT[] DEFAULT '{}',
    threat_types TEXT[] DEFAULT '{}',
    processing_time_ms INTEGER,
    user_id VARCHAR(255),
    source VARCHAR(100),
    api_version VARCHAR(10) DEFAULT 'v1',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Stage results table (for detailed analysis)
CREATE TABLE IF NOT EXISTS stage_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES scan_history(id) ON DELETE CASCADE,
    stage_name VARCHAR(50) NOT NULL,
    risk_score INTEGER NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    flags TEXT[] DEFAULT '{}',
    processing_time_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Feedback table for continuous learning
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID REFERENCES scan_history(id) ON DELETE SET NULL,
    prompt_hash VARCHAR(64) NOT NULL,
    predicted_risk INTEGER NOT NULL,
    predicted_label VARCHAR(20) NOT NULL,
    actual_label VARCHAR(20) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    feedback_type VARCHAR(20) NOT NULL,  -- 'false_positive', 'false_negative', 'correction'
    user_id VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Pattern usage statistics
CREATE TABLE IF NOT EXISTS pattern_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_id VARCHAR(100) NOT NULL,
    pattern_name VARCHAR(255) NOT NULL,
    matches_count INTEGER DEFAULT 0,
    true_positives INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    last_matched TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    metric_unit VARCHAR(20),
    tags JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_scan_history_created_at ON scan_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_history_user_id ON scan_history(user_id);
CREATE INDEX IF NOT EXISTS idx_scan_history_risk_level ON scan_history(risk_level);
CREATE INDEX IF NOT EXISTS idx_scan_history_prompt_hash ON scan_history(prompt_hash);

CREATE INDEX IF NOT EXISTS idx_stage_results_scan_id ON stage_results(scan_id);
CREATE INDEX IF NOT EXISTS idx_stage_results_stage_name ON stage_results(stage_name);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_feedback_type ON feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_prompt_hash ON feedback(prompt_hash);

CREATE INDEX IF NOT EXISTS idx_pattern_stats_pattern_id ON pattern_stats(pattern_id);
CREATE INDEX IF NOT EXISTS idx_pattern_stats_updated_at ON pattern_stats(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_metrics_metric_name ON system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp DESC);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_scan_history_updated_at 
    BEFORE UPDATE ON scan_history 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pattern_stats_updated_at 
    BEFORE UPDATE ON pattern_stats 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert some initial data for testing
INSERT INTO system_metrics (metric_name, metric_value, metric_unit) VALUES
    ('total_scans', 0, 'count'),
    ('avg_processing_time', 0, 'ms'),
    ('false_positive_rate', 0, 'percentage')
ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO scanner_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO scanner_user;

-- Create a view for scan analytics
CREATE OR REPLACE VIEW scan_analytics AS
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total_scans,
    AVG(risk_score) as avg_risk_score,
    AVG(confidence) as avg_confidence,
    AVG(processing_time_ms) as avg_processing_time,
    COUNT(CASE WHEN risk_level = 'critical' THEN 1 END) as critical_scans,
    COUNT(CASE WHEN risk_level = 'high' THEN 1 END) as high_scans,
    COUNT(CASE WHEN risk_level = 'medium' THEN 1 END) as medium_scans,
    COUNT(CASE WHEN risk_level = 'low' THEN 1 END) as low_scans
FROM scan_history 
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;