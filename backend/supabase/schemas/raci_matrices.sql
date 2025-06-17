-- Create enums for RACI matrices
DO $$ BEGIN
    CREATE TYPE raci_role_type AS ENUM ('R', 'A', 'C', 'I');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE raci_matrix_type AS ENUM ('inventory_inbound', 'shipbob_issues', 'data_collection', 'retail_logistics', 'custom');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Main RACI matrices table
CREATE TABLE IF NOT EXISTS public.raci_matrices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  matrix_type raci_matrix_type NOT NULL DEFAULT 'custom',
  metadata JSONB DEFAULT '{}'::JSONB,
  is_active BOOLEAN DEFAULT TRUE,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Activities within RACI matrices
CREATE TABLE IF NOT EXISTS public.raci_activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matrix_id UUID NOT NULL REFERENCES public.raci_matrices(id) ON DELETE CASCADE,
  activity_id TEXT NOT NULL, -- Internal ID within the matrix
  name TEXT NOT NULL,
  description TEXT,
  order_index INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(matrix_id, activity_id)
);

-- Roles within RACI matrices
CREATE TABLE IF NOT EXISTS public.raci_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matrix_id UUID NOT NULL REFERENCES public.raci_matrices(id) ON DELETE CASCADE,
  role_id TEXT NOT NULL, -- Internal ID within the matrix
  name TEXT NOT NULL,
  title TEXT,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  is_person BOOLEAN DEFAULT FALSE,
  order_index INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(matrix_id, role_id)
);

-- RACI assignments connecting activities and roles
CREATE TABLE IF NOT EXISTS public.raci_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matrix_id UUID NOT NULL REFERENCES public.raci_matrices(id) ON DELETE CASCADE,
  activity_id TEXT NOT NULL,
  role_id TEXT NOT NULL,
  role raci_role_type NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(matrix_id, activity_id, role_id),
  FOREIGN KEY (matrix_id, activity_id) REFERENCES public.raci_activities(matrix_id, activity_id) ON DELETE CASCADE,
  FOREIGN KEY (matrix_id, role_id) REFERENCES public.raci_roles(matrix_id, role_id) ON DELETE CASCADE
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_raci_matrices_type ON public.raci_matrices(matrix_type);
CREATE INDEX IF NOT EXISTS idx_raci_matrices_active ON public.raci_matrices(is_active);
CREATE INDEX IF NOT EXISTS idx_raci_matrices_created_by ON public.raci_matrices(created_by);
CREATE INDEX IF NOT EXISTS idx_raci_activities_matrix ON public.raci_activities(matrix_id);
CREATE INDEX IF NOT EXISTS idx_raci_roles_matrix ON public.raci_roles(matrix_id);
CREATE INDEX IF NOT EXISTS idx_raci_roles_user ON public.raci_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_raci_assignments_matrix ON public.raci_assignments(matrix_id);
CREATE INDEX IF NOT EXISTS idx_raci_assignments_activity ON public.raci_assignments(matrix_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_raci_assignments_role ON public.raci_assignments(matrix_id, role_id);

-- Enable RLS on all tables
ALTER TABLE public.raci_matrices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raci_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raci_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raci_assignments ENABLE ROW LEVEL SECURITY;

-- RLS Policies for raci_matrices
CREATE POLICY "Users can view RACI matrices" 
  ON public.raci_matrices 
  FOR SELECT 
  USING (
    auth.uid() IS NOT NULL AND (
      is_active = TRUE OR
      auth.uid() = created_by OR
      EXISTS (
        SELECT 1 FROM public.users 
        WHERE id = auth.uid() AND role = 'ADMIN'
      )
    )
  );

CREATE POLICY "Users can create RACI matrices" 
  ON public.raci_matrices 
  FOR INSERT 
  WITH CHECK (
    auth.uid() IS NOT NULL AND
    auth.uid() = created_by
  );

CREATE POLICY "Users can update their RACI matrices" 
  ON public.raci_matrices 
  FOR UPDATE 
  USING (
    auth.uid() = created_by OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

CREATE POLICY "Users can delete their RACI matrices" 
  ON public.raci_matrices 
  FOR DELETE 
  USING (
    auth.uid() = created_by OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- RLS Policies for raci_activities (inherit from matrix permissions)
CREATE POLICY "Users can view activities from accessible matrices" 
  ON public.raci_activities 
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.raci_matrices m
      WHERE m.id = matrix_id
      AND (
        auth.uid() IS NOT NULL AND (
          m.is_active = TRUE OR
          auth.uid() = m.created_by OR
          EXISTS (
            SELECT 1 FROM public.users 
            WHERE id = auth.uid() AND role = 'ADMIN'
          )
        )
      )
    )
  );

-- RLS Policies for raci_roles (inherit from matrix permissions)
CREATE POLICY "Users can view roles from accessible matrices" 
  ON public.raci_roles 
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.raci_matrices m
      WHERE m.id = matrix_id
      AND (
        auth.uid() IS NOT NULL AND (
          m.is_active = TRUE OR
          auth.uid() = m.created_by OR
          EXISTS (
            SELECT 1 FROM public.users 
            WHERE id = auth.uid() AND role = 'ADMIN'
          )
        )
      )
    )
  );

-- RLS Policies for raci_assignments (inherit from matrix permissions)
CREATE POLICY "Users can view assignments from accessible matrices" 
  ON public.raci_assignments 
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.raci_matrices m
      WHERE m.id = matrix_id
      AND (
        auth.uid() IS NOT NULL AND (
          m.is_active = TRUE OR
          auth.uid() = m.created_by OR
          EXISTS (
            SELECT 1 FROM public.users 
            WHERE id = auth.uid() AND role = 'ADMIN'
          )
        )
      )
    )
  );

-- Functions to update the updated_at timestamp
CREATE OR REPLACE FUNCTION public.set_updated_at() 
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to update the updated_at timestamp
DROP TRIGGER IF EXISTS raci_matrices_updated_at ON public.raci_matrices;
CREATE TRIGGER raci_matrices_updated_at
  BEFORE UPDATE ON public.raci_matrices
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS raci_activities_updated_at ON public.raci_activities;
CREATE TRIGGER raci_activities_updated_at
  BEFORE UPDATE ON public.raci_activities
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS raci_roles_updated_at ON public.raci_roles;
CREATE TRIGGER raci_roles_updated_at
  BEFORE UPDATE ON public.raci_roles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS raci_assignments_updated_at ON public.raci_assignments;
CREATE TRIGGER raci_assignments_updated_at
  BEFORE UPDATE ON public.raci_assignments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at(); 