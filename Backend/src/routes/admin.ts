import { Router, Request, Response } from 'express';
import { supabaseAdmin } from '../lib/supabase';
import { requireRole } from '../middleware/auth';

const router = Router();

// All routes below require admin role
router.use(requireRole('admin'));

/** GET /api/admin/assignments — all assignments across all users */
router.get('/assignments', async (_req: Request, res: Response) => {
  const { data, error } = await supabaseAdmin
    .from('assignments')
    .select('*, profiles(email, full_name), assessments(name, subjects(name))')
    .order('created_at', { ascending: false })
    .limit(200);

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  res.json({ assignments: data });
});

/** GET /api/admin/results — all AI results */
router.get('/results', async (_req: Request, res: Response) => {
  const { data, error } = await supabaseAdmin
    .from('ai_results')
    .select('*, assignments(original_filename, profiles(email))')
    .order('processed_at', { ascending: false })
    .limit(200);

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  res.json({ results: data });
});

/** GET /api/admin/audit — audit log entries */
router.get('/audit', async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 100, 500);
  const offset = Number(req.query.offset) || 0;

  const { data, error } = await supabaseAdmin
    .from('audit_logs')
    .select('*, profiles(email)')
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  res.json({ logs: data });
});

/** GET /api/admin/stats — dashboard stats */
router.get('/stats', async (_req: Request, res: Response) => {
  const [assignmentCount, completedCount, userCount] = await Promise.all([
    supabaseAdmin.from('assignments').select('id', { count: 'exact', head: true }),
    supabaseAdmin.from('assignments').select('id', { count: 'exact', head: true }).eq('status', 'completed'),
    supabaseAdmin.from('profiles').select('id', { count: 'exact', head: true }),
  ]);

  // Average score
  const { data: avgData } = await supabaseAdmin
    .from('ai_results')
    .select('overall_score, max_overall_score');

  let avgPct = 0;
  if (avgData && avgData.length > 0) {
    const totalPct = avgData.reduce((sum, r) => {
      const max = r.max_overall_score || 1;
      return sum + (r.overall_score / max) * 100;
    }, 0);
    avgPct = Math.round(totalPct / avgData.length);
  }

  res.json({
    totalAssignments: assignmentCount.count ?? 0,
    completedAssignments: completedCount.count ?? 0,
    totalUsers: userCount.count ?? 0,
    averageScorePercent: avgPct,
  });
});

export default router;
