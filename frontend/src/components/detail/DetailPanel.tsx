import { useState, useCallback } from 'react';
import { useAppState, useAppDispatch } from '../../state/AppContext';
import { fl } from '../../utils/flags';
import { scoreColor } from '../../utils/labels';
import ScoreRing from './ScoreRing';
import ProbabilityBar from './ProbabilityBar';
import ContributionList from './ContributionList';
import H2HSection from './H2HSection';
import StarsSection from './StarsSection';
import ComparisonView from './ComparisonView';

/* ── Disclosure section (progressive disclosure) ───────────────────────────── */

function Disclosure({
  title,
  count,
  countColor,
  children,
}: {
  title: string;
  count?: number | string;
  countColor?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((o) => !o), []);

  return (
    <div className={`disclosure-section${open ? ' open' : ''}`}>
      <div className="disclosure-hdr" onClick={toggle}>
        <span className="disclosure-arrow">{open ? '\u203A' : '\u203A'}</span>{' '}
        {title}
        {count != null && (
          <>
            {' '}
            <span
              className="disclosure-count"
              style={countColor ? { color: countColor } : undefined}
            >
              {count}
            </span>
          </>
        )}
      </div>
      {open && <div className="disclosure-body">{children}</div>}
    </div>
  );
}

/* ── Simulated result badge ────────────────────────────────────────────────── */

function SimResult({
  home,
  away,
  homeGoals,
  awayGoals,
  predictedWinner,
}: {
  home: string;
  away: string;
  homeGoals: number;
  awayGoals: number;
  predictedWinner?: string | null;
}) {
  return (
    <div
      style={{
        margin: '10px 16px 0',
        padding: '8px 12px',
        background: 'rgba(94,214,74,0.08)',
        border: '1px solid rgba(94,214,74,0.25)',
        borderRadius: 6,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span
        style={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: 1,
          textTransform: 'uppercase',
          color: 'var(--text-sm)',
        }}
      >
        Resultado predicho
      </span>
      <span style={{ fontSize: 14, fontWeight: 900, color: '#fff' }}>
        {fl(home)} {homeGoals} - {awayGoals} {fl(away)}
      </span>
      {predictedWinner && (
        <span style={{ fontSize: 15, fontWeight: 900, color: 'var(--green)' }}>
          {fl(predictedWinner)} {predictedWinner}
        </span>
      )}
    </div>
  );
}

/* ── Simulation path section ───────────────────────────────────────────────── */

function SimPath({
  home,
  away,
  rarity,
  homePath,
  awayPath,
}: {
  home: string;
  away: string;
  rarity: number;
  homePath: Record<string, number>;
  awayPath: Record<string, number>;
}) {
  const rarePct = Math.round(rarity * 100);
  const rareLabel =
    rarePct <= 5
      ? 'Muy raro'
      : rarePct <= 15
        ? 'Poco frecuente'
        : rarePct <= 40
          ? 'Frecuente'
          : 'Muy probable';
  const rareCol =
    rarePct <= 5
      ? '#e06060'
      : rarePct <= 15
        ? 'var(--amber)'
        : rarePct <= 40
          ? 'var(--text-sm)'
          : 'var(--green)';

  const pathLabels: Record<string, string> = {
    R32: '16vos',
    R16: '8vos',
    QF: 'QF',
    SF: 'SF',
    F: 'Final',
    Champ: 'Campeon',
  };

  function TeamPathBars({
    team,
    path,
  }: {
    team: string;
    path: Record<string, number>;
  }) {
    return (
      <div className="path-col">
        <div className="path-team">
          {fl(team)} {team}
        </div>
        {Object.entries(pathLabels).map(([key, label]) => {
          const pct = Math.round((path[key] || 0) * 100);
          return (
            <div key={key} className="path-row">
              <span className="path-label">{label}</span>
              <div className="path-bar-bg">
                <div
                  className="path-bar-fill"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="path-pct">{pct}%</span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <Disclosure title="Simulacion" count={rareLabel} countColor={rareCol}>
      <div className="det-h2h">
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-sm)',
            marginBottom: 10,
          }}
        >
          Este cruce ocurre en{' '}
          <strong style={{ color: rareCol }}>{rarePct}%</strong> de las
          simulaciones
        </div>
        <div className="det-section-title" style={{ marginBottom: 6 }}>
          Camino en el torneo
        </div>
        <div className="path-grid">
          <TeamPathBars team={home} path={homePath} />
          <TeamPathBars team={away} path={awayPath} />
        </div>
      </div>
    </Disclosure>
  );
}

/* ── Main detail panel ─────────────────────────────────────────────────────── */

export default function DetailPanel() {
  const { selectedId, matchById, pinnedId } = useAppState();
  const dispatch = useAppDispatch();
  const closeDetail = useCallback(() => dispatch({ type: 'SELECT_MATCH', id: null }), [dispatch]);

  const m = selectedId ? matchById[selectedId] : null;
  const pinnedMatch = pinnedId ? matchById[pinnedId] : null;

  // Comparison mode: pinned match + different selected match
  if (pinnedMatch && m && pinnedMatch.match_id !== m.match_id) {
    return (
      <aside id="detail">
        <ComparisonView matchA={pinnedMatch} matchB={m} />
      </aside>
    );
  }

  if (!m) {
    return (
      <aside id="detail">
        <div id="detail-empty">
          <div className="big-icon">&#9917;</div>
          <p style={{ fontSize: 14, color: 'var(--text)', marginBottom: 4 }}>
            Selecciona un partido
          </p>
          <p>
            Haz click en cualquier partido de la lista para ver su puntaje,
            probabilidades y desglose completo.
          </p>
        </div>
      </aside>
    );
  }

  const hasSelection = !!m;

  const color = scoreColor(m.score);
  const intrinsic = m.intrinsic_score ?? 0;
  const personal = m.personal_score ?? 0;
  const isPinned = pinnedId === m.match_id;

  const handlePin = () => {
    dispatch({ type: 'PIN_MATCH', id: m.match_id });
  };

  return (
    <aside id="detail" className={hasSelection ? 'detail-open' : ''}>
      <div id="detail-match">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="det-header">
          <button className="detail-close-btn" onClick={closeDetail} aria-label="Cerrar">
            ✕
          </button>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 8,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div className="det-teams">
                {fl(m.home)} {m.home} vs {m.away} {fl(m.away)}
              </div>
              <div className="det-meta">
                {m.stage_label} &middot; {m.kickoff_local}
              </div>
              <div className="det-meta" style={{ fontSize: 10 }}>
                {m.venue}
              </div>
            </div>
            <button
              className={`btn comp-pin-btn${isPinned ? ' pinned' : ''}`}
              onClick={handlePin}
            >
              {isPinned ? '\uD83D\uDCCC Fijado' : '\uD83D\uDCCC Comparar'}
            </button>
          </div>

          {/* Narrative & archetype */}
          <div className="det-narrative">
            <span className="det-arch-badge">
              {m.archetype?.icon || ''} {m.archetype?.label || ''}
            </span>
            <p>{m.narrative || ''}</p>
          </div>

          {/* Score ring + label */}
          <ScoreRing score={m.score} label={m.label} emoji={m.emoji} />

          {/* Split bar: intrinsic vs personal */}
          <div className="det-split-bar-wrap">
            <div className="det-split-bar">
              <div
                style={{
                  width: `${intrinsic}%`,
                  background: '#3dd6c8',
                  transition: 'width 0.7s ease',
                }}
              />
              <div
                style={{
                  width: `${personal}%`,
                  background: '#d4a840',
                  transition: 'width 0.7s ease',
                }}
              />
            </div>
            <div className="det-split-nums">
              <span style={{ color: '#3dd6c8' }}>
                {typeof intrinsic === 'number' ? intrinsic.toFixed(1) : intrinsic}{' '}
                partido
              </span>
              <span style={{ color: 'var(--text-sm)' }}>=</span>
              <span style={{ color }}>{m.score}</span>
              <span style={{ color: 'var(--text-sm)' }}>=</span>
              <span style={{ color: 'var(--gold)' }}>
                +
                {typeof personal === 'number' ? personal.toFixed(1) : personal}{' '}
                tu perfil
              </span>
            </div>
          </div>

          {/* Simulated result */}
          {m.home_goals != null && m.away_goals != null && (
            <SimResult
              home={m.home}
              away={m.away}
              homeGoals={m.home_goals}
              awayGoals={m.away_goals}
              predictedWinner={m.predicted_winner}
            />
          )}
        </div>

        {/* ── Probabilities ───────────────────────────────────────── */}
        <Disclosure title="Probabilidades">
          {m.prediction && m.home !== 'TBD' && m.away !== 'TBD' ? (
            <ProbabilityBar
              prediction={m.prediction}
              home={m.home}
              away={m.away}
            />
          ) : (
            <div
              style={{
                padding: '10px 16px',
                fontSize: 11,
                color: 'var(--muted)',
              }}
            >
              Sin datos de probabilidad
            </div>
          )}
        </Disclosure>

        {/* ── Simulation path ─────────────────────────────────────── */}
        {m.rarity != null &&
          m.home_goals != null &&
          m.home_path &&
          m.away_path && (
            <SimPath
              home={m.home}
              away={m.away}
              rarity={m.rarity!}
              homePath={
                (m as unknown as { home_path: Record<string, number> })
                  .home_path
              }
              awayPath={
                (m as unknown as { away_path: Record<string, number> })
                  .away_path
              }
            />
          )}

        {/* ── H2H ─────────────────────────────────────────────────── */}
        <Disclosure title="Historial">
          <H2HSection
            home={m.home}
            away={m.away}
            h2h={m.h2h as any}
            h2hAll={m.h2h_all as any}
            h2hRecent={m.h2h_recent as any}
          />
        </Disclosure>

        {/* ── Stars ────────────────────────────────────────────────── */}
        {m.stars && m.stars.length > 0 && (
          <Disclosure title="Estrellas" count={m.stars.length}>
            <StarsSection stars={m.stars} />
          </Disclosure>
        )}

        {/* ── Contributions ───────────────────────────────────────── */}
        <Disclosure title="Contribuciones">
          <ContributionList
            breakdown={m.breakdown}
            rawByScorer={m.raw_by_scorer}
            weightByScorer={m.weight_by_scorer}
            reasonByScorer={m.reason_by_scorer}
            detailByScorer={m.detail_by_scorer}
            score={m.score}
          />
        </Disclosure>
      </div>
    </aside>
  );
}
