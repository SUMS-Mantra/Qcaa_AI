import { Router, Request, Response } from 'express';
import { supabaseAdmin } from '../lib/supabase';

const router = Router();

/** GET /api/subjects — list all subjects with their assessment types */
router.get('/', async (_req: Request, res: Response) => {
  const { data, error } = await supabaseAdmin
    .from('subjects')
    .select('id, name, assessments(id, name)')
    .order('name');

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  res.json({ subjects: data });
});

export default router;
