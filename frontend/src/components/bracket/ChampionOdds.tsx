import type { ChampionOdds as ChampionOddsType } from '../../types';
import { fl } from '../../utils/flags';

interface Props {
  odds: ChampionOddsType[];
  nSims: number;
}

export default function ChampionOdds({ odds, nSims }: Props) {
  if (!odds.length) return null;

  const maxPct = odds[0].pct;
  const top = odds.slice(0, 15);

  return (
    <>
      <div className="bracket-section-title">
        Probabilidad de Campe&oacute;n &mdash; {nSims} simulaciones
      </div>
      <div className="champion-odds">
        {top.map(({ team, pct }) => {
          const barW = maxPct > 0 ? Math.round((pct / maxPct) * 100) : 0;
          return (
            <div className="odds-row" key={team}>
              <span className="odds-flag">{fl(team)}</span>
              <span className="odds-team">{team}</span>
              <div className="odds-bar-bg">
                <div className="odds-bar" style={{ width: `${barW}%` }} />
              </div>
              <span className="odds-pct">{Math.round(pct * 100)}%</span>
            </div>
          );
        })}
      </div>
    </>
  );
}
