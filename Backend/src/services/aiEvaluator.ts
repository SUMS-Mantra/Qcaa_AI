import { supabaseAdmin } from '../lib/supabase';
import { writeAuditLog } from '../lib/audit';

/**
 * Process an assignment through the AI evaluation pipeline.
 * Called asynchronously after upload — do NOT await in the request handler.
 */
export async function evaluateAssignment(assignmentId: string, userId: string) {
  try {
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

    // 4. Call AI service (send file as multipart form)
    const aiServiceUrl = process.env.AI_SERVICE_URL;
    const originalFilename = assignment.original_filename || 'upload.txt';

    // Build a description for audit logging
    const aiInput = JSON.stringify({ subject: subjectName, assessment_type: assessmentType, filename: originalFilename });

    let aiResponse: any;

    if (aiServiceUrl) {
      const formData = new FormData();
      formData.append('file', fileData, originalFilename);
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
      aiResponse = await resp.json();
    } else {
      // Fallback: generate placeholder scores when no AI service is configured
      const rubrics = assess?.rubrics ?? [];
      aiResponse = {
        rubric_scores: rubrics.map((r: any) => ({
          criterion_id: r.id,
          criterion: r.criterion,
          score: Math.floor(Math.random() * (r.max_score + 1)),
          max_score: r.max_score,
          feedback: `Placeholder feedback for "${r.criterion}". Connect an AI service for real evaluation.`,
        })),
        feedback: 'This is placeholder feedback. Configure AI_SERVICE_URL in .env for real AI evaluation.',
      };
      const totalScore = aiResponse.rubric_scores.reduce((s: number, r: any) => s + r.score, 0);
      const totalMax = aiResponse.rubric_scores.reduce((s: number, r: any) => s + r.max_score, 0);
      aiResponse.overall_score = totalScore;
      aiResponse.max_overall_score = totalMax;
    }

    // 6. Store AI results
    const { error: insertErr } = await supabaseAdmin.from('ai_results').insert({
      assignment_id: assignmentId,
      rubric_scores: aiResponse.rubric_scores,
      overall_score: aiResponse.overall_score ?? 0,
      max_overall_score: aiResponse.max_overall_score ?? 0,
      feedback: aiResponse.feedback ?? '',
      raw_ai_input: aiInput,
      raw_ai_output: JSON.stringify(aiResponse),
      model_version: aiResponse.model_version ?? 'placeholder-v1',
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
