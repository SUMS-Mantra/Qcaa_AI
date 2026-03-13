import crypto from 'crypto';
import { supabaseAdmin } from '../lib/supabase';
import { writeAuditLog } from '../lib/audit';

/**
 * Compute a SHA-256 hash of a file buffer for deduplication.
 */
function hashFile(buffer: ArrayBuffer): string {
  return crypto.createHash('sha256').update(Buffer.from(buffer)).digest('hex');
}

/**
 * Process an assignment through the AI evaluation pipeline.
 * Called asynchronously after upload — do NOT await in the request handler.
 *
 * FAIL-CLOSED: If AI_SERVICE_URL is missing or the AI service fails,
 * grading stops with an error — no random/placeholder scores are ever assigned.
 */
export async function evaluateAssignment(assignmentId: string, userId: string) {
  try {
    // Fail-closed: refuse to run without AI service configured (#1)
    const aiServiceUrl = process.env.AI_SERVICE_URL;
    if (!aiServiceUrl) {
      throw new Error('AI_SERVICE_URL not configured. AI grading cannot run.');
    }

    // 1. Mark as processing
    await supabaseAdmin
      .from('assignments')
      .update({ status: 'processing' })
      .eq('id', assignmentId);

    // 2. Fetch assignment + assessment + subject
    const { data: assignment } = await supabaseAdmin
      .from('assignments')
      .select('*, assessments(*, subjects(name), rubrics(*))')
      .eq('id', assignmentId)
      .single();

    if (!assignment) throw new Error('Assignment not found');

    const assess = (assignment as any).assessments;
    const subjectName: string = assess?.subjects?.name ?? '';
    const assessmentType: string = assess?.name ?? '';

    // 3. Download the file from storage
    const { data: fileData, error: dlError } = await supabaseAdmin
      .storage
      .from('assignments')
      .download(assignment.file_path);

    if (dlError || !fileData) throw new Error(`File download failed: ${dlError?.message}`);

    // 4. File hash deduplication (#4)
    // Compute SHA-256 of the uploaded file and check for cached AI results.
    const fileBuffer = await fileData.arrayBuffer();
    const fileHash = hashFile(fileBuffer);
    const assessmentIdForDedup = assess?.id ?? '';

    // Store the hash on the assignment row
    await supabaseAdmin
      .from('assignments')
      .update({ file_hash: fileHash })
      .eq('id', assignmentId);

    // Check if an identical submission (same assessment + file hash) already has results
    const { data: existingResult } = await supabaseAdmin
      .from('ai_results')
      .select('*')
      .eq('assignment_id', assignmentId)
      .limit(1)
      .maybeSingle();

    if (!existingResult && assessmentIdForDedup) {
      // Look for a different assignment with the same assessment + file hash that already has results
      const { data: dupAssignment } = await supabaseAdmin
        .from('assignments')
        .select('id')
        .eq('assessment_id', assessmentIdForDedup)
        .eq('file_hash', fileHash)
        .neq('id', assignmentId)
        .eq('status', 'completed')
        .limit(1)
        .maybeSingle();

      if (dupAssignment) {
        const { data: cachedResult } = await supabaseAdmin
          .from('ai_results')
          .select('*')
          .eq('assignment_id', dupAssignment.id)
          .limit(1)
          .maybeSingle();

        if (cachedResult) {
          console.log(`[ai] Cache hit: reusing result from assignment ${dupAssignment.id} for ${assignmentId}`);

          await supabaseAdmin.from('ai_results').insert({
            assignment_id: assignmentId,
            rubric_scores: cachedResult.rubric_scores,
            overall_score: cachedResult.overall_score,
            max_overall_score: cachedResult.max_overall_score,
            feedback: cachedResult.feedback,
            raw_ai_input: cachedResult.raw_ai_input,
            raw_ai_output: cachedResult.raw_ai_output,
            model_version: cachedResult.model_version,
          });

          await supabaseAdmin
            .from('assignments')
            .update({ status: 'completed' })
            .eq('id', assignmentId);

          await writeAuditLog({
            actor_id: userId,
            action: 'ai.evaluation.cached',
            resource_type: 'assignment',
            resource_id: assignmentId,
            metadata: {
              cached_from: dupAssignment.id,
              overall_score: cachedResult.overall_score,
              max_overall_score: cachedResult.max_overall_score,
            },
          });

          return;
        }
      }
    }

    // 5. Call AI service (send file as multipart form) — fail-closed, no fallback (#1)
    const originalFilename = assignment.original_filename || 'upload.txt';
    const aiInput = JSON.stringify({ subject: subjectName, assessment_type: assessmentType, filename: originalFilename });

    const formData = new FormData();
    formData.append('file', new Blob([fileBuffer]), originalFilename);
    formData.append('subject', subjectName);
    formData.append('assessment_type', assessmentType);

    const resp = await fetch(aiServiceUrl, {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) {
      const errBody = await resp.text();
      throw new Error(`AI service error ${resp.status}: ${errBody}`);
    }
    const aiResponse: any = await resp.json();

    // 6. Store AI results
    const { error: insertErr } = await supabaseAdmin.from('ai_results').insert({
      assignment_id: assignmentId,
      rubric_scores: aiResponse.rubric_scores,
      overall_score: aiResponse.overall_score ?? 0,
      max_overall_score: aiResponse.max_overall_score ?? 0,
      feedback: aiResponse.feedback ?? '',
      assignment_text: aiResponse.assignment_text ?? '',
      raw_ai_input: aiInput,
      raw_ai_output: JSON.stringify(aiResponse),
      model_version: aiResponse.model_version ?? 'unknown',
    });

    if (insertErr) throw insertErr;

    // 7. Mark completed
    await supabaseAdmin
      .from('assignments')
      .update({ status: 'completed' })
      .eq('id', assignmentId);

    await writeAuditLog({
      actor_id: userId,
      action: 'ai.evaluation.completed',
      resource_type: 'assignment',
      resource_id: assignmentId,
      metadata: {
        overall_score: aiResponse.overall_score,
        max_overall_score: aiResponse.max_overall_score,
      },
    });

    console.log(`[ai] Evaluation complete for assignment ${assignmentId}`);
  } catch (err: any) {
    console.error(`[ai] Evaluation failed for ${assignmentId}:`, err.message);

    await supabaseAdmin
      .from('assignments')
      .update({ status: 'failed' })
      .eq('id', assignmentId);

    await writeAuditLog({
      actor_id: userId,
      action: 'ai.evaluation.failed',
      resource_type: 'assignment',
      resource_id: assignmentId,
      metadata: { error: err.message },
    });
  }
}
