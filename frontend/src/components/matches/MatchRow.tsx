import type { Match } from '../../types/index';
import { useAppState, useAppDispatch } from '../../state/AppContext';
import { fl } from '../../utils/flags';
import { rowClass, scoreColor } from '../../utils/labels';

interface Props {
  match: Match;
}

export default function MatchRow({ match: m }: Props) {
  const { selectedId, simulated, hasLearned } = useAppState();
  const dispatch = useAppDispatch();

  const rc = rowClass(m.label);
  const sel = m.match_id === selectedId ? ' sel' : '';
  const sc = scoreColor(m.score);

  const archIcon = m.archetype?.icon || m.emoji;
  const archTag = m.archetype?.label || null;

  const isKoSim = simulated && m.stage !== 'group';
  const showRare = m.rarity != null && m.rarity <= 0.1;

  const mDelta =
    hasLearned && m.base_score != null ? m.score - m.base_score : 0;
  const showDelta = hasLearned && Math.abs(mDelta) >= 1;

  const hasResult = m.home_goals != null && m.away_goals != null;

  return (
    <div
      className={`match-row ${rc}${sel}`}
      data-mid={m.match_id}
      onClick={() => dispatch({ type: 'SELECT_MATCH', id: m.match_id })}
    >
      <span className="mr-emoji">{archIcon}</span>
      <span className="mr-score" style={{ color: sc }}>
        {m.score}
      </span>
      {showDelta && (
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            fontWeight: 700,
            color: mDelta > 0 ? '#3dd6c8' : '#e06060',
            marginLeft: '2px',
          }}
        >
          {mDelta > 0 ? '+' : ''}
          {mDelta.toFixed(0)}
        </span>
      )}
      <span className="mr-teams">
        {fl(m.home)} {m.home} vs {m.away} {fl(m.away)}
      </span>
      {archTag && <span className="mr-arch">{archTag}</span>}
      {isKoSim && (
        <span className="ko-sim-badge" title="Equipos por simulaci\u00f3n">
          sim
        </span>
      )}
      {showRare && (
        <span className="rare-badge">{Math.round(m.rarity! * 100)}%</span>
      )}
      {hasResult && (
        <span className="mr-result">
          {m.home_goals} - {m.away_goals}
        </span>
      )}
      {m.predicted_winner && (
        <span className="mr-winner">
          <span className="arrow">{'\u25B6'}</span>
          {fl(m.predicted_winner)} {m.predicted_winner}
        </span>
      )}
      <span className="mr-stage">{m.stage_label}</span>
      <span className="mr-date">{m.kickoff_local}</span>
    </div>
  );
}
