import type { BracketMatch } from '../../types';
import { fl } from '../../utils/flags';

interface Props {
  match: BracketMatch;
}

function TeamRow({
  team,
  isWinner,
  prob,
  goals,
}: {
  team: string;
  isWinner: boolean;
  prob: number | null;
  goals: number | null;
}) {
  return (
    <div className={`ko-team ${isWinner ? 'winner' : 'loser'}`}>
      <span className="ko-team-flag">{fl(team)}</span>
      <span className="ko-team-name">{team}</span>
      {isWinner && <span className="ko-win-dot" />}
      {prob != null && (
        <span className="ko-prob">{Math.round(prob * 100)}%</span>
      )}
      {goals != null && <span className="ko-goals">{goals}</span>}
    </div>
  );
}

export default function KOMatch({ match }: Props) {
  const prob = match.winner_prob || {};

  return (
    <div className="ko-match">
      <TeamRow
        team={match.home}
        isWinner={match.winner === match.home}
        prob={prob[match.home] ?? null}
        goals={match.home_goals}
      />
      <TeamRow
        team={match.away}
        isWinner={match.winner === match.away}
        prob={prob[match.away] ?? null}
        goals={match.away_goals}
      />
    </div>
  );
}
