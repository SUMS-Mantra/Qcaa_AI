import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getHistory, type HistoryEntry } from '../api';

function scoreBadge(score: number | null, max: number | null) {
  if (score == null || max == null || max === 0) return 'bg-gray-100 text-gray-500';
  const pct = score / max;
  if (pct >= 0.7) return 'bg-green-100 text-green-700';
  if (pct >= 0.4) return 'bg-yellow-100 text-yellow-700';
  return 'bg-red-100 text-red-700';
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: Props) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    if (open) {
      getHistory()
        .then(({ history: h }) => setHistory(h))
        .catch(() => {});
    }
  }, [open]);
  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-16 right-0 z-40 h-[calc(100vh-4rem)] w-80 bg-white border-l border-gray-200
                    shadow-xl transition-transform duration-300 ease-in-out
                    ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900 text-sm">Assignment History</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
            aria-label="Close sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto h-full pb-20 px-3 py-3 space-y-2">
          {history.length === 0 ? (
            <div className="text-center py-10">
              <p className="text-sm text-gray-400">No history yet.</p>
            </div>
          ) : (
            history.map((entry) => (
              <Link
                key={entry.id}
                to={`/feedback/${entry.id}`}
                onClick={onClose}
                className="block rounded-xl border border-gray-100 p-4 hover:bg-gray-50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate group-hover:text-zima transition-colors">
                      {entry.fileName}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {entry.subject} &middot; {entry.assessmentType}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 text-xs font-bold px-2 py-1 rounded-lg ${scoreBadge(
                      entry.overallScore,
                      entry.maxOverallScore
                    )}`}
                  >
                    {entry.overallScore != null ? `${entry.overallScore}/${entry.maxOverallScore}` : entry.status}
                  </span>
                </div>
                <p className="text-xs text-gray-300 mt-2">
                  {new Date(entry.submittedAt).toLocaleDateString()}
                </p>
              </Link>
            ))
          )}
        </div>
      </aside>
    </>
  );
}
