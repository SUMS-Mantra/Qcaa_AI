-- Run this in the Supabase SQL Editor to add the assignment_text column
-- to the existing ai_results table.
ALTER TABLE ai_results ADD COLUMN IF NOT EXISTS assignment_text text;
