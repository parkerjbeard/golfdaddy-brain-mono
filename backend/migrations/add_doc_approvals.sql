-- Create doc_approvals table for tracking documentation approval requests
CREATE TABLE IF NOT EXISTS doc_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commit_hash VARCHAR NOT NULL,
    repository VARCHAR NOT NULL,
    diff_content TEXT NOT NULL,
    patch_content TEXT NOT NULL,
    
    -- Slack interaction details
    slack_channel VARCHAR,
    slack_message_ts VARCHAR,
    slack_user_id VARCHAR,
    
    -- Approval status
    status VARCHAR DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    approved_by VARCHAR,
    approved_at TIMESTAMP,
    rejection_reason TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    
    -- GitHub PR details
    pr_url VARCHAR,
    pr_number VARCHAR
);

-- Create indexes
CREATE INDEX idx_doc_approvals_commit_hash ON doc_approvals(commit_hash);
CREATE INDEX idx_doc_approvals_status ON doc_approvals(status);
CREATE INDEX idx_doc_approvals_created_at ON doc_approvals(created_at);
CREATE INDEX idx_doc_approvals_slack_message ON doc_approvals(slack_message_ts);

-- Add update trigger for updated_at
CREATE OR REPLACE FUNCTION update_doc_approvals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_doc_approvals_updated_at_trigger
    BEFORE UPDATE ON doc_approvals
    FOR EACH ROW
    EXECUTE FUNCTION update_doc_approvals_updated_at();

-- Add RLS policies
ALTER TABLE doc_approvals ENABLE ROW LEVEL SECURITY;

-- Policy for authenticated users to read their own approvals
CREATE POLICY "Users can view their own doc approvals"
    ON doc_approvals FOR SELECT
    USING (auth.uid()::text = slack_user_id OR auth.role() = 'admin');

-- Policy for service role to manage all approvals
CREATE POLICY "Service role can manage all doc approvals"
    ON doc_approvals FOR ALL
    USING (auth.role() = 'service_role');