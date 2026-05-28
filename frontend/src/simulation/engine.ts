/**
 * WC 2026 Monte Carlo Bracket Simulation — TypeScript port.
 *
 * Performance-first design:
 *   - mulberry32 PRNG (fast, seeded, no allocation)
 *   - Pre-computed Poisson PMF tables (avoid exp/factorial per sample)
 *   - Flat arrays for standings (no object alloc in hot path)
 *   - Inlined math on hot paths
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface TeamProfile {
  elo: number;
  quality: number;
  form: number;
  attack: number;
  defense: number;
  confederation: string;
}

export interface GroupMatch {
  match_id: string;
  home: string;
  away: string;
}

export type SimEngine = 'classic' | 'fte538';

export interface SimulationResult {
  matchWinners: Map<number, string>;
  matchLosers: Map<number, string>;
  matchScores: Map<number, [number, number]>;
  standings: Map<string, StandingRow[]>;
}

export interface StandingRow {
  team: string;
  pts: number;
  gd: number;
  gf: number;
}

export interface MonteCarloResult {
  nSims: number;
  championCounts: Map<string, number>;
  finalistCounts: Map<string, number>;
  semifinalCounts: Map<string, number>;
  matchWinnerCounts: Map<number, Map<string, number>>;
  matchParticipantCounts: Map<number, Map<string, number>>;
  matchAvgGoals: Map<number, [number, number]>;
  representative: SimulationResult;
}

// ── Constants ────────────────────────────────────────────────────────────────

const HOST_CODES = new Set(['USA', 'CAN', 'MEX']);
const HOST_CONFEDERATION = 'CONCACAF';
const HOST_ELO_BOOST = 60.0;
const CONFED_ELO_BOOST = 20.0;
const DRAW_INFLATION = 0.09;
const MAX_GOALS = 8; // score matrix size (0..8)

// R32 slot definitions: match_num → [home_slot, away_slot]
// Slot: ["W"|"RU", group] or ["T3", allowed_groups_string]
type Slot = [string, string];

const R32_SLOTS: Record<number, [Slot, Slot]> = {
  73: [['RU', 'A'], ['RU', 'B']],
  74: [['W', 'C'], ['RU', 'F']],
  75: [['W', 'E'], ['T3', 'ABCDF']],
  76: [['W', 'F'], ['RU', 'C']],
  77: [['RU', 'E'], ['RU', 'I']],
  78: [['W', 'I'], ['T3', 'CDFGH']],
  79: [['W', 'A'], ['T3', 'CEFHI']],
  80: [['W', 'L'], ['T3', 'EHIJK']],
  81: [['W', 'G'], ['T3', 'AEHIJ']],
  82: [['W', 'D'], ['T3', 'BEFIJ']],
  83: [['W', 'H'], ['RU', 'J']],
  84: [['RU', 'K'], ['RU', 'L']],
  85: [['W', 'B'], ['T3', 'EFGIJ']],
  86: [['RU', 'D'], ['RU', 'G']],
  87: [['W', 'J'], ['RU', 'H']],
  88: [['W', 'K'], ['T3', 'DEIJL']],
};

const R16_FEEDS: Record<number, [number, number]> = {
  89: [73, 75], 90: [74, 77], 91: [76, 78], 92: [79, 80],
  93: [83, 84], 94: [81, 82], 95: [86, 88], 96: [85, 87],
};

const QF_FEEDS: Record<number, [number, number]> = {
  97: [89, 90], 98: [93, 94], 99: [91, 92], 100: [95, 96],
};

const SF_FEEDS: Record<number, [number, number]> = {
  101: [97, 98], 102: [99, 100],
};

const T3_SLOT_MATCH_NUMS = [75, 78, 79, 80, 81, 82, 85, 88]; // sorted

const R32_MATCH_NUMS = [73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88];

// Round weights for representative selection
const ROUND_WEIGHTS: Record<number, number> = {};
for (let mn = 73; mn <= 88; mn++) ROUND_WEIGHTS[mn] = 1.0;
for (let mn = 89; mn <= 96; mn++) ROUND_WEIGHTS[mn] = 1.5;
for (let mn = 97; mn <= 100; mn++) ROUND_WEIGHTS[mn] = 2.0;
ROUND_WEIGHTS[101] = 3.0;
ROUND_WEIGHTS[102] = 3.0;
ROUND_WEIGHTS[103] = 1.5;
ROUND_WEIGHTS[104] = 5.0;

// ── PRNG: mulberry32 (fast, seedable, 32-bit) ───────────────────────────────

function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Pre-computed Poisson PMF table ───────────────────────────────────────────
// For λ values from 0.20 to 3.00 in 0.01 steps, pre-compute PMF(k) for k=0..8.
// Avoids exp/factorial calls in the hot loop.

const LAMBDA_MIN = 0.20;
const LAMBDA_STEP = 0.01;
const LAMBDA_COUNT = 281; // 0.20..3.00 inclusive

// PMF table: [lambda_index][k] → probability
const PMF_TABLE: Float64Array[] = new Array(LAMBDA_COUNT);

function initPmfTable(): void {
  for (let li = 0; li < LAMBDA_COUNT; li++) {
    const lam = LAMBDA_MIN + li * LAMBDA_STEP;
    const row = new Float64Array(MAX_GOALS + 1);
    const expNegLam = Math.exp(-lam);
    let lamPow = 1.0;
    let fact = 1;
    for (let k = 0; k <= MAX_GOALS; k++) {
      if (k > 0) {
        lamPow *= lam;
        fact *= k;
      }
      row[k] = lamPow * expNegLam / fact;
    }
    PMF_TABLE[li] = row;
  }
}
initPmfTable();

function getPmfRow(lam: number): Float64Array {
  const idx = Math.round((Math.min(3.0, Math.max(0.20, lam)) - LAMBDA_MIN) / LAMBDA_STEP);
  return PMF_TABLE[Math.min(idx, LAMBDA_COUNT - 1)];
}

// ── Core math ────────────────────────────────────────────────────────────────

function compositeElo(
  p: TeamProfile,
  isHomeHost: boolean,
): number {
  const expectedFromQuality = 1300 + p.quality * 800;
  const qualityAdj = (expectedFromQuality - p.elo) * 0.25;
  const formAdj = p.form * 50.0;
  const hostAdj = isHomeHost ? HOST_ELO_BOOST : 0.0;
  return p.elo + qualityAdj + formAdj + hostAdj;
}

function confedEloBoost(p: TeamProfile, code: string): number {
  if (HOST_CODES.has(code)) return 0.0;
  return p.confederation === HOST_CONFEDERATION ? CONFED_ELO_BOOST : 0.0;
}

/** Returns [pHome, pDraw, pAway] */
function compositeWinProb(
  homeCode: string, awayCode: string,
  profiles: Map<string, TeamProfile>,
): [number, number, number] {
  const pH = profiles.get(homeCode)!;
  const pA = profiles.get(awayCode)!;

  const rHome = compositeElo(pH, HOST_CODES.has(homeCode));
  const rAway = compositeElo(pA, HOST_CODES.has(awayCode));

  const expHome = 1.0 / (1.0 + 10.0 ** ((rAway - rHome) / 400.0));
  const diff = Math.abs(rHome - rAway);
  const pDraw = 0.28 * Math.exp(-((diff / 200.0) ** 2));
  const pDecisive = 1.0 - pDraw;

  return [expHome * pDecisive, pDraw, (1.0 - expHome) * pDecisive];
}

/** Returns [lamHome, lamAway] for Poisson scoring */
function expectedGoals(
  homeCode: string, awayCode: string,
  profiles: Map<string, TeamProfile>,
): [number, number] {
  const pH = profiles.get(homeCode)!;
  const pA = profiles.get(awayCode)!;

  const rHome = compositeElo(pH, HOST_CODES.has(homeCode)) + confedEloBoost(pH, homeCode);
  const rAway = compositeElo(pA, HOST_CODES.has(awayCode)) + confedEloBoost(pA, awayCode);

  const base = 1.25;
  const eloAdj = (rHome - rAway) / 650.0;

  const homeAtkBonus = (pH.attack - 0.5) * 0.3;
  const homeDefPenalty = (pA.defense - 0.5) * 0.3;
  const awayAtkBonus = (pA.attack - 0.5) * 0.3;
  const awayDefPenalty = (pH.defense - 0.5) * 0.3;

  const lamHome = Math.max(0.20, Math.min(3.0, base + eloAdj + homeAtkBonus - homeDefPenalty));
  const lamAway = Math.max(0.20, Math.min(3.0, base - eloAdj + awayAtkBonus - awayDefPenalty));

  return [lamHome, lamAway];
}

// ── Poisson sampling ─────────────────────────────────────────────────────────

/** Knuth's algorithm — used for Classic engine and KO re-rolls */
function poissonSample(lam: number, rng: () => number): number {
  const L = Math.exp(-lam);
  let k = 0, p = 1.0;
  do {
    k++;
    p *= rng();
  } while (p > L);
  return k - 1;
}

/** Sample from score matrix with diagonal inflation (FTE538 group stage) */
function sampleScoreMatrix(
  lamHome: number,
  lamAway: number,
  rng: () => number,
): [number, number] {
  const pmfH = getPmfRow(lamHome);
  const pmfA = getPmfRow(lamAway);

  // Build CDF inline — avoid allocating a 9x9 matrix
  // Total probability mass = 1 + DRAW_INFLATION * sum(pmfH[k]*pmfA[k] for k=0..8)
  let drawMass = 0.0;
  for (let k = 0; k <= MAX_GOALS; k++) {
    drawMass += pmfH[k] * pmfA[k];
  }
  const total = 1.0 + DRAW_INFLATION * drawMass;

  const r = rng() * total;
  let cumul = 0.0;

  for (let h = 0; h <= MAX_GOALS; h++) {
    const ph = pmfH[h];
    for (let a = 0; a <= MAX_GOALS; a++) {
      let p = ph * pmfA[a];
      if (h === a) p *= (1.0 + DRAW_INFLATION);
      cumul += p;
      if (cumul >= r) return [h, a];
    }
  }
  return [0, 0]; // fallback
}

/** FTE538 knockout: re-roll on draws, fallback to shootout */
function simMatchPoissonKO(
  homeCode: string, awayCode: string,
  profiles: Map<string, TeamProfile>,
  rng: () => number,
): [number, number] {
  const [lamHome, lamAway] = expectedGoals(homeCode, awayCode, profiles);

  for (let i = 0; i < 100; i++) {
    const hg = poissonSample(lamHome, rng);
    const ag = poissonSample(lamAway, rng);
    if (hg !== ag) return [hg, ag];
  }

  // Penalty shootout
  if (rng() < 0.5 + (lamHome - lamAway) * 0.05) return [1, 0];
  return [0, 1];
}

// ── Classic engine helpers ───────────────────────────────────────────────────

function simScoreV2(
  winner: TeamProfile,
  loser: TeamProfile,
  rng: () => number,
): [number, number] {
  const wPower = winner.attack * (1.0 - loser.defense * 0.5);
  const lPower = loser.attack * (1.0 - winner.defense * 0.5);

  const lamLoser = 0.2 + lPower * 1.2;
  const eloGap = Math.max(0.0, (winner.elo - loser.elo) / 800.0);
  const attackEdge = Math.max(0.0, wPower - lPower);
  const lamMargin = Math.max(0.1, 0.4 + eloGap * 0.6 + attackEdge * 0.5);

  const lGoals = poissonSample(lamLoser, rng);
  const margin = 1 + poissonSample(lamMargin, rng);
  return [lGoals + margin, lGoals];
}

function simDrawScore(rng: () => number): [number, number] {
  const g = poissonSample(0.9, rng);
  return [g, g];
}

// ── Knockout simulation ──────────────────────────────────────────────────────

/** Returns [winner, loser, homeGoals, awayGoals] */
function simKO(
  homeCode: string, awayCode: string,
  profiles: Map<string, TeamProfile>,
  rng: () => number,
  engine: SimEngine,
): [string, string, number, number] {
  if (engine === 'fte538') {
    const [hg, ag] = simMatchPoissonKO(homeCode, awayCode, profiles, rng);
    return hg > ag
      ? [homeCode, awayCode, hg, ag]
      : [awayCode, homeCode, hg, ag];
  }

  // Classic
  const [pHome, , pAway] = compositeWinProb(homeCode, awayCode, profiles);
  const total = pHome + pAway;
  const pHW = total > 0 ? pHome / total : 0.5;
  const pW = profiles.get(homeCode)!;
  const pL = profiles.get(awayCode)!;

  if (rng() < pHW) {
    const [wg, lg] = simScoreV2(pW, pL, rng);
    return [homeCode, awayCode, wg, lg];
  } else {
    const [wg, lg] = simScoreV2(pL, pW, rng);
    return [awayCode, homeCode, lg, wg];
  }
}

// ── Group stage simulation ───────────────────────────────────────────────────

function simulateGroups(
  groupMatches: GroupMatch[],
  teamGroups: Record<string, string>,
  profiles: Map<string, TeamProfile>,
  rng: () => number,
  engine: SimEngine,
): { standings: Map<string, StandingRow[]>; winners: Map<number, string>; scores: Map<number, [number, number]> } {
  // Collect all teams per group
  const groupTeams = new Map<string, Set<string>>();
  for (const m of groupMatches) {
    for (const t of [m.home, m.away]) {
      if (t !== 'TBD') {
        const grp = teamGroups[t];
        if (grp) {
          let s = groupTeams.get(grp);
          if (!s) { s = new Set(); groupTeams.set(grp, s); }
          s.add(t);
        }
      }
    }
  }

  // Flat maps for pts/gd/gf
  const pts = new Map<string, number>();
  const gd = new Map<string, number>();
  const gf = new Map<string, number>();
  for (const teams of groupTeams.values()) {
    for (const t of teams) {
      pts.set(t, 0);
      gd.set(t, 0);
      gf.set(t, 0);
    }
  }

  const matchWinners = new Map<number, string>();
  const matchScores = new Map<number, [number, number]>();

  for (const m of groupMatches) {
    if (m.home === 'TBD' || m.away === 'TBD') continue;
    const mn = parseInt(m.match_id.slice(1), 10);
    let hg: number, ag: number;

    if (engine === 'fte538') {
      const [lamH, lamA] = expectedGoals(m.home, m.away, profiles);
      [hg, ag] = sampleScoreMatrix(lamH, lamA, rng);

      if (hg > ag) {
        pts.set(m.home, pts.get(m.home)! + 3);
        matchWinners.set(mn, m.home);
      } else if (hg === ag) {
        pts.set(m.home, pts.get(m.home)! + 1);
        pts.set(m.away, pts.get(m.away)! + 1);
        const [pH, , pA] = compositeWinProb(m.home, m.away, profiles);
        matchWinners.set(mn, pH >= pA ? m.home : m.away);
      } else {
        pts.set(m.away, pts.get(m.away)! + 3);
        matchWinners.set(mn, m.away);
      }
    } else {
      // Classic
      const [pHome, pDraw, ] = compositeWinProb(m.home, m.away, profiles);
      const r = rng();

      if (r < pHome) {
        [hg, ag] = simScoreV2(profiles.get(m.home)!, profiles.get(m.away)!, rng);
        pts.set(m.home, pts.get(m.home)! + 3);
        matchWinners.set(mn, m.home);
      } else if (r < pHome + pDraw) {
        [hg, ag] = simDrawScore(rng);
        pts.set(m.home, pts.get(m.home)! + 1);
        pts.set(m.away, pts.get(m.away)! + 1);
        const [pH, , pA] = compositeWinProb(m.home, m.away, profiles);
        matchWinners.set(mn, pH >= pA ? m.home : m.away);
      } else {
        [ag, hg] = simScoreV2(profiles.get(m.away)!, profiles.get(m.home)!, rng);
        pts.set(m.away, pts.get(m.away)! + 3);
        matchWinners.set(mn, m.away);
      }
    }

    gf.set(m.home, gf.get(m.home)! + hg);
    gf.set(m.away, gf.get(m.away)! + ag);
    gd.set(m.home, gd.get(m.home)! + hg - ag);
    gd.set(m.away, gd.get(m.away)! + ag - hg);
    matchScores.set(mn, [hg, ag]);
  }

  // Build sorted standings per group
  const standings = new Map<string, StandingRow[]>();
  for (const [grp, teams] of groupTeams) {
    const table = Array.from(teams).map(t => ({
      team: t,
      pts: pts.get(t)!,
      gd: gd.get(t)!,
      gf: gf.get(t)!,
    }));
    table.sort((a, b) => (b.pts - a.pts) || (b.gd - a.gd) || (b.gf - a.gf));
    standings.set(grp, table);
  }

  return { standings, winners: matchWinners, scores: matchScores };
}

// ── Full bracket simulation ──────────────────────────────────────────────────

export function simulateBracket(
  groupMatches: GroupMatch[],
  teamGroups: Record<string, string>,
  profiles: Map<string, TeamProfile>,
  seed: number,
  engine: SimEngine,
): SimulationResult {
  const rng = mulberry32(seed);

  const { standings, winners: groupWinners, scores: groupScores } = simulateGroups(
    groupMatches, teamGroups, profiles, rng, engine,
  );

  // Extract positions
  const groupW = new Map<string, string>();
  const groupRU = new Map<string, string>();
  const t3Candidates: StandingRow[] = [];

  for (const [grp, table] of standings) {
    groupW.set(grp, table[0].team);
    groupRU.set(grp, table[1].team);
    const third = table[2];
    t3Candidates.push({ ...third, team: third.team, gd: third.gd, gf: third.gf, pts: third.pts });
    // Tag group for T3 assignment
    (t3Candidates[t3Candidates.length - 1] as any)._group = grp;
  }

  // Sort T3 best-first
  t3Candidates.sort((a, b) => (b.pts - a.pts) || (b.gd - a.gd) || (b.gf - a.gf));

  // Assign T3 to slots
  const t3Assignments = new Map<number, string>();
  const availableT3 = [...t3Candidates];

  for (const mn of T3_SLOT_MATCH_NUMS) {
    const allowed = R32_SLOTS[mn][1][1]; // string of allowed group letters
    let pickIdx = availableT3.findIndex(t => allowed.includes((t as any)._group));
    if (pickIdx === -1) pickIdx = 0;
    if (availableT3.length > 0) {
      t3Assignments.set(mn, availableT3[pickIdx].team);
      availableT3.splice(pickIdx, 1);
    }
  }

  // Simulate knockout
  const matchWinners = new Map(groupWinners);
  const matchLosers = new Map<number, string>();
  const matchScores = new Map(groupScores);

  function teamForSlot(slot: Slot): string {
    const [kind, val] = slot;
    if (kind === 'W') return groupW.get(val) ?? 'TBD';
    if (kind === 'RU') return groupRU.get(val) ?? 'TBD';
    return 'TBD'; // T3 handled separately
  }

  function resolve(mn: number, home: string, away: string): void {
    const [w, l, hg, ag] = simKO(home, away, profiles, rng, engine);
    matchWinners.set(mn, w);
    matchLosers.set(mn, l);
    matchScores.set(mn, [hg, ag]);
  }

  // R32
  for (const mn of R32_MATCH_NUMS) {
    const [slotH, slotA] = R32_SLOTS[mn];
    let home = slotH[0] === 'T3' ? (t3Assignments.get(mn) ?? 'TBD') : teamForSlot(slotH);
    let away = slotA[0] === 'T3' ? (t3Assignments.get(mn) ?? 'TBD') : teamForSlot(slotA);
    resolve(mn, home, away);
  }

  // R16
  for (const mn of [89, 90, 91, 92, 93, 94, 95, 96]) {
    const [a, b] = R16_FEEDS[mn];
    resolve(mn, matchWinners.get(a)!, matchWinners.get(b)!);
  }

  // QF
  for (const mn of [97, 98, 99, 100]) {
    const [a, b] = QF_FEEDS[mn];
    resolve(mn, matchWinners.get(a)!, matchWinners.get(b)!);
  }

  // SF
  for (const mn of [101, 102]) {
    const [a, b] = SF_FEEDS[mn];
    resolve(mn, matchWinners.get(a)!, matchWinners.get(b)!);
  }

  // 3rd place
  resolve(103, matchLosers.get(101)!, matchLosers.get(102)!);

  // Final
  resolve(104, matchWinners.get(101)!, matchWinners.get(102)!);

  return { matchWinners, matchLosers, matchScores, standings };
}

// ── Monte Carlo aggregation ──────────────────────────────────────────────────

export function runMonteCarlo(
  groupMatches: GroupMatch[],
  teamGroups: Record<string, string>,
  profilesObj: Record<string, TeamProfile>,
  n: number,
  seed: number,
  engine: SimEngine,
  onProgress?: (done: number, total: number) => void,
): MonteCarloResult {
  // Convert to Map once (Map.get is faster than obj[key] in hot loops)
  const profiles = new Map<string, TeamProfile>();
  for (const [code, p] of Object.entries(profilesObj)) {
    profiles.set(code, p);
  }

  // Generate seeds
  const seedRng = mulberry32(seed);
  const seeds = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    seeds[i] = (seedRng() * 1_000_000_000) | 0;
  }

  const championCounts = new Map<string, number>();
  const finalistCounts = new Map<string, number>();
  const semifinalCounts = new Map<string, number>();
  const matchWinnerCounts = new Map<number, Map<string, number>>();
  const matchParticipantCounts = new Map<number, Map<string, number>>();
  const goalSumsH = new Map<number, number>();
  const goalSumsA = new Map<number, number>();
  const goalCounts = new Map<number, number>();

  // Store lightweight KO winners per run for representative selection
  const runKoWinners: Array<[number, Map<number, string>]> = new Array(n);

  const progressInterval = Math.max(1, Math.floor(n / 20));

  for (let i = 0; i < n; i++) {
    const result = simulateBracket(groupMatches, teamGroups, profiles, seeds[i], engine);

    // Champion
    const champion = result.matchWinners.get(104)!;
    championCounts.set(champion, (championCounts.get(champion) ?? 0) + 1);

    // Finalists
    const finalist1 = champion;
    const finalist2 = result.matchLosers.get(104)!;
    finalistCounts.set(finalist1, (finalistCounts.get(finalist1) ?? 0) + 1);
    finalistCounts.set(finalist2, (finalistCounts.get(finalist2) ?? 0) + 1);

    // Semifinalists
    for (const mn of [101, 102]) {
      const w = result.matchWinners.get(mn)!;
      const l = result.matchLosers.get(mn)!;
      semifinalCounts.set(w, (semifinalCounts.get(w) ?? 0) + 1);
      semifinalCounts.set(l, (semifinalCounts.get(l) ?? 0) + 1);
    }

    // KO match tracking
    const koWinners = new Map<number, string>();
    for (let mn = 73; mn <= 104; mn++) {
      const w = result.matchWinners.get(mn);
      if (w === undefined) continue;

      // Winner counts
      let wc = matchWinnerCounts.get(mn);
      if (!wc) { wc = new Map(); matchWinnerCounts.set(mn, wc); }
      wc.set(w, (wc.get(w) ?? 0) + 1);

      koWinners.set(mn, w);
    }

    // Participant counts for KO matches
    for (const [mn, score] of result.matchScores) {
      if (mn < 73) {
        // Group match — just accumulate goals
        goalSumsH.set(mn, (goalSumsH.get(mn) ?? 0) + score[0]);
        goalSumsA.set(mn, (goalSumsA.get(mn) ?? 0) + score[1]);
        goalCounts.set(mn, (goalCounts.get(mn) ?? 0) + 1);
        continue;
      }

      goalSumsH.set(mn, (goalSumsH.get(mn) ?? 0) + score[0]);
      goalSumsA.set(mn, (goalSumsA.get(mn) ?? 0) + score[1]);
      goalCounts.set(mn, (goalCounts.get(mn) ?? 0) + 1);
    }

    // Track participants for KO
    for (const [mn] of result.matchScores) {
      if (mn < 73) continue;
      const w = result.matchWinners.get(mn);
      const l = result.matchLosers.get(mn);
      if (w) {
        let pc = matchParticipantCounts.get(mn);
        if (!pc) { pc = new Map(); matchParticipantCounts.set(mn, pc); }
        pc.set(w, (pc.get(w) ?? 0) + 1);
        if (l) pc.set(l, (pc.get(l) ?? 0) + 1);
      }
    }

    runKoWinners[i] = [seeds[i], koWinners];

    if (onProgress && (i + 1) % progressInterval === 0) {
      onProgress(i + 1, n);
    }
  }

  // Modal champion
  let modalChampion = '';
  let maxChampCount = 0;
  for (const [team, count] of championCounts) {
    if (count > maxChampCount) {
      maxChampCount = count;
      modalChampion = team;
    }
  }

  // Filter to champion runs
  let championRuns = runKoWinners.filter(([, kw]) => kw.get(104) === modalChampion);
  if (championRuns.length === 0) championRuns = [...runKoWinners];

  // Compute modal winners within champion runs
  const champModal = new Map<number, string>();
  const champMatchCounts = new Map<number, Map<string, number>>();
  for (const [, kw] of championRuns) {
    for (const [mn, winner] of kw) {
      let mc = champMatchCounts.get(mn);
      if (!mc) { mc = new Map(); champMatchCounts.set(mn, mc); }
      mc.set(winner, (mc.get(winner) ?? 0) + 1);
    }
  }
  for (const [mn, counts] of champMatchCounts) {
    let best = '';
    let bestCount = 0;
    for (const [team, c] of counts) {
      if (c > bestCount) { bestCount = c; best = team; }
    }
    champModal.set(mn, best);
  }

  // Score each champion run by alignment with champion-path modals
  let bestSeed = championRuns[0][0];
  let bestScore = -1;
  for (const [s, kw] of championRuns) {
    let score = 0;
    for (const [mn, winner] of kw) {
      if (champModal.get(mn) === winner) {
        score += ROUND_WEIGHTS[mn] ?? 1.0;
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestSeed = s;
    }
  }

  // Re-simulate representative
  const representative = simulateBracket(groupMatches, teamGroups, profiles, bestSeed, engine);

  // Compute average goals
  const matchAvgGoals = new Map<number, [number, number]>();
  for (const [mn, cnt] of goalCounts) {
    if (cnt > 0) {
      matchAvgGoals.set(mn, [
        (goalSumsH.get(mn) ?? 0) / cnt,
        (goalSumsA.get(mn) ?? 0) / cnt,
      ]);
    }
  }

  if (onProgress) onProgress(n, n);

  return {
    nSims: n,
    championCounts,
    finalistCounts,
    semifinalCounts,
    matchWinnerCounts,
    matchParticipantCounts,
    matchAvgGoals,
    representative,
  };
}
