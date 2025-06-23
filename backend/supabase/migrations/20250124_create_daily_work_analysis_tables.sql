-- Migration: Create Daily Work Analysis Tables
-- Description: Creates tables for the unified daily analysis system that aggregates work from multiple sources
-- Date: 2025-01-24

-- Create daily_work_analyses table
CREATE TABLE IF NOT EXISTS daily_work_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    analysis_date DATE NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Analysis results
    total_work_items INTEGER DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    total_tickets INTEGER DEFAULT 0,
    total_prs INTEGER DEFAULT 0,
    
    -- Aggregated metrics
    total_loc_added INTEGER DEFAULT 0,
    total_loc_removed INTEGER DEFAULT 0,
    total_files_changed INTEGER DEFAULT 0,
    
    -- Time tracking
    total_estimated_hours FLOAT DEFAULT 0.0,
    
    -- AI-generated summaries
    daily_summary TEXT,
    key_achievements JSONB,
    technical_highlights JSONB,
    
    -- Work item details
    work_items JSONB,
    
    -- Deduplication tracking
    deduplication_results JSONB,
    
    -- Processing status
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_error TEXT,
    last_processed_at TIMESTAMPTZ,
    
    -- Source tracking
    data_sources JSONB,
    
    -- Ensure one analysis per user per day
    CONSTRAINT unique_user_date UNIQUE (user_id, analysis_date)
);

-- Create indexes for performance
CREATE INDEX idx_daily_work_analyses_user_id ON daily_work_analyses(user_id);
CREATE INDEX idx_daily_work_analyses_analysis_date ON daily_work_analyses(analysis_date);
CREATE INDEX idx_daily_work_analyses_user_date ON daily_work_analyses(user_id, analysis_date);

-- Create work_items table
CREATE TABLE IF NOT EXISTS work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    daily_analysis_id UUID NOT NULL REFERENCES daily_work_analyses(id) ON DELETE CASCADE,
    
    -- Work item identification
    item_type VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    
    -- Work item metadata
    title TEXT,
    description TEXT,
    url TEXT,
    
    -- Timing
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Metrics
    loc_added INTEGER DEFAULT 0,
    loc_removed INTEGER DEFAULT 0,
    files_changed INTEGER DEFAULT 0,
    estimated_hours FLOAT DEFAULT 0.0,
    
    -- Additional data
    metadata JSONB,
    
    -- Deduplication
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of_id UUID REFERENCES work_items(id),
    
    -- AI analysis
    ai_summary TEXT,
    ai_tags JSONB,
    
    -- Ensure unique work items per analysis
    CONSTRAINT unique_analysis_source_id UNIQUE (daily_analysis_id, source, source_id)
);

-- Create indexes for work_items
CREATE INDEX idx_work_items_daily_analysis_id ON work_items(daily_analysis_id);
CREATE INDEX idx_work_items_source ON work_items(source);
CREATE INDEX idx_work_items_item_type ON work_items(item_type);
CREATE INDEX idx_work_items_created_at ON work_items(created_at);

-- Create deduplication_results table
CREATE TABLE IF NOT EXISTS deduplication_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    daily_analysis_id UUID NOT NULL REFERENCES daily_work_analyses(id) ON DELETE CASCADE,
    
    -- Items being compared
    item1_id VARCHAR(255) NOT NULL,
    item1_type VARCHAR(50) NOT NULL,
    item1_source VARCHAR(50) NOT NULL,
    
    item2_id VARCHAR(255) NOT NULL,
    item2_type VARCHAR(50) NOT NULL,
    item2_source VARCHAR(50) NOT NULL,
    
    -- Deduplication result
    is_duplicate BOOLEAN NOT NULL,
    confidence_score FLOAT,
    reason TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for deduplication_results
CREATE INDEX idx_deduplication_results_daily_analysis_id ON deduplication_results(daily_analysis_id);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_daily_work_analyses_updated_at BEFORE UPDATE
    ON daily_work_analyses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add Row Level Security (RLS) policies
ALTER TABLE daily_work_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE deduplication_results ENABLE ROW LEVEL SECURITY;

-- Policy for daily_work_analyses: Users can only see their own analyses
CREATE POLICY "Users can view own daily analyses" ON daily_work_analyses
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own daily analyses" ON daily_work_analyses
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own daily analyses" ON daily_work_analyses
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own daily analyses" ON daily_work_analyses
    FOR DELETE USING (auth.uid() = user_id);

-- Policy for work_items: Users can only see work items from their analyses
CREATE POLICY "Users can view own work items" ON work_items
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM daily_work_analyses 
            WHERE daily_work_analyses.id = work_items.daily_analysis_id 
            AND daily_work_analyses.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own work items" ON work_items
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM daily_work_analyses 
            WHERE daily_work_analyses.id = work_items.daily_analysis_id 
            AND daily_work_analyses.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own work items" ON work_items
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM daily_work_analyses 
            WHERE daily_work_analyses.id = work_items.daily_analysis_id 
            AND daily_work_analyses.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete own work items" ON work_items
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM daily_work_analyses 
            WHERE daily_work_analyses.id = work_items.daily_analysis_id 
            AND daily_work_analyses.user_id = auth.uid()
        )
    );

-- Policy for deduplication_results: Users can only see deduplication results from their analyses
CREATE POLICY "Users can view own deduplication results" ON deduplication_results
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM daily_work_analyses 
            WHERE daily_work_analyses.id = deduplication_results.daily_analysis_id 
            AND daily_work_analyses.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own deduplication results" ON deduplication_results
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM daily_work_analyses 
            WHERE daily_work_analyses.id = deduplication_results.daily_analysis_id 
            AND daily_work_analyses.user_id = auth.uid()
        )
    );

-- Grant necessary permissions
GRANT ALL ON daily_work_analyses TO authenticated;
GRANT ALL ON work_items TO authenticated;
GRANT ALL ON deduplication_results TO authenticated;