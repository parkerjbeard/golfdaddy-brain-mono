-- Function to get daily report by user and date
-- This uses the same date extraction logic as the unique constraint
CREATE OR REPLACE FUNCTION public.get_daily_report_by_user_date(
    p_user_id uuid,
    p_date date
)
RETURNS SETOF public.daily_reports
LANGUAGE sql
STABLE PARALLEL SAFE
AS $$
    SELECT *
    FROM public.daily_reports
    WHERE user_id = p_user_id
      AND public.get_date_immutable(report_date) = p_date
    LIMIT 1;
$$;

COMMENT ON FUNCTION public.get_daily_report_by_user_date IS 'Get daily report for a user on a specific date, using the same date extraction as the unique constraint';

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.get_daily_report_by_user_date TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_daily_report_by_user_date TO service_role;