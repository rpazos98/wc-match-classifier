import type { Match, ScorerWeight } from '../../types';
import { fl } from '../../utils/flags';
import { scoreColor, barColor } from '../../utils/labels';
import { useAppState, useAppDispatch } from '../../state/AppContext';

interface Props {
  matchA: Match;
  matchB: Match;
}

export default function ComparisonView({ matchA, matchB }: Props) {
  const { weights } = useAppState();
  const dispatch = useAppDispatch();

  const allScorers = [...new Set([
    ...Object.keys(matchA.breakdown),
    ...Object.keys(matchB.breakdown),
  ])];

  const rows = allScorers.map((name) => ({
    name,
    label: (weights[name] as ScorerWeight | undefined)?.label || name,
    maxPts: (weights[name] as ScorerWeight | undefined)?.max_pts || 0,
    ptsA: matchA.breakdown[name] || 0,
    ptsB: matchB.breakdown[name] || 0,
  })).sort((a, b) => Math.max(b.ptsA, b.ptsB) - Math.max(a.ptsA, a.ptsB));

  const cA = scoreColor(matchA.score);
  const cB = scoreColor(matchB.score);
  const winner = matchA.score > matchB.score ? 'A' : matchB.score > matchA.score ? 'B' : null;
  const diff = Math.abs(matchA.score - matchB.score).toFixed(1);

  const handleClose = () => {
    dispatch({ type: 'PIN_MATCH', id: null });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header with two match cards */}
      <div className="comp-header">
        <div className="comp-match-cards">
          <div className={`comp-card ${winner === 'A' ? 'comp-card-winner' : ''}`}>
            <div className="comp-card-teams">
              {fl(matchA.home)} {matchA.home}<br />vs {fl(matchA.away)} {matchA.away}
            </div>
            <div className="comp-card-score" style={{ color: cA }}>{matchA.score.toFixed(1)}</div>
            <div className="comp-card-label">{matchA.emoji} {matchA.label}</div>
          </div>
          <div className="comp-vs">vs</div>
          <div className={`comp-card ${winner === 'B' ? 'comp-card-winner' : ''}`}>
            <div className="comp-card-teams">
              {fl(matchB.home)} {matchB.home}<br />vs {fl(matchB.away)} {matchB.away}
            </div>
            <div className="comp-card-score" style={{ color: cB }}>{matchB.score.toFixed(1)}</div>
            <div className="comp-card-label">{matchB.emoji} {matchB.label}</div>
          </div>
        </div>
        <button
          className="btn"
          style={{ fontSize: 10, padding: '3px 10px', alignSelf: 'flex-end' }}
          onClick={handleClose}
        >
          × Cerrar comparación
        </button>
      </div>

      {/* Scorer-by-scorer breakdown */}
      <div className="comp-body">
        {rows.map((r) => {
          const fpA = r.maxPts > 0 ? r.ptsA / r.maxPts : 0;
          const fpB = r.maxPts > 0 ? r.ptsB / r.maxPts : 0;
          const bcA = barColor(fpA);
          const bcB = barColor(fpB);
          const delta = r.ptsA - r.ptsB;

          return (
            <div className="comp-scorer-block" key={r.name}>
              <div className="comp-scorer-name">
                <span>{r.label}</span>
                <span className="comp-delta">
                  {Math.abs(delta) < 0.05 ? (
                    <span style={{ color: 'var(--muted)' }}>—</span>
                  ) : delta > 0 ? (
                    <span style={{ color: 'var(--green)' }}>▲{delta.toFixed(1)}</span>
                  ) : (
                    <span style={{ color: 'var(--text-sm)' }}>▼{Math.abs(delta).toFixed(1)}</span>
                  )}
                </span>
              </div>
              <div className="comp-bar-row">
                <span className="comp-bar-flag">{fl(matchA.home)}</span>
                <div className="comp-bar-bg">
                  <div
                    className="comp-bar-fill"
                    style={{ width: `${(fpA * 100).toFixed(1)}%`, background: bcA }}
                  />
                </div>
                <span className="comp-bar-pts">{r.ptsA.toFixed(1)}</span>
              </div>
              <div className="comp-bar-row">
                <span className="comp-bar-flag">{fl(matchB.home)}</span>
                <div className="comp-bar-bg">
                  <div
                    className="comp-bar-fill"
                    style={{ width: `${(fpB * 100).toFixed(1)}%`, background: bcB }}
                  />
                </div>
                <span className="comp-bar-pts">{r.ptsB.toFixed(1)}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Total comparison footer */}
      <div className="comp-total-row">
        <span style={{ color: cA, fontSize: 16 }}>{matchA.score.toFixed(1)}</span>
        <span style={{ color: 'var(--muted)', fontSize: 12 }}>vs</span>
        <span style={{ color: cB, fontSize: 16 }}>{matchB.score.toFixed(1)}</span>
        {winner ? (
          <span style={{
            fontSize: 11, color: 'var(--green)', padding: '2px 7px',
            background: 'rgba(0,212,132,0.1)', borderRadius: 5,
          }}>
            Δ {diff}
          </span>
        ) : (
          <span style={{ color: 'var(--muted)', fontSize: 11 }}>Empate</span>
        )}
      </div>
    </div>
  );
}
