import { useState } from 'react';
import type { RubricCriterion } from '../types';

const BAND_ORDER = ['E', 'D', 'C', 'B', 'A'];

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

function bandColor(band: string): string {
  switch (band.toUpperCase()) {
    case 'A': return 'bg-emerald-100 text-emerald-800';
    case 'B': return 'bg-blue-100 text-blue-800';
    case 'C': return 'bg-yellow-100 text-yellow-800';
    case 'D': return 'bg-orange-100 text-orange-800';
    case 'E': return 'bg-red-100 text-red-800';
    default: return 'bg-gray-100 text-gray-800';
  }
}

interface Props {
  criterion: RubricCriterion;
}

export default function RubricCard({ criterion }: Props) {
  const [expanded, setExpanded] = useState(false);
  const color = scoreColor(criterion.score, criterion.maxScore);
  const bg = scoreBg(criterion.score, criterion.maxScore);
  const pct = criterion.maxScore > 0 ? Math.round((criterion.score / criterion.maxScore) * 100) : 0;
  const needsImprovement = pct < 50;
  const hasBandAnalysis = criterion.bandAnalysis && Object.keys(criterion.bandAnalysis).length > 0;
  const hasQuotes = (criterion.evidenceQuotes ?? []).length > 0;

  return (
    <div className={`rounded-xl border p-5 transition-shadow hover:shadow-md ${bg}`}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-sm leading-snug">{criterion.name}</h3>
          {criterion.band && (
            <span className={`px-2 py-0.5 rounded-md text-xs font-bold ${bandColor(criterion.band)}`}>
              Band {criterion.band}
            </span>
          )}
        </div>
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

      {/* Evidence quotes */}
      {hasQuotes && (
        <div className="mt-3 space-y-1.5">
          <p className="text-xs font-medium text-gray-500">Evidence from your work:</p>
          {criterion.evidenceQuotes!.map((q, i) => (
            <blockquote key={i} className="text-xs text-gray-500 italic border-l-2 border-gray-300 pl-2">
              "{q}"
            </blockquote>
          ))}
        </div>
      )}

      {needsImprovement && (
        <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-score-low">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Needs improvement
        </div>
      )}

      {criterion.improvement && (
        <div className="mt-2 text-xs text-gray-500">
          <span className="font-medium">To improve:</span> {criterion.improvement}
        </div>
      )}

      {/* Band-by-band analysis (expandable) */}
      {hasBandAnalysis && (
        <div className="mt-3 pt-3 border-t border-gray-200/60">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs font-medium text-gray-500 hover:text-gray-700 flex items-center gap-1 cursor-pointer"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-90' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Band-by-band analysis
          </button>
          {expanded && (
            <div className="mt-2 space-y-1.5">
              {BAND_ORDER.map((b) => {
                const desc = criterion.bandAnalysis?.[b];
                if (!desc) return null;
                const isAwarded = criterion.band?.toUpperCase() === b;
                return (
                  <div
                    key={b}
                    className={`text-xs rounded-lg px-3 py-2 ${isAwarded ? `${bandColor(b)} font-medium` : 'bg-white/50 text-gray-500'}`}
                  >
                    <span className="font-bold">Band {b}:</span> {desc}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
