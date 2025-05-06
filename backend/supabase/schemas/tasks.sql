-- Create tasks table for tracking work with RACI assignments
CREATE TABLE IF NOT EXISTS public.tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'ASSIGNED',
  priority TEXT DEFAULT 'MEDIUM',
  due_date TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- RACI model fields
  assignee_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  responsible_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  accountable_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  consulted_ids UUID[] DEFAULT ARRAY[]::UUID[],
  informed_ids UUID[] DEFAULT ARRAY[]::UUID[],
  
  -- Additional tracking fields
  creator_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  estimated_hours NUMERIC(5,2),
  actual_hours NUMERIC(5,2),
  tags TEXT[],
  metadata JSONB DEFAULT '{}'::JSONB,
  blocked BOOLEAN DEFAULT FALSE,
  blocked_reason TEXT,
  doc_references TEXT[]
);

-- Add indices for common queries
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON public.tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_responsible ON public.tasks(responsible_id);
CREATE INDEX IF NOT EXISTS idx_tasks_accountable ON public.tasks(accountable_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON public.tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON public.tasks(due_date);

-- Enable RLS
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view tasks they're involved with
CREATE POLICY "Users can view their tasks" 
  ON public.tasks 
  FOR SELECT 
  USING (
    auth.uid() IN (assignee_id, responsible_id, accountable_id) OR
    auth.uid() = ANY(consulted_ids) OR 
    auth.uid() = ANY(informed_ids) OR
    auth.uid() = creator_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Policy: Users can update tasks they're responsible for
CREATE POLICY "Users can update tasks they're responsible for" 
  ON public.tasks 
  FOR UPDATE 
  USING (
    auth.uid() = responsible_id OR 
    auth.uid() = assignee_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Policy: Users can create tasks
CREATE POLICY "Users can create tasks" 
  ON public.tasks 
  FOR INSERT 
  WITH CHECK (
    auth.uid() IS NOT NULL
  );

-- Policy: Only responsible, accountable, or admin users can delete tasks
CREATE POLICY "Users can delete tasks they're responsible for" 
  ON public.tasks 
  FOR DELETE 
  USING (
    auth.uid() = responsible_id OR 
    auth.uid() = accountable_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION public.set_updated_at() 
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update the updated_at timestamp
DROP TRIGGER IF EXISTS tasks_updated_at ON public.tasks;
CREATE TRIGGER tasks_updated_at
  BEFORE UPDATE ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at(); 