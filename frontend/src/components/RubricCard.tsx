import type { RubricCriterion } from '../types';

function scoreColor(score: number, max: number): string {
  const pct = max > 0 ? score / max : 0;
  if (pct >= 0.7) return 'score-high';
  if (pct >= 0.4) return 'score-mid';
  return 'score-low';
}

function scoreBg(score: number, max: number): string {
  const pct = max > 0 ? score / max : 0;
  if (pct >= 0.7) return 'bg-green-50 border-green-200';
  if (pct >= 0.4) return 'bg-yellow-50 border-yellow-200';
  return 'bg-red-50 border-red-200';
}

interface Props {
  criterion: RubricCriterion;
}

export default function RubricCard({ criterion }: Props) {
  const color = scoreColor(criterion.score, criterion.maxScore);
  const bg = scoreBg(criterion.score, criterion.maxScore);
  const pct = criterion.maxScore > 0 ? Math.round((criterion.score / criterion.maxScore) * 100) : 0;
  const needsImprovement = pct < 50;

  return (
    <div className={`rounded-xl border p-5 transition-shadow hover:shadow-md ${bg}`}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug">{criterion.name}</h3>
        <span className={`shrink-0 px-2.5 py-1 rounded-lg text-xs font-bold text-${color}`}>
          {criterion.score}/{criterion.maxScore}
        </span>
      </div>

      {/* Mini progress bar */}
      <div className="w-full h-1.5 bg-white/60 rounded-full overflow-hidden mb-3">
        <div
          className={`h-full rounded-full bg-${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <p className="text-sm text-gray-600 leading-relaxed">{criterion.feedback}</p>

      {needsImprovement && (
        <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-score-low">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Needs improvement
        </div>
      )}
    </div>
  );
}
