import { Router, Request, Response } from 'express';
import { supabaseAdmin, supabaseForUser } from '../lib/supabase';

const router = Router();

/** GET /api/feedback/:assignmentId — full AI feedback for an assignment */
router.get('/:assignmentId', async (req: Request, res: Response) => {
  const { assignmentId } = req.params;
  const sb = supabaseForUser(req.jwt!);

  // Verify user owns the assignment (RLS will enforce, but explicit check for clear error)
  const { data: assignment, error: aErr } = await sb
    .from('assignments')
    .select('id, original_filename, status, assessment_id, created_at, assessments(name, subjects(name))')
    .eq('id', assignmentId)
    .single();

  if (aErr || !assignment) {
    res.status(404).json({ error: 'Assignment not found' });
    return;
  }

  if (assignment.status === 'pending' || assignment.status === 'processing') {
    res.json({
      assignment: {
        id: assignment.id,
        fileName: assignment.original_filename,
        status: assignment.status,
        subject: (assignment as any).assessments?.subjects?.name ?? '',
        assessmentType: (assignment as any).assessments?.name ?? '',
      },
      result: null,
    });
    return;
  }

  // Fetch AI result
  const { data: result } = await supabaseAdmin
    .from('ai_results')
    .select('*')
    .eq('assignment_id', assignmentId)
    .order('processed_at', { ascending: false })
    .limit(1)
    .single();

  res.json({
    assignment: {
      id: assignment.id,
      fileName: assignment.original_filename,
      status: assignment.status,
      subject: (assignment as any).assessments?.subjects?.name ?? '',
      assessmentType: (assignment as any).assessments?.name ?? '',
      submittedAt: assignment.created_at,
    },
    result: result
      ? {
          id: result.id,
          criteria: result.rubric_scores,
          overallScore: result.overall_score,
          maxOverallScore: result.max_overall_score,
          feedback: result.feedback,
          processedAt: result.processed_at,
        }
      : null,
  });
});

export default router;
