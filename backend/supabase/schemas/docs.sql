-- Create docs table for storing AI-generated documentation
CREATE TABLE IF NOT EXISTS public.docs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  doc_type TEXT NOT NULL DEFAULT 'general',
  format TEXT NOT NULL DEFAULT 'markdown',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Optional fields
  creator_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  related_task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
  external_url TEXT,
  tags TEXT[],
  feedback_history JSONB[] DEFAULT ARRAY[]::JSONB[],
  metadata JSONB DEFAULT '{}'::JSONB
);

-- Add indices for common queries
CREATE INDEX IF NOT EXISTS idx_docs_creator ON public.docs(creator_id);
CREATE INDEX IF NOT EXISTS idx_docs_task ON public.docs(related_task_id);
CREATE INDEX IF NOT EXISTS idx_docs_type ON public.docs(doc_type);

-- Enable RLS
ALTER TABLE public.docs ENABLE ROW LEVEL SECURITY;

-- Policy: All authenticated users can view docs
CREATE POLICY "Authenticated users can view docs" 
  ON public.docs 
  FOR SELECT 
  USING (auth.role() = 'authenticated');

-- Policy: Users can update docs they created
CREATE POLICY "Users can update their own docs" 
  ON public.docs 
  FOR UPDATE 
  USING (
    auth.uid() = creator_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Policy: Users can create docs
CREATE POLICY "Users can create docs" 
  ON public.docs 
  FOR INSERT 
  WITH CHECK (
    auth.uid() IS NOT NULL
  );

-- Policy: Only creators or admins can delete docs
CREATE POLICY "Only creators or admins can delete docs" 
  ON public.docs 
  FOR DELETE 
  USING (
    auth.uid() = creator_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Function to update the updated_at timestamp
DROP TRIGGER IF EXISTS docs_updated_at ON public.docs;
CREATE TRIGGER docs_updated_at
  BEFORE UPDATE ON public.docs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at(); 