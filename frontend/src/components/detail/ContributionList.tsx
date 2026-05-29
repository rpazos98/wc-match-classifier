import { useAppState } from '../../state/AppContext';
import { scoreColor, barColor } from '../../utils/labels';
import { useEffect, useRef, useState } from 'react';

interface ContribRow {
  name: string;
  label: string;
  desc: string;
  pts: number;
  raw: number;
  weight: number;
  reason: string;
  detail: string;
}

interface ContributionListProps {
  breakdown: Record<string, number>;
  rawByScorer: Record<string, number>;
  weightByScorer: Record<string, number>;
  reasonByScorer: Record<string, string>;
  detailByScorer?: Record<string, string>;
  score: number;
}

const QUALITY_SCORERS = new Set([
  'Competitive Tension',
  'Chaos Potential',
  'Form',
]);

const CONTEXT_SCORERS = new Set([
  'Match Stage',
  'Narrative',
  'Star Power',
]);

const PERSONAL_SCORERS = new Set([
  'Favorite Team',
  'Same Group',
  'Momentum',
]);

function ContribRowItem({ r, cls }: { r: ContribRow; cls: string }) {
  const barRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);

  const rawPct = Math.round(r.raw * 100);
  const wPct = Math.round(r.weight * 100);
  const isPositive = r.pts > 2;
  const isNegative = r.pts < 1 && r.raw < 0.15;
  const sign = isPositive ? '+' : isNegative ? '\u2212' : ' ';
  const signCol = isPositive
    ? 'var(--green)'
    : isNegative
      ? '#e06060'
      : 'var(--muted)';
  const ptsStr = r.pts > 0.05 ? r.pts.toFixed(1) : '0.0';
  const bc = barColor(r.raw);
  const hasDetail = !!(r.detail || r.reason);

  useEffect(() => {
    requestAnimationFrame(() => {
      if (barRef.current) {
        barRef.current.style.width = `${rawPct}%`;
      }
    });
  }, [rawPct]);

  return (
    <div className={`scorer-block ${cls}${expanded ? ' scorer-expanded' : ''}`}>
      <div
        className={`contrib-top${hasDetail ? ' contrib-clickable' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        <span className="contrib-sign" style={{ color: signCol }}>
          {sign}
        </span>
        <span className="sc-name" title={r.desc}>
          {r.label}
          {hasDetail && (
            <span className="sc-expand-icon">
              {expanded ? '\u25BC' : '\u25B6'}
            </span>
          )}
        </span>
        <span className="contrib-pts" style={{ color: signCol }}>
          {sign === '\u2212' ? '' : '+'}
          {ptsStr}
        </span>
      </div>
      <div className="contrib-bottom">
        <span className="contrib-formula">
          {rawPct}% &times; {wPct}%
        </span>
        <div className="sc-bar-bg">
          <div
            ref={barRef}
            className="sc-bar-fill"
            style={{ width: '0%', background: bc }}
          />
        </div>
      </div>
      {expanded && (
        <div className="sc-detail">
          {r.reason && <div className="sc-detail-reason">{r.reason}</div>}
          {r.detail && (
            <pre className="sc-detail-calc">{r.detail}</pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function ContributionList({
  breakdown,
  rawByScorer,
  weightByScorer,
  reasonByScorer,
  detailByScorer,
  score,
}: ContributionListProps) {
  const { weights } = useAppState();
  const color = scoreColor(score);

  const allRows: ContribRow[] = Object.entries(breakdown).map(
    ([name, pts]) => ({
      name,
      label: weights[name]?.label || name,
      desc: weights[name]?.desc || '',
      pts,
      raw: rawByScorer?.[name] ?? 0,
      weight:
        weightByScorer?.[name] ?? ((weights[name]?.max_pts ?? 0) / 100),
      reason: reasonByScorer?.[name] || '',
      detail: detailByScorer?.[name] || '',
    }),
  );

  const qualityRows = allRows
    .filter((r) => QUALITY_SCORERS.has(r.name))
    .sort((a, b) => b.pts - a.pts);
  const contextRows = allRows
    .filter((r) => CONTEXT_SCORERS.has(r.name))
    .sort((a, b) => b.pts - a.pts);
  const persRows = allRows
    .filter((r) => PERSONAL_SCORERS.has(r.name))
    .sort((a, b) => b.pts - a.pts);

  const visibleQualRows = qualityRows.filter((r) => r.weight >= 0.005);
  const visibleCtxRows = contextRows.filter((r) => r.weight >= 0.005);
  const visiblePersRows = persRows.filter(
    (r) => r.pts > 0.05 && r.weight >= 0.005,
  );

  const lowScorers = allRows
    .filter((r) => r.raw < 0.15 && r.weight > 0.03)
    .sort((a, b) => a.raw - b.raw);

  return (
    <>
      <div className="det-section">
        {visibleQualRows.length > 0 && (
          <>
            <div className="det-group-hdr">
              <span style={{ color: '#3dd6c8' }}>QUALITY</span>
            </div>
            {visibleQualRows
              .filter((r) => r.weight >= 0.005)
              .map((r) => (
                <ContribRowItem key={r.name} r={r} cls="ent-row" />
              ))}
          </>
        )}

        {visibleCtxRows.length > 0 && (
          <>
            <div className="det-group-hdr" style={{ marginTop: 4 }}>
              <span style={{ color: '#a78bfa' }}>CONTEXT</span>
            </div>
            {visibleCtxRows
              .filter((r) => r.weight >= 0.005)
              .map((r) => (
                <ContribRowItem key={r.name} r={r} cls="ctx-row" />
              ))}
          </>
        )}

        {visiblePersRows.length > 0 && (
          <>
            <div className="det-group-hdr" style={{ marginTop: 4 }}>
              <span style={{ color: 'var(--gold)' }}>YOUR PROFILE</span>
            </div>
            {visiblePersRows.map((r) => (
              <ContribRowItem key={r.name} r={r} cls="prof-row" />
            ))}
          </>
        )}

        <div className="det-total">
          <span style={{ color: 'var(--text-sm)' }}>TOTAL</span>
          <span style={{ color }}>
            {score} / 100
          </span>
        </div>
      </div>

      {lowScorers.length > 0 && (
        <div className="det-section" style={{ paddingTop: 8 }}>
          <div className="det-section-title" style={{ color: '#e06060' }}>
            What holds it back
          </div>
          {lowScorers.map((r) => (
            <div key={r.name} className="holdback-item">
              <span className="holdback-dash">&minus;</span>
              <span>{r.label}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
