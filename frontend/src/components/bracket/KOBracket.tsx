import type { BracketRound, BracketMatch } from '../../types';
import { fl } from '../../utils/flags';
import KOMatch from './KOMatch';

interface Props {
  rounds: BracketRound[];
  champion: string;
  runnerUp: string;
  thirdPlace: string;
}

/** Placeholder for a TBD match slot. */
function TBDMatch() {
  return (
    <div className="ko-match" style={{ opacity: 0.3 }}>
      <div className="ko-team">
        <span className="ko-team-name">TBD</span>
      </div>
      <div className="ko-team">
        <span className="ko-team-name">TBD</span>
      </div>
    </div>
  );
}

/**
 * Build a column of matches for a single KO round.
 * pairSize groups consecutive matches visually (usually 2).
 */
function RoundColumn({
  title,
  matches,
  pairSize,
}: {
  title: string;
  matches: (BracketMatch | undefined)[];
  pairSize: number;
}) {
  const pairs: (BracketMatch | undefined)[][] = [];
  for (let i = 0; i < matches.length; i += pairSize) {
    pairs.push(matches.slice(i, i + pairSize));
  }

  return (
    <div className="ko-round">
      <div className="ko-round-title">{title}</div>
      <div className="ko-slots">
        {pairs.map((pair, pi) => (
          <div className="ko-pair" key={pi} style={{ flex: pairSize }}>
            {pair.map((m, mi) =>
              m ? (
                <KOMatch match={m} key={m.match_num} />
              ) : (
                <TBDMatch key={`tbd-${pi}-${mi}`} />
              ),
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Match number ranges following the WC 2026 48-team format
const R32_NUMS = [73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88];
const R16_NUMS = [89,90,91,92,93,94,95,96];
const QF_NUMS  = [97,98,99,100];
const SF_NUMS  = [101,102];
const FINAL_NUM = 104;
const THIRD_NUM = 103;

export default function KOBracket({ rounds, champion, runnerUp, thirdPlace }: Props) {
  // Build lookup: match_num -> match
  const byNum: Record<number, BracketMatch> = {};
  for (const round of rounds) {
    for (const m of round.matches) {
      byNum[m.match_num] = m;
    }
  }

  const pick = (nums: number[]) => nums.map((n) => byNum[n]);
  const fin = byNum[FINAL_NUM];
  const trd = byNum[THIRD_NUM];

  return (
    <>
      <div className="bracket-section-title">Fase Eliminatoria</div>
      <div className="ko-bracket">
        <RoundColumn title="Ronda 32" matches={pick(R32_NUMS)} pairSize={2} />
        <RoundColumn title="16vos" matches={pick(R16_NUMS)} pairSize={2} />
        <RoundColumn title="Cuartos" matches={pick(QF_NUMS)} pairSize={2} />
        <RoundColumn title="Semis" matches={pick(SF_NUMS)} pairSize={2} />

        {/* Final + Champion card */}
        <div className="ko-round" style={{ minWidth: 160 }}>
          <div className="ko-round-title">Gran Final</div>
          <div className="ko-slots">
            <div
              className="ko-pair"
              style={{ flex: 1, justifyContent: 'center' }}
            >
              {fin ? <KOMatch match={fin} /> : <TBDMatch />}

              {fin && (
                <div className="champion-card">
                  <div className="champion-trophy">&#127942;</div>
                  <div className="champion-label">
                    Campe&oacute;n Mundial 2026
                  </div>
                  <div className="champion-name">
                    {fl(champion)} {champion}
                  </div>
                  <div className="runner-up">
                    &#129352; {fl(runnerUp)} {runnerUp}
                  </div>
                </div>
              )}

              {trd && (
                <div className="third-place-row">
                  &#129353; {fl(thirdPlace)} {thirdPlace}{' '}
                  <span style={{ color: 'var(--text-sm)', fontSize: 10 }}>
                    3er lugar
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
