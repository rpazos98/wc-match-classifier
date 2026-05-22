import type { LearnMatch } from '../../types';
import { fl } from '../../utils/flags';

interface Props {
  match: LearnMatch;
}

function parseGoals(_team: string, goalsStr: string): string[] {
  if (!goalsStr) return [];
  return goalsStr
    .split('|')
    .map((g) => {
      const parts = g.split('\u00b7'); // middle dot
      const name = parts[0].trim();
      const min = parts[1] ? parts[1].trim() + "'" : '';
      return min ? `${name} ${min}` : name;
    })
    .filter(Boolean);
}

export default function LearnMatchCard({ match }: Props) {
  const homeGoals = parseGoals(match.home, match.home_goals);
  const awayGoals = parseGoals(match.away, match.away_goals);

  return (
    <div className="learn-single-card">
      <div
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 11,
          letterSpacing: '2px',
          color: 'var(--gold)',
          marginBottom: 8,
          textAlign: 'center',
        }}
      >
        PARTIDO HISTÓRICO
      </div>

      <div className="lc-teams">
        {fl(match.home)} {match.home} vs {match.away} {fl(match.away)}
      </div>

      <div className="lc-meta">
        {match.stage_label}
        {match.venue ? ` \u00b7 ${match.venue}` : ''}
      </div>

      <div className="lc-result">{match.result}</div>

      {(homeGoals.length > 0 || awayGoals.length > 0) && (
        <div className="lc-goals">
          {homeGoals.length > 0 && (
            <div className="lc-goal-row">
              <span>{fl(match.home)}</span>
              <span style={{ color: 'var(--text)' }}>
                {homeGoals.join(' \u00b7 ')}
              </span>
            </div>
          )}
          {awayGoals.length > 0 && (
            <div className="lc-goal-row">
              <span>{fl(match.away)}</span>
              <span style={{ color: 'var(--text)' }}>
                {awayGoals.join(' \u00b7 ')}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
