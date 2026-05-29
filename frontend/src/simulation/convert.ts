/**
 * Convert SerializedMonteCarloResult → SimulationResponse
 *
 * Bridges the gap between raw engine output and what the UI expects.
 */
import type { SerializedMonteCarloResult } from './worker';
import type {
  SimulationResponse,
  BracketRound,
  BracketMatch,
  GroupStanding,
  ChampionOdds,
  TeamPath,
  Match,
  ScorerWeight,
} from '../types';
import { scoreKOMatch, type ScoringData } from '../scoring/classify';

// ── Stage metadata ───────────────────────────────────────────────────────────

const STAGE_MAP: Record<string, { stage: string; stage_label: string }> = {};
for (let mn = 73; mn <= 88; mn++) STAGE_MAP[mn] = { stage: 'r32', stage_label: '16vos' };
for (let mn = 89; mn <= 96; mn++) STAGE_MAP[mn] = { stage: 'r16', stage_label: 'Octavos' };
for (let mn = 97; mn <= 100; mn++) STAGE_MAP[mn] = { stage: 'qf', stage_label: 'Cuartos' };
STAGE_MAP[101] = { stage: 'sf', stage_label: 'Semifinal' };
STAGE_MAP[102] = { stage: 'sf', stage_label: 'Semifinal' };
STAGE_MAP[103] = { stage: 'third_place', stage_label: '3er Lugar' };
STAGE_MAP[104] = { stage: 'final', stage_label: 'FINAL' };

// KO match venue/kickoff data (static from FIFA schedule)
const KO_VENUES: Record<number, { venue: string; kickoff_utc: string; kickoff_local: string }> = {
  73:  { venue: 'Estadio Azteca, CDMX',                kickoff_utc: '2026-07-04T17:00:00+00:00', kickoff_local: '04/07 17:00' },
  74:  { venue: 'Hard Rock Stadium, Miami',             kickoff_utc: '2026-07-04T20:00:00+00:00', kickoff_local: '04/07 20:00' },
  75:  { venue: 'AT&T Stadium, Dallas',                 kickoff_utc: '2026-07-04T23:00:00+00:00', kickoff_local: '04/07 23:00' },
  76:  { venue: 'SoFi Stadium, Los Angeles',            kickoff_utc: '2026-07-05T02:00:00+00:00', kickoff_local: '05/07 02:00' },
  77:  { venue: 'MetLife Stadium, New York/New Jersey',  kickoff_utc: '2026-07-05T17:00:00+00:00', kickoff_local: '05/07 17:00' },
  78:  { venue: 'NRG Stadium, Houston',                 kickoff_utc: '2026-07-05T20:00:00+00:00', kickoff_local: '05/07 20:00' },
  79:  { venue: 'Lincoln Financial Field, Philadelphia', kickoff_utc: '2026-07-05T23:00:00+00:00', kickoff_local: '05/07 23:00' },
  80:  { venue: 'BMO Stadium, Toronto',                 kickoff_utc: '2026-07-06T02:00:00+00:00', kickoff_local: '06/07 02:00' },
  81:  { venue: 'Lumen Field, Seattle',                 kickoff_utc: '2026-07-06T17:00:00+00:00', kickoff_local: '06/07 17:00' },
  82:  { venue: 'Gillette Stadium, Boston',             kickoff_utc: '2026-07-06T20:00:00+00:00', kickoff_local: '06/07 20:00' },
  83:  { venue: 'Mercedes-Benz Stadium, Atlanta',       kickoff_utc: '2026-07-06T23:00:00+00:00', kickoff_local: '06/07 23:00' },
  84:  { venue: 'BC Place, Vancouver',                  kickoff_utc: '2026-07-07T02:00:00+00:00', kickoff_local: '07/07 02:00' },
  85:  { venue: 'GEODIS Park, Nashville',               kickoff_utc: '2026-07-07T17:00:00+00:00', kickoff_local: '07/07 17:00' },
  86:  { venue: 'Arrowhead Stadium, Kansas City',       kickoff_utc: '2026-07-07T20:00:00+00:00', kickoff_local: '07/07 20:00' },
  87:  { venue: 'Levi\'s Stadium, San Francisco',       kickoff_utc: '2026-07-07T23:00:00+00:00', kickoff_local: '07/07 23:00' },
  88:  { venue: 'Mercedes-Benz Stadium, Atlanta',       kickoff_utc: '2026-07-08T02:00:00+00:00', kickoff_local: '08/07 02:00' },
  89:  { venue: 'MetLife Stadium, New York/New Jersey',  kickoff_utc: '2026-07-09T17:00:00+00:00', kickoff_local: '09/07 17:00' },
  90:  { venue: 'AT&T Stadium, Dallas',                 kickoff_utc: '2026-07-09T20:00:00+00:00', kickoff_local: '09/07 20:00' },
  91:  { venue: 'Hard Rock Stadium, Miami',             kickoff_utc: '2026-07-09T23:00:00+00:00', kickoff_local: '09/07 23:00' },
  92:  { venue: 'SoFi Stadium, Los Angeles',            kickoff_utc: '2026-07-10T02:00:00+00:00', kickoff_local: '10/07 02:00' },
  93:  { venue: 'Estadio Azteca, CDMX',                kickoff_utc: '2026-07-10T17:00:00+00:00', kickoff_local: '10/07 17:00' },
  94:  { venue: 'NRG Stadium, Houston',                 kickoff_utc: '2026-07-10T20:00:00+00:00', kickoff_local: '10/07 20:00' },
  95:  { venue: 'Lincoln Financial Field, Philadelphia', kickoff_utc: '2026-07-10T23:00:00+00:00', kickoff_local: '10/07 23:00' },
  96:  { venue: 'BMO Stadium, Toronto',                 kickoff_utc: '2026-07-11T02:00:00+00:00', kickoff_local: '11/07 02:00' },
  97:  { venue: 'MetLife Stadium, New York/New Jersey',  kickoff_utc: '2026-07-12T17:00:00+00:00', kickoff_local: '12/07 17:00' },
  98:  { venue: 'AT&T Stadium, Dallas',                 kickoff_utc: '2026-07-12T21:00:00+00:00', kickoff_local: '12/07 21:00' },
  99:  { venue: 'Hard Rock Stadium, Miami',             kickoff_utc: '2026-07-13T17:00:00+00:00', kickoff_local: '13/07 17:00' },
  100: { venue: 'SoFi Stadium, Los Angeles',            kickoff_utc: '2026-07-13T21:00:00+00:00', kickoff_local: '13/07 21:00' },
  101: { venue: 'MetLife Stadium, New York/New Jersey',  kickoff_utc: '2026-07-15T21:00:00+00:00', kickoff_local: '15/07 21:00' },
  102: { venue: 'AT&T Stadium, Dallas',                 kickoff_utc: '2026-07-16T21:00:00+00:00', kickoff_local: '16/07 21:00' },
  103: { venue: 'Hard Rock Stadium, Miami',             kickoff_utc: '2026-07-18T21:00:00+00:00', kickoff_local: '18/07 21:00' },
  104: { venue: 'MetLife Stadium, New York/New Jersey',  kickoff_utc: '2026-07-19T19:00:00+00:00', kickoff_local: '19/07 19:00' },
};

const ROUND_LABELS: Array<{ label: string; range: [number, number] }> = [
  { label: '16VOS', range: [73, 88] },
  { label: 'OCTAVOS', range: [89, 96] },
  { label: 'CUARTOS', range: [97, 100] },
  { label: 'SEMIFINALES', range: [101, 102] },
  { label: 'TERCER LUGAR', range: [103, 103] },
  { label: 'GRAN FINAL', range: [104, 104] },
];

/**
 * Build SimulationResponse from engine output + existing match data.
 */
export function convertToSimulationResponse(
  mc: SerializedMonteCarloResult,
  existingGroupMatches: Match[],
  seed: number,
  weights: Record<string, ScorerWeight>,
  _defaultWeights: Record<string, number>,
  scoringData: ScoringData | null = null,
): SimulationResponse {
  const rep = mc.representative;

  // ── 1. Champion odds ───────────────────────────────────────────────────────
  const championOdds: ChampionOdds[] = Object.entries(mc.championCounts)
    .map(([team, count]) => ({ team, pct: count / mc.nSims }))
    .sort((a, b) => b.pct - a.pct);

  // ── 2. Team paths ──────────────────────────────────────────────────────────
  const teamPaths: Record<string, TeamPath> = {};
  const partCounts = mc.matchParticipantCounts;

  // Initialize all 48 teams
  const allTeams = new Set<string>();
  for (const standings of Object.values(rep.standings)) {
    for (const row of standings) allTeams.add(row.team);
  }
  for (const team of allTeams) {
    teamPaths[team] = { R32: 0, R16: 0, QF: 0, SF: 0, F: 0, Champ: 0 };
  }

  // Aggregate from participant counts
  const stageRanges: Array<{ key: string; from: number; to: number }> = [
    { key: 'R32', from: 73, to: 88 },
    { key: 'R16', from: 89, to: 96 },
    { key: 'QF', from: 97, to: 100 },
    { key: 'SF', from: 101, to: 102 },
    { key: 'F', from: 104, to: 104 },
  ];

  for (const { key, from, to } of stageRanges) {
    // For each team, max participation across matches in this stage
    const teamMax: Record<string, number> = {};
    for (let mn = from; mn <= to; mn++) {
      const counts = partCounts[mn];
      if (!counts) continue;
      for (const [team, count] of Object.entries(counts)) {
        const pct = count / mc.nSims;
        if (!teamMax[team] || pct > teamMax[team]) {
          teamMax[team] = pct;
        }
      }
    }
    for (const [team, pct] of Object.entries(teamMax)) {
      if (teamPaths[team]) teamPaths[team][key] = Math.round(pct * 1000) / 1000;
    }
  }

  // Champion probabilities
  for (const [team, count] of Object.entries(mc.championCounts)) {
    if (teamPaths[team]) teamPaths[team].Champ = Math.round((count / mc.nSims) * 1000) / 1000;
  }

  // ── 3. Standings ───────────────────────────────────────────────────────────
  // Determine which teams qualified from representative standings
  const bestThirds: Array<{ team: string; group: string; pts: number; gd: number; gf: number }> = [];
  for (const [grp, rows] of Object.entries(rep.standings)) {
    if (rows.length >= 3) {
      bestThirds.push({ ...rows[2], group: grp });
    }
  }
  bestThirds.sort((a, b) => (b.pts - a.pts) || (b.gd - a.gd) || (b.gf - a.gf));
  const qualifiedThirds = new Set(bestThirds.slice(0, 8).map(t => t.team));

  const standings: GroupStanding[] = Object.entries(rep.standings)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([group, rows]) => ({
      group,
      teams: rows.map((row, idx) => ({
        team: row.team,
        played: 3,
        won: 0, drawn: 0, lost: 0, // not tracked individually
        gf: row.gf,
        ga: 0,
        gd: row.gd,
        pts: row.pts,
        qualified: idx < 2 || qualifiedThirds.has(row.team),
        third_place: idx === 2 && qualifiedThirds.has(row.team),
      })),
    }));

  // ── 4. Bracket rounds ──────────────────────────────────────────────────────
  const bracketRounds: BracketRound[] = ROUND_LABELS.map(({ label, range }) => {
    const matches: BracketMatch[] = [];
    for (let mn = range[0]; mn <= range[1]; mn++) {
      const home = rep.matchHome?.[mn] ?? rep.matchWinners[mn] ?? 'TBD';
      const away = rep.matchAway?.[mn] ?? rep.matchLosers[mn] ?? 'TBD';
      const winner = rep.matchWinners[mn] ?? '';
      const loser = rep.matchLosers[mn] ?? '';
      const score = rep.matchScores[mn];

      // winner_prob: from matchWinnerCounts for this match
      const winnerProb: Record<string, number> = {};
      const wc = mc.matchWinnerCounts[mn];
      if (wc) {
        for (const [team, count] of Object.entries(wc)) {
          winnerProb[team] = Math.round((count / mc.nSims) * 1000) / 1000;
        }
      }

      matches.push({
        match_num: mn,
        home,
        away,
        winner,
        loser,
        is_final: mn === 104,
        is_third: mn === 103,
        winner_prob: winnerProb,
        home_goals: score ? score[0] : null,
        away_goals: score ? score[1] : null,
      });
    }
    return { label, matches };
  });

  // ── 5. Build full match list (group + KO) ──────────────────────────────────
  // Group matches: use existing scored matches, add simulated goals
  const groupMatchesOut = existingGroupMatches.map(m => {
    const mn = parseInt(m.match_id.slice(1), 10);
    const score = rep.matchScores[mn];
    const avg = mc.matchAvgGoals[mn];
    return {
      ...m,
      home_goals: score ? score[0] : null,
      away_goals: score ? score[1] : null,
      predicted_winner: rep.matchWinners[mn] ?? null,
      home_path: teamPaths[m.home] ?? null,
      away_path: teamPaths[m.away] ?? null,
      rarity: avg ? computeRarity(score, avg) : null,
    };
  });

  // KO matches: build scored Match objects
  const koMatches: Match[] = [];
  for (let mn = 73; mn <= 104; mn++) {
    const mid = `M${String(mn).padStart(3, '0')}`;
    const stageInfo = STAGE_MAP[mn];
    const venueInfo = KO_VENUES[mn] ?? { venue: '', kickoff_utc: '', kickoff_local: '' };
    const home = rep.matchHome?.[mn] ?? rep.matchWinners[mn] ?? 'TBD';
    const away = rep.matchAway?.[mn] ?? rep.matchLosers[mn] ?? 'TBD';
    const score = rep.matchScores[mn];
    const winner = rep.matchWinners[mn] ?? null;
    const avg = mc.matchAvgGoals[mn];

    // Full intrinsic scoring when data available
    const scores = scoringData
      ? scoreKOMatch(home, away, stageInfo.stage, avg, scoringData)
      : null;

    const totalScore = scores?.total ?? 0;
    const label = totalScore >= 60 ? 'Imperdible' : totalScore >= 30 ? 'Vale la pena' : 'Para ver el resumen';
    const emoji = totalScore >= 60 ? '\u{1F525}' : totalScore >= 30 ? '\u{1F440}' : '\u{1F4CB}';

    koMatches.push({
      match_id: mid,
      home,
      away,
      stage: stageInfo.stage,
      stage_label: stageInfo.stage_label,
      kickoff_utc: venueInfo.kickoff_utc,
      kickoff_local: venueInfo.kickoff_local,
      venue: venueInfo.venue,
      score: totalScore,
      label,
      emoji,
      archetype: scores?.archetype ?? null,
      narrative: scores?.narrative ?? null,
      breakdown: scores?.breakdown ?? {},
      raw_by_scorer: scores?.raw_by_scorer ?? {},
      weight_by_scorer: scores?.weight_by_scorer ?? {},
      reason_by_scorer: scores?.reason_by_scorer ?? {},
      detail_by_scorer: scores?.detail_by_scorer ?? {},
      reasons: {},
      prediction: scores?.prediction ?? null,
      intrinsic_score: totalScore,
      personal_score: 0,
      h2h: null,
      h2h_all: null,
      h2h_recent: null,
      stars: scores?.stars ?? null,
      base_score: totalScore,
      home_goals: score ? score[0] : null,
      away_goals: score ? score[1] : null,
      predicted_winner: winner,
      rarity: avg ? computeRarity(score, avg) : null,
      home_path: teamPaths[home] ?? null,
      away_path: teamPaths[away] ?? null,
    } as Match);
  }

  return {
    seed,
    n_sims: mc.nSims,
    matches: [...groupMatchesOut, ...koMatches],
    bracket_rounds: bracketRounds,
    standings,
    champion_odds: championOdds,
    team_paths: teamPaths,
    weights,
  };
}

/** Rarity: how unusual was this result compared to average? Higher = more unusual. */
function computeRarity(
  score: [number, number] | undefined,
  avg: [number, number],
): number {
  if (!score) return 0;
  const diff = Math.abs(score[0] - avg[0]) + Math.abs(score[1] - avg[1]);
  return Math.round(Math.min(1.0, diff / 3.0) * 100) / 100;
}
