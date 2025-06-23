-- Zapier Integration Tables Migration
-- Run this script in your Supabase SQL editor

-- Create ENUM types
CREATE TYPE objective_status AS ENUM ('active', 'completed', 'on_hold', 'cancelled');
CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE employee_status AS ENUM ('active', 'inactive', 'on_leave', 'terminated');

-- Social Media Metrics Table
CREATE TABLE IF NOT EXISTS social_media_metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    platform VARCHAR(50) NOT NULL,
    views INTEGER DEFAULT 0,
    engagement DECIMAL(5,2) DEFAULT 0.0,
    reach INTEGER,
    impressions INTEGER,
    clicks INTEGER,
    shares INTEGER,
    comments INTEGER,
    likes INTEGER,
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Indexes for social_media_metrics
CREATE INDEX idx_social_media_platform ON social_media_metrics(platform);
CREATE INDEX idx_social_media_timestamp ON social_media_metrics(timestamp);
CREATE INDEX idx_social_media_platform_timestamp ON social_media_metrics(platform, timestamp);

-- User Feedback Table
CREATE TABLE IF NOT EXISTS user_feedback (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    csat_score INTEGER NOT NULL CHECK (csat_score >= 1 AND csat_score <= 5),
    feedback_text TEXT,
    user_id VARCHAR(255),
    user_email VARCHAR(255),
    feedback_category VARCHAR(100),
    sentiment VARCHAR(50),
    product_area VARCHAR(100),
    resolution_status VARCHAR(50) DEFAULT 'pending',
    resolution_notes TEXT,
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Indexes for user_feedback
CREATE INDEX idx_feedback_user ON user_feedback(user_id);
CREATE INDEX idx_feedback_timestamp ON user_feedback(timestamp);
CREATE INDEX idx_feedback_score_timestamp ON user_feedback(csat_score, timestamp);

-- Objectives Table
CREATE TABLE IF NOT EXISTS objectives (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status objective_status DEFAULT 'active' NOT NULL,
    priority priority_level DEFAULT 'medium',
    owner VARCHAR(255),
    team VARCHAR(100),
    due_date TIMESTAMP WITH TIME ZONE,
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    key_results JSONB,
    milestones JSONB,
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for objectives
CREATE INDEX idx_objectives_status ON objectives(status);

-- Wins Table
CREATE TABLE IF NOT EXISTS wins (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) DEFAULT 'general',
    impact VARCHAR(50) DEFAULT 'medium',
    ai_generated BOOLEAN DEFAULT TRUE,
    ai_prompt TEXT,
    team_members JSONB,
    metrics JSONB,
    related_objective_id UUID REFERENCES objectives(id),
    visibility VARCHAR(50) DEFAULT 'public',
    tags JSONB,
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Indexes for wins
CREATE INDEX idx_wins_timestamp ON wins(timestamp);

-- Analytics Table
CREATE TABLE IF NOT EXISTS analytics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    metric_value JSONB NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    source VARCHAR(100) DEFAULT 'zapier',
    dimension VARCHAR(100),
    dimension_value VARCHAR(255),
    comparison_period VARCHAR(50),
    comparison_value JSONB,
    target_value JSONB,
    tags JSONB,
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Indexes for analytics
CREATE INDEX idx_analytics_category ON analytics(category);
CREATE INDEX idx_analytics_metric ON analytics(metric_name);
CREATE INDEX idx_analytics_category_metric ON analytics(category, metric_name);
CREATE INDEX idx_analytics_timestamp ON analytics(timestamp);

-- Form Submissions Table
CREATE TABLE IF NOT EXISTS form_submissions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    form_id VARCHAR(255) NOT NULL,
    form_name VARCHAR(255) NOT NULL,
    form_type VARCHAR(100) DEFAULT 'general',
    respondent_email VARCHAR(255),
    respondent_name VARCHAR(255),
    responses JSONB NOT NULL,
    score DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'new',
    assigned_to VARCHAR(255),
    notes TEXT,
    tags JSONB,
    metadata JSONB,
    submission_timestamp TIMESTAMP WITH TIME ZONE,
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Indexes for form_submissions
CREATE INDEX idx_form_id ON form_submissions(form_id);
CREATE INDEX idx_form_type_status ON form_submissions(form_type, status);

-- Employees Table
CREATE TABLE IF NOT EXISTS employees (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    employee_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    department VARCHAR(100),
    title VARCHAR(255),
    phone VARCHAR(50),
    location VARCHAR(255),
    manager VARCHAR(255),
    manager_id VARCHAR(100),
    status employee_status DEFAULT 'active' NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    skills JSONB,
    certifications JSONB,
    emergency_contact JSONB,
    custom_fields JSONB,
    profile_image_url VARCHAR(500),
    slack_user_id VARCHAR(100),
    github_username VARCHAR(100),
    zap_run_id VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for employees
CREATE INDEX idx_employees_email ON employees(email);
CREATE INDEX idx_employees_department ON employees(department);
CREATE INDEX idx_employee_dept_status ON employees(department, status);
CREATE INDEX idx_employees_employee_id ON employees(employee_id);

-- Create update trigger for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to tables with updated_at
CREATE TRIGGER update_objectives_updated_at BEFORE UPDATE ON objectives
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_employees_updated_at BEFORE UPDATE ON employees
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust based on your needs)
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Add RLS policies if needed (example)
-- ALTER TABLE social_media_metrics ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_feedback ENABLE ROW LEVEL SECURITY;
-- etc...