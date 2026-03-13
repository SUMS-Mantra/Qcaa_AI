import { Router, Request, Response } from 'express';
import multer from 'multer';
import path from 'path';
import { supabaseAdmin, supabaseForUser } from '../lib/supabase';
import { writeAuditLog } from '../lib/audit';
import { evaluateAssignment } from '../services/aiEvaluator';

const router = Router();

// Multer stores file in memory so we can stream to Supabase storage
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 }, // 10 MB
  fileFilter: (_req, file, cb) => {
    const allowed = ['.pdf', '.docx', '.txt'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowed.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type. Allowed: PDF, DOCX, TXT'));
    }
  },
});

/** POST /api/assignments — upload + create assignment */
router.post('/', upload.single('file'), async (req: Request, res: Response) => {
  const user = req.user!;
  const file = req.file;
  const { assessment_id } = req.body;

  if (!file) {
    res.status(400).json({ error: 'File is required' });
    return;
  }
  if (!assessment_id) {
    res.status(400).json({ error: 'assessment_id is required' });
    return;
  }

  // Verify the assessment exists
  const { data: assessment } = await supabaseAdmin
    .from('assessments')
    .select('id')
    .eq('id', Number(assessment_id))
    .single();

  if (!assessment) {
    res.status(400).json({ error: 'Invalid assessment_id' });
    return;
  }

  // Upload to Supabase Storage: assignments/<user_id>/<timestamp>_<filename>
  const ts = Date.now();
  const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_');
  const storagePath = `${user.id}/${ts}_${safeName}`;

  const { error: uploadErr } = await supabaseAdmin.storage
    .from('assignments')
    .upload(storagePath, file.buffer, {
      contentType: file.mimetype,
      upsert: false,
    });

  if (uploadErr) {
    res.status(500).json({ error: `Storage upload failed: ${uploadErr.message}` });
    return;
  }

  // Insert DB record
  const { data: row, error: dbErr } = await supabaseAdmin
    .from('assignments')
    .insert({
      user_id: user.id,
      assessment_id: Number(assessment_id),
      file_path: storagePath,
      original_filename: file.originalname,
      status: 'pending',
    })
    .select()
    .single();

  if (dbErr || !row) {
    res.status(500).json({ error: `DB insert failed: ${dbErr?.message}` });
    return;
  }

  await writeAuditLog({
    actor_id: user.id,
    action: 'assignment.uploaded',
    resource_type: 'assignment',
    resource_id: row.id,
    metadata: { filename: file.originalname, assessment_id },
  });

  // Fire-and-forget AI evaluation
  evaluateAssignment(row.id, user.id);

  res.status(201).json({ assignment: row });
});

/** GET /api/assignments — list current user's assignments */
router.get('/', async (req: Request, res: Response) => {
  const user = req.user!;
  const sb = supabaseForUser(req.jwt!);

  const { data, error } = await sb
    .from('assignments')
    .select('id, assessment_id, original_filename, status, created_at, assessments(name, subjects(name))')
    .order('created_at', { ascending: false });

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  // Also fetch overall scores for completed assignments
  const ids = (data ?? []).filter(a => a.status === 'completed').map(a => a.id);
  let scores: Record<string, { overall_score: number; max_overall_score: number }> = {};

  if (ids.length > 0) {
    const { data: results } = await supabaseAdmin
      .from('ai_results')
      .select('assignment_id, overall_score, max_overall_score')
      .in('assignment_id', ids);

    for (const r of results ?? []) {
      scores[r.assignment_id] = {
        overall_score: r.overall_score,
        max_overall_score: r.max_overall_score,
      };
    }
  }

  const history = (data ?? []).map(a => ({
    id: a.id,
    fileName: a.original_filename,
    subject: (a as any).assessments?.subjects?.name ?? '',
    assessmentType: (a as any).assessments?.name ?? '',
    status: a.status,
    submittedAt: a.created_at,
    overallScore: scores[a.id]?.overall_score ?? null,
    maxOverallScore: scores[a.id]?.max_overall_score ?? null,
  }));

  res.json({ history });
});

/** GET /api/assignments/:id — single assignment status */
router.get('/:id', async (req: Request, res: Response) => {
  const sb = supabaseForUser(req.jwt!);

  const { data, error } = await sb
    .from('assignments')
    .select('*')
    .eq('id', req.params.id)
    .single();

  if (error || !data) {
    res.status(404).json({ error: 'Assignment not found' });
    return;
  }

  res.json({ assignment: data });
});

export default router;
