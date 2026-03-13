import { supabaseAdmin } from './supabase';

interface AuditEntry {
  actor_id: string | null;
  action: string;
  resource_type?: string;
  resource_id?: string;
  metadata?: Record<string, unknown>;
}

/** Append an immutable audit log entry. */
export async function writeAuditLog(entry: AuditEntry) {
  const { error } = await supabaseAdmin.from('audit_logs').insert({
    actor_id: entry.actor_id,
    action: entry.action,
    resource_type: entry.resource_type ?? null,
    resource_id: entry.resource_id ?? null,
    metadata: entry.metadata ?? {},
  });
  if (error) {
    console.error('[audit] Failed to write log:', error.message);
  }
}
