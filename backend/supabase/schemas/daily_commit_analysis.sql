-- Daily Commit Analysis Table
-- Stores aggregated daily analysis of all commits for a user
CREATE TABLE IF NOT EXISTS daily_commit_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    total_estimated_hours DECIMAL(4,2) NOT NULL,
    commit_count INTEGER NOT NULL DEFAULT 0,
    daily_report_id UUID REFERENCES daily_reports(id) ON DELETE SET NULL,
    analysis_type VARCHAR(20) NOT NULL CHECK (analysis_type IN ('with_report', 'automatic')),
    
    -- AI Analysis Results
    ai_analysis JSONB NOT NULL DEFAULT '{}',
    complexity_score INTEGER CHECK (complexity_score >= 1 AND complexity_score <= 10),
    seniority_score INTEGER CHECK (seniority_score >= 1 AND seniority_score <= 10),
    
    -- Metadata
    repositories_analyzed TEXT[] DEFAULT '{}',
    total_lines_added INTEGER DEFAULT 0,
    total_lines_deleted INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one analysis per user per day
    CONSTRAINT unique_user_date UNIQUE (user_id, analysis_date)
);

-- Create indexes for common queries
CREATE INDEX idx_daily_commit_analysis_user_date ON daily_commit_analysis(user_id, analysis_date DESC);
CREATE INDEX idx_daily_commit_analysis_date ON daily_commit_analysis(analysis_date DESC);
CREATE INDEX idx_daily_commit_analysis_daily_report ON daily_commit_analysis(daily_report_id);

-- Add RLS policies
ALTER TABLE daily_commit_analysis ENABLE ROW LEVEL SECURITY;

-- Users can read their own analysis
CREATE POLICY "Users can read own daily analysis" ON daily_commit_analysis
    FOR SELECT
    USING (auth.uid() = user_id);

-- Service role can do everything
CREATE POLICY "Service role has full access" ON daily_commit_analysis
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Add updated_at trigger
CREATE TRIGGER update_daily_commit_analysis_updated_at
    BEFORE UPDATE ON daily_commit_analysis
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add column to commits table to track which daily analysis it belongs to
ALTER TABLE commits ADD COLUMN IF NOT EXISTS daily_analysis_id UUID REFERENCES daily_commit_analysis(id) ON DELETE SET NULL;
CREATE INDEX idx_commits_daily_analysis ON commits(daily_analysis_id);