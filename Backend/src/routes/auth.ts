import { Router, Request, Response } from 'express';
import { supabaseAdmin } from '../lib/supabase';
import { writeAuditLog } from '../lib/audit';
import { authRequired } from '../middleware/auth';

const router = Router();

/** POST /api/auth/signup */
router.post('/signup', async (req: Request, res: Response) => {
  const { email, password, full_name } = req.body;

  if (!email || !password) {
    res.status(400).json({ error: 'Email and password are required' });
    return;
  }

  const { data, error } = await supabaseAdmin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { full_name: full_name ?? '' },
  });

  if (error) {
    res.status(400).json({ error: error.message });
    return;
  }

  // Create the profiles row (must exist before audit_logs FK can reference it)
  const { error: profileErr } = await supabaseAdmin.from('profiles').insert({
    id: data.user.id,
    email: data.user.email!,
    full_name: full_name ?? '',
    role: 'student',
  });

  if (profileErr) {
    console.error('[signup] Profile insert failed:', profileErr.message);
    res.status(500).json({ error: 'Account created but profile setup failed. Try logging in.' });
    return;
  }

  await writeAuditLog({
    actor_id: data.user.id,
    action: 'auth.signup',
    resource_type: 'user',
    resource_id: data.user.id,
  });

  res.status(201).json({ user: { id: data.user.id, email: data.user.email } });
});

/** POST /api/auth/login */
router.post('/login', async (req: Request, res: Response) => {
  const { email, password } = req.body;

  if (!email || !password) {
    res.status(400).json({ error: 'Email and password are required' });
    return;
  }

  const { data, error } = await supabaseAdmin.auth.signInWithPassword({ email, password });

  if (error) {
    res.status(401).json({ error: error.message });
    return;
  }

  await writeAuditLog({
    actor_id: data.user.id,
    action: 'auth.login',
    resource_type: 'user',
    resource_id: data.user.id,
  });

  res.json({
    access_token: data.session.access_token,
    refresh_token: data.session.refresh_token,
    user: {
      id: data.user.id,
      email: data.user.email,
    },
  });
});

/** POST /api/auth/refresh */
router.post('/refresh', async (req: Request, res: Response) => {
  const { refresh_token } = req.body;

  if (!refresh_token) {
    res.status(400).json({ error: 'refresh_token is required' });
    return;
  }

  const { data, error } = await supabaseAdmin.auth.refreshSession({ refresh_token });

  if (error || !data.session) {
    res.status(401).json({ error: error?.message ?? 'Could not refresh session' });
    return;
  }

  res.json({
    access_token: data.session.access_token,
    refresh_token: data.session.refresh_token,
  });
});

/** GET /api/auth/me — returns current user profile */
router.get('/me', authRequired, async (req: Request, res: Response) => {
  // This route requires authRequired middleware to be applied upstream
  if (!req.user) {
    res.status(401).json({ error: 'Not authenticated' });
    return;
  }

  const { data: profile } = await supabaseAdmin
    .from('profiles')
    .select('*')
    .eq('id', req.user.id)
    .single();

  res.json({ profile });
});

export default router;
