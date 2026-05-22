import { useAppState } from '../../state/AppContext';
import ChampionOdds from './ChampionOdds';
import GroupStandings from './GroupStandings';
import KOBracket from './KOBracket';

export default function BracketView() {
  const { bracketData, matches } = useAppState();

  if (!bracketData) {
    return (
      <div className="bracket-wrap">
        <p style={{ textAlign: 'center', color: 'var(--muted)', padding: 40 }}>
          Run simulation first
        </p>
      </div>
    );
  }

  const {
    champion_odds,
    standings,
    bracket_rounds,
    n_sims,
    champion,
    runner_up,
    third_place,
  } = bracketData;

  // Derive champion / runner-up / third-place from bracket data if not explicit
  const finalMatch = bracket_rounds
    .flatMap((r) => r.matches)
    .find((m) => m.is_final);
  const thirdMatch = bracket_rounds
    .flatMap((r) => r.matches)
    .find((m) => m.is_third);

  const resolvedChampion = champion ?? finalMatch?.winner ?? '';
  const resolvedRunnerUp = runner_up ?? finalMatch?.loser ?? '';
  const resolvedThird = third_place ?? thirdMatch?.winner ?? '';

  return (
    <div className="bracket-wrap">
      {champion_odds.length > 0 && (
        <ChampionOdds odds={champion_odds} nSims={n_sims} />
      )}

      {standings.length > 0 && <GroupStandings standings={standings} matches={matches} />}

      {bracket_rounds.length > 0 && (
        <KOBracket
          rounds={bracket_rounds}
          champion={resolvedChampion}
          runnerUp={resolvedRunnerUp}
          thirdPlace={resolvedThird}
        />
      )}
    </div>
  );
}
