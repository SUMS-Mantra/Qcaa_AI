import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config();

const supabaseUrl = process.env.SUPABASE_URL;
const serviceKey = process.env.SUPABASE_SERVICE_KEY;

if (!supabaseUrl || !serviceKey) {
  throw new Error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env');
}

/**
 * Admin client — uses the service-role key.
 * Used server-side only for operations that bypass RLS
 * (e.g. inserting audit logs, triggering AI processing).
 */
export const supabaseAdmin = createClient(supabaseUrl, serviceKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

/**
 * Create a per-request Supabase client that inherits the
 * caller's JWT so RLS policies are enforced.
 */
export function supabaseForUser(jwt: string) {
  return createClient(supabaseUrl!, serviceKey!, {
    global: { headers: { Authorization: `Bearer ${jwt}` } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
