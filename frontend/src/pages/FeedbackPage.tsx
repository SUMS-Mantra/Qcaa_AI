import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import RubricCard from '../components/RubricCard';
import HighlightedEssay from '../components/HighlightedEssay';
import SkeletonCard from '../components/SkeletonCard';
import { getFeedback, type FeedbackResponse } from '../api';
import type { RubricCriterion } from '../types';

export default function FeedbackPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<FeedbackResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      const resp = await getFeedback(id);
      setData(resp);
      // If still processing, keep polling
      if (resp.assignment.status === 'pending' || resp.assignment.status === 'processing') {
        setPolling(true);
      } else {
        setPolling(false);
      }
    } catch {
      setData(null);
    }
    setLoading(false);
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll every 3 seconds while processing
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [polling, fetchData]);

  const result = data?.result;
  const assignment = data?.assignment;

  // Map API criteria to RubricCriterion for cards
  const criteria: RubricCriterion[] = (result?.criteria ?? []).map((c, i) => ({
    id: String(c.criterion_id ?? i),
    name: c.criterion,
    score: c.score,
    maxScore: c.max_score,
    feedback: c.feedback,
    band: c.band,
    improvement: c.improvement,
    evidenceQuotes: c.evidence_quotes,
    bandAnalysis: c.band_analysis,
  }));

  const overallPct = result
    ? Math.round((result.overallScore / result.maxOverallScore) * 100)
    : 0;

  const isProcessing = assignment?.status === 'pending' || assignment?.status === 'processing';

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Assignment Feedback</h1>
          {assignment && (
            <p className="text-gray-500 text-sm mt-1">
              {assignment.fileName} &middot; {assignment.subject} &middot; {assignment.assessmentType}
            </p>
          )}
        </div>
        <div className="flex gap-3">
          <Link
            to="/upload"
            className="px-4 py-2 rounded-xl border border-gray-300 text-sm font-medium text-gray-700
                       hover:bg-gray-50 transition-colors"
          >
            New Upload
          </Link>
          <button
            onClick={() => window.print()}
            disabled={!result}
            className="px-4 py-2 rounded-xl bg-zima text-white text-sm font-medium
                       hover:bg-zima-light transition-colors disabled:opacity-50"
          >
            Download PDF
          </button>
        </div>
      </div>

      {/* Processing state */}
      {isProcessing && (
        <div className="rounded-xl bg-zima/5 border border-zima/20 p-6 mb-8 text-center">
          <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-zima/10 flex items-center justify-center animate-pulse">
            <svg className="w-5 h-5 text-zima animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-zima">AI is grading your assignment…</p>
          <p className="text-xs text-gray-400 mt-1">This page will update automatically when results are ready.</p>
        </div>
      )}

      {/* Overall score banner */}
      {loading || isProcessing ? (
        !isProcessing && <div className="h-24 rounded-xl bg-gray-100 animate-pulse mb-8" />
      ) : result && (
        <div className="rounded-xl bg-linear-to-r from-zima to-zima-light p-6 mb-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-white/80">Overall Score</p>
              <p className="text-4xl font-bold mt-1">
                {result.overallScore}
                <span className="text-lg font-normal text-white/70"> / {result.maxOverallScore}</span>
              </p>
            </div>
            <div className="w-20 h-20 rounded-full border-4 border-white/30 flex items-center justify-center">
              <span className="text-2xl font-bold">{overallPct}%</span>
            </div>
          </div>
          {/* Overall bar */}
          <div className="mt-4 h-2 bg-white/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-white rounded-full transition-all duration-700"
              style={{ width: `${overallPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Assignment text with highlighted evidence */}
      {result?.assignmentText && !isProcessing && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Your Assignment</h2>
          <HighlightedEssay text={result.assignmentText} criteria={criteria} />
        </div>
      )}

      {/* Rubric grid */}
      <h2 className="text-lg font-semibold text-gray-900 mb-3">
        {loading || isProcessing ? '' : 'Rubric Breakdown'}
      </h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {(loading || isProcessing)
          ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
          : criteria.map((c) => <RubricCard key={c.id} criterion={c} />)
        }
      </div>
    </div>
  );
}
