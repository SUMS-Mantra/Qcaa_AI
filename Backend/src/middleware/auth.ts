import { Request, Response, NextFunction } from 'express';
import { supabaseAdmin } from '../lib/supabase';

/** Populated by authRequired middleware */
export interface AuthUser {
  id: string;
  email: string;
  role: string;
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
      jwt?: string;
    }
  }
}

/**
 * Verifies the Bearer token via Supabase Auth and attaches
 * `req.user` and `req.jwt` to the request.
 */
export async function authRequired(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'Missing or invalid Authorization header' });
    return;
  }

  const token = header.slice(7);

  const { data: { user }, error } = await supabaseAdmin.auth.getUser(token);
  if (error || !user) {
    res.status(401).json({ error: 'Invalid or expired token' });
    return;
  }

  // Fetch role from profiles table
  const { data: profile } = await supabaseAdmin
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single();

  req.user = {
    id: user.id,
    email: user.email ?? '',
    role: profile?.role ?? 'student',
  };
  req.jwt = token;
  next();
}

/**
 * Requires the authenticated user to have one of the given roles.
 */
export function requireRole(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user || !roles.includes(req.user.role)) {
      res.status(403).json({ error: 'Forbidden' });
      return;
    }
    next();
  };
}
