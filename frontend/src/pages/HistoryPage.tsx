import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getHistory, type HistoryEntry } from '../api';
import toast from 'react-hot-toast';

function scoreBadge(score: number | null, max: number | null) {
  if (score == null || max == null || max === 0) return 'bg-gray-100 text-gray-500';
  const pct = score / max;
  if (pct >= 0.7) return 'bg-green-100 text-green-700';
  if (pct >= 0.4) return 'bg-yellow-100 text-yellow-700';
  return 'bg-red-100 text-red-700';
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed': return 'bg-green-100 text-green-700';
    case 'processing': return 'bg-yellow-100 text-yellow-700';
    case 'failed': return 'bg-red-100 text-red-700';
    default: return 'bg-gray-100 text-gray-500';
  }
}

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHistory()
      .then(({ history: h }) => setHistory(h))
      .catch(() => toast.error('Failed to load history'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Assignment History</h1>
      <p className="text-gray-500 mb-8">View your previously graded assignments.</p>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : history.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-gray-400">No assignments graded yet.</p>
          <Link to="/upload" className="text-zima font-medium text-sm hover:underline mt-2 inline-block">
            Upload your first assignment
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((entry) => (
            <Link
              key={entry.id}
              to={`/feedback/${entry.id}`}
              className="flex items-center justify-between gap-4 rounded-xl border border-gray-200 bg-white
                         p-5 hover:shadow-md hover:border-gray-300 transition-all group"
            >
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-10 h-10 rounded-lg bg-zima/10 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-zima" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-zima transition-colors">
                    {entry.fileName}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {entry.subject} &middot; {entry.assessmentType} &middot;{' '}
                    {new Date(entry.submittedAt).toLocaleDateString()}
                  </p>
                </div>
              </div>
              {entry.status === 'completed' && entry.overallScore != null ? (
                <span
                  className={`shrink-0 text-xs font-bold px-3 py-1.5 rounded-lg ${scoreBadge(
                    entry.overallScore,
                    entry.maxOverallScore
                  )}`}
                >
                  {entry.overallScore}/{entry.maxOverallScore}
                </span>
              ) : (
                <span className={`shrink-0 text-xs font-bold px-3 py-1.5 rounded-lg ${statusBadge(entry.status)}`}>
                  {entry.status}
                </span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
