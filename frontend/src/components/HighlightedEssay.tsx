import { useMemo, useState } from 'react';
import type { RubricCriterion } from '../types';

const HIGHLIGHT_COLORS = [
  { bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-800', dot: 'bg-blue-500' },
  { bg: 'bg-emerald-100', border: 'border-emerald-300', text: 'text-emerald-800', dot: 'bg-emerald-500' },
  { bg: 'bg-amber-100', border: 'border-amber-300', text: 'text-amber-800', dot: 'bg-amber-500' },
  { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-800', dot: 'bg-purple-500' },
  { bg: 'bg-rose-100', border: 'border-rose-300', text: 'text-rose-800', dot: 'bg-rose-500' },
  { bg: 'bg-teal-100', border: 'border-teal-300', text: 'text-teal-800', dot: 'bg-teal-500' },
  { bg: 'bg-orange-100', border: 'border-orange-300', text: 'text-orange-800', dot: 'bg-orange-500' },
  { bg: 'bg-indigo-100', border: 'border-indigo-300', text: 'text-indigo-800', dot: 'bg-indigo-500' },
];

interface Span {
  start: number;
  end: number;
  criterionIdx: number;
  quote: string;
}

interface Props {
  text: string;
  criteria: RubricCriterion[];
}

export default function HighlightedEssay({ text, criteria }: Props) {
  const [activeCriterion, setActiveCriterion] = useState<number | null>(null);

  const spans = useMemo(() => {
    const found: Span[] = [];
    const lowerText = text.toLowerCase();

    criteria.forEach((c, cIdx) => {
      (c.evidenceQuotes ?? []).forEach((quote) => {
        if (!quote || quote.length < 5) return;
        const lowerQuote = quote.toLowerCase().trim();
        const idx = lowerText.indexOf(lowerQuote);
        if (idx !== -1) {
          found.push({ start: idx, end: idx + lowerQuote.length, criterionIdx: cIdx, quote });
        }
      });
    });

    // Sort by start position, resolve overlaps (keep first)
    found.sort((a, b) => a.start - b.start || b.end - a.end);
    const merged: Span[] = [];
    for (const s of found) {
      if (merged.length === 0 || s.start >= merged[merged.length - 1].end) {
        merged.push(s);
      }
    }
    return merged;
  }, [text, criteria]);

  // Build segments
  const segments: { text: string; span: Span | null }[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start > cursor) {
      segments.push({ text: text.slice(cursor, span.start), span: null });
    }
    segments.push({ text: text.slice(span.start, span.end), span });
    cursor = span.end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), span: null });
  }

  const criteriaWithQuotes = criteria
    .map((c, i) => ({ ...c, idx: i }))
    .filter((c) => (c.evidenceQuotes ?? []).length > 0);

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {criteriaWithQuotes.map((c) => {
          const color = HIGHLIGHT_COLORS[c.idx % HIGHLIGHT_COLORS.length];
          const isActive = activeCriterion === c.idx;
          return (
            <button
              key={c.id}
              onClick={() => setActiveCriterion(isActive ? null : c.idx)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
                         border transition-all cursor-pointer
                         ${isActive ? `${color.bg} ${color.border} ${color.text}` : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'}`}
            >
              <span className={`w-2 h-2 rounded-full ${color.dot}`} />
              {c.name}
            </button>
          );
        })}
      </div>

      {/* Essay text */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm leading-relaxed text-gray-700 whitespace-pre-wrap font-serif max-h-150 overflow-y-auto">
        {segments.map((seg, i) => {
          if (!seg.span) return <span key={i}>{seg.text}</span>;
          const color = HIGHLIGHT_COLORS[seg.span.criterionIdx % HIGHLIGHT_COLORS.length];
          const dimmed = activeCriterion !== null && activeCriterion !== seg.span.criterionIdx;
          return (
            <mark
              key={i}
              title={criteria[seg.span.criterionIdx]?.name}
              className={`${color.bg} ${color.text} rounded px-0.5 transition-opacity duration-200
                         ${dimmed ? 'opacity-25' : 'opacity-100'}`}
            >
              {seg.text}
            </mark>
          );
        })}
      </div>

      {spans.length === 0 && text && (
        <p className="text-xs text-gray-400 italic">No exact evidence quotes could be matched in the assignment text.</p>
      )}
    </div>
  );
}
