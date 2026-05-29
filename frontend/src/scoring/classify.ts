/**
 * Client-side intrinsic match scoring for KO matches.
 *
 * Ports 6 scorers from Python (Competitive Tension, Star Power,
 * Chaos Potential, Form, Narrative, Match Stage) plus Espectáculo synergy.
 *
 * Personal scorers (Favorite Team, Same Group, Momento) stay in personal.ts.
 */

import type { TeamProfile } from '../simulation/engine';

const BASE = import.meta.env.BASE_URL ?? '/';

// ── Types ────────────────────────────────────────────────────────────────────

export interface StarEntry {
  name: string;
  overall: number;
}

export interface H2HEntry {
  rivalry: number;
  drama: number;
  all_h2h: number;
  meetings: number;
}

export interface H2HRecordData {
  wc: { matches: number; a_wins: number; draws: number; b_wins: number } | null;
  all: { matches: number; a_wins: number; draws: number; b_wins: number } | null;
  recent: Array<{ date: string; tournament: string; a_goals: number; b_goals: number }> | null;
}

export interface ScoringData {
  profiles: Record<string, TeamProfile>;
  teamStars: Record<string, StarEntry[]>;
  h2h: Record<string, H2HEntry>;
  h2hRecords: Record<string, H2HRecordData>;
}

export interface IntrinsicScores {
  breakdown: Record<string, number>;
  raw_by_scorer: Record<string, number>;
  weight_by_scorer: Record<string, number>;
  reason_by_scorer: Record<string, string>;
  detail_by_scorer: Record<string, string>;
  prediction: Record<string, number> | null;
  stars: Array<{ name: string; team: string; overall: number }> | null;
  archetype: { key: string; icon: string; label: string } | null;
  narrative: string | null;
  h2h: { matches: number; a_wins: number; draws: number; b_wins: number } | null;
  h2hAll: { matches: number; a_wins: number; draws: number; b_wins: number } | null;
  h2hRecent: Array<{ date: string; tournament: string; a_goals: number; b_goals: number }> | null;
  total: number;
}

// ── Constants ────────────────────────────────────────────────────────────────

const WEIGHTS: Record<string, number> = {
  'Competitive Tension': 0.18,
  'Star Power': 0.17,
  'Match Stage': 0.17,
  'Chaos Potential': 0.12,
  'Form': 0.08,
  'Narrative': 0.06,
};

const STAGE_RAW: Record<string, number> = {
  r32: 0.40,
  r16: 0.55,
  qf: 0.75,
  sf: 0.90,
  third_place: 0.60,
  final: 1.00,
};

const STAGE_LABELS: Record<string, string> = {
  r32: '16vos de final',
  r16: 'Octavos de final',
  qf: 'Cuartos de final',
  sf: 'Semifinal',
  third_place: 'Tercer lugar',
  final: '¡Gran Final!',
};

const STAR_TIER_BASE = 84;
const STAR_TIER_RANGE = 7;
const ELITE_THRESHOLD = 90;
const ELITE_TIER = (ELITE_THRESHOLD - STAR_TIER_BASE) / STAR_TIER_RANGE;
const DEPTH_WEIGHTS = [0.50, 0.30, 0.20];

// ── Data loader ──────────────────────────────────────────────────────────────

export async function loadScoringData(
  profiles: Record<string, TeamProfile>,
): Promise<ScoringData> {
  const [teamStars, h2h, h2hRecords] = await Promise.all([
    fetch(`${BASE}data/team_stars.json`).then(r => r.json()),
    fetch(`${BASE}data/h2h.json`).then(r => r.json()),
    fetch(`${BASE}data/h2h_records.json`).then(r => r.json()),
  ]);

  return { profiles, teamStars, h2h, h2hRecords };
}

// ── ELO prediction (base ELO, neutral venue) ────────────────────────────────

function computePrediction(eloHome: number, eloAway: number) {
  const expHome = 1.0 / (1.0 + 10.0 ** ((eloAway - eloHome) / 400.0));
  const diff = Math.abs(eloHome - eloAway);
  const pDraw = 0.28 * Math.exp(-((diff / 200.0) ** 2));
  const pHome = expHome * (1.0 - pDraw);
  const pAway = (1.0 - expHome) * (1.0 - pDraw);

  // Shannon entropy normalized by ln(3)
  const ln3 = Math.log(3);
  let H = 0;
  for (const p of [pHome, pDraw, pAway]) {
    if (p > 0) H -= p * Math.log(p);
  }
  const entropy = H / ln3;

  const totalDec = pHome + pAway;
  const pUnderdog = totalDec > 0 ? Math.min(pHome, pAway) / totalDec : 0.5;

  return { pHome, pDraw, pAway, entropy, pUnderdog, eloHome, eloAway };
}

// ── Individual scorers ───────────────────────────────────────────────────────

function scoreCompetitiveTension(
  pred: ReturnType<typeof computePrediction>,
): [number, string] {
  const avgElo = (pred.eloHome + pred.eloAway) / 2.0;
  const prestige = Math.max(0, Math.min(1, (avgElo - 1400) / 700));
  const base = (pred.entropy ** 0.7) * (0.4 + 0.6 * prestige);

  // Vecer bonus: peak at p_underdog ≈ 0.35
  const vecerBonus = Math.max(0, 1.0 - Math.abs(pred.pUnderdog - 0.35) / 0.15) * 0.08;
  const raw = Math.min(1.0, base + vecerBonus);

  let reason = '';
  if (raw >= 0.75) reason = 'duelo de élites completamente abierto';
  else if (raw >= 0.55) reason = 'partido equilibrado de buen nivel';
  else if (raw >= 0.40) reason = 'resultado incierto';

  return [raw, reason];
}

function scoreStarPower(
  homeCode: string,
  awayCode: string,
  teamStars: Record<string, StarEntry[]>,
): [number, string, Array<{ name: string; team: string; overall: number }> | null] {
  const hStars = teamStars[homeCode] ?? [];
  const aStars = teamStars[awayCode] ?? [];

  function depth(stars: StarEntry[]): [number, number] {
    if (stars.length === 0) return [0, 0];
    const tiers = stars.map(s => (s.overall - STAR_TIER_BASE) / STAR_TIER_RANGE);
    const best = tiers[0];
    const top3 = tiers.slice(0, 3);
    let d = 0;
    let wSum = 0;
    for (let i = 0; i < top3.length; i++) {
      d += top3[i] * DEPTH_WEIGHTS[i];
      wSum += DEPTH_WEIGHTS[i];
    }
    return [d / wSum, best];
  }

  const [depthH, bestH] = depth(hStars);
  const [depthA, bestA] = depth(aStars);

  if (depthH === 0 && depthA === 0) return [0, '', null];

  let raw = (depthH + depthA) / 2.0;
  const bothElite = bestH >= ELITE_TIER && bestA >= ELITE_TIER;
  if (bothElite) raw = Math.min(1.0, raw * 1.4);

  // Build stars list for Match type
  const allStars = [
    ...hStars.map(s => ({ name: s.name, team: homeCode, overall: s.overall })),
    ...aStars.map(s => ({ name: s.name, team: awayCode, overall: s.overall })),
  ];

  const display = [...hStars, ...aStars].slice(0, 4).map(s => s.name);
  const suffix = hStars.length + aStars.length > 4 ? ' y más' : '';

  let reason: string;
  if (bothElite) {
    reason = 'Duelo de estrellas: ' + display.slice(0, 2).join(' vs ');
    if (display.length > 2) reason += ' + ' + display.slice(2).join(', ') + suffix;
  } else {
    reason = display.join(', ') + suffix + ' en la cancha';
  }

  return [raw, reason, allStars];
}

function scoreChaosPotential(
  homeCode: string,
  awayCode: string,
  avgGoals: [number, number] | undefined,
  profiles: Record<string, TeamProfile>,
): [number, string] {
  // Prefer predicted goals from simulation
  if (avgGoals) {
    const total = avgGoals[0] + avgGoals[1];
    const raw = Math.min(total / 5.0, 1.0);
    const hg = Math.round(avgGoals[0] * 10) / 10;
    const ag = Math.round(avgGoals[1] * 10) / 10;
    const totalR = Math.round(total * 10) / 10;
    const scoreStr = `promedio ${hg}-${ag} (${totalR} goles/partido)`;
    if (total >= 4.5) return [raw, `Partido caótico: ${scoreStr}`];
    if (total >= 3) return [raw, `Partido abierto: ${scoreStr}`];
    if (total >= 2) return [raw, `Llegadas de ambos lados: ${scoreStr}`];
    return [raw, `Partido cerrado: ${scoreStr}`];
  }

  // Fallback: attack/defense from profiles
  const pH = profiles[homeCode];
  const pA = profiles[awayCode];
  if (!pH || !pA) return [0.5, ''];

  const avgAtk = (pH.attack + pA.attack) / 2;
  const avgDfn = (pH.defense + pA.defense) / 2;
  const fragility = 1.0 - avgDfn;
  const raw = Math.min(1.0, (avgAtk * 2 + fragility + avgAtk * fragility) / 4.0);

  if (raw >= 0.75) return [raw, 'Dos equipos con vocación ofensiva y defensas permeables — partido abierto'];
  if (raw >= 0.55) return [raw, 'Buen potencial ofensivo — se esperan llegadas'];
  return [raw, ''];
}

function scoreForm(
  homeCode: string,
  awayCode: string,
  profiles: Record<string, TeamProfile>,
): [number, string] {
  const teams = [homeCode, awayCode].filter(t => profiles[t]);
  if (teams.length === 0) return [0.5, ''];

  const norms = teams.map(t => (profiles[t].form + 1.0) / 2.0);
  const raw = (norms.reduce((a, b) => a + b, 0) + Math.max(...norms)) / (norms.length + 1);

  const hot = teams.filter((_t, i) => norms[i] >= 0.65);
  if (hot.length > 0) {
    return [raw, `${hot.join(' y ')} en gran momento de forma`];
  }
  return [raw, ''];
}

function scoreNarrative(
  homeCode: string,
  awayCode: string,
  h2h: Record<string, H2HEntry>,
): [number, string] {
  const key = [homeCode, awayCode].sort().join('-');
  const entry = h2h[key];
  if (!entry) return [0, ''];

  const raw = Math.min(1.0, 0.55 * entry.rivalry + 0.30 * entry.drama + 0.15 * entry.all_h2h);
  if (raw < 0.10) return [0, ''];

  let label: string;
  if (raw >= 0.70) label = 'clásico histórico del Mundial';
  else if (raw >= 0.50) label = 'rivalidad histórica';
  else if (raw >= 0.25) label = 'historia en el fútbol internacional';
  else label = 'se han enfrentado antes';

  let dramaNot = '';
  if (entry.drama >= 0.7) dramaNot = ' — historial de partidos dramáticos';
  else if (entry.drama >= 0.4) dramaNot = ' — encuentros intensos';

  const reason = entry.meetings >= 3
    ? `${homeCode} vs ${awayCode} — ${label} (${entry.meetings} duelos en el Mundial)${dramaNot}`
    : `${homeCode} vs ${awayCode} — ${label}${dramaNot}`;

  return [raw, reason];
}

function scoreMatchStage(stage: string): [number, string] {
  const raw = STAGE_RAW[stage] ?? 0.5;
  const label = STAGE_LABELS[stage] ?? stage;
  return [raw, label];
}

// ── Archetype & narrative ────────────────────────────────────────────────────

const STAGE_NARRATIVE: Record<string, string> = {
  group: 'fase de grupos',
  r32: '16vos de final',
  r16: 'octavos de final',
  qf: 'cuartos de final',
  sf: 'semifinal',
  third_place: 'tercer lugar',
  final: 'la gran final',
};

function matchArchetype(
  raw: Record<string, number>,
  _entropy: number,
): { key: string; icon: string; label: string } {
  const tension = raw['Competitive Tension'] ?? 0;
  const chaos = raw['Chaos Potential'] ?? 0;
  const stage = raw['Match Stage'] ?? 0;
  const narr = raw['Narrative'] ?? 0;
  const stars = raw['Star Power'] ?? 0;

  const archetypes: Array<[string, string, string, number]> = [];

  if (stage >= 0.7)
    archetypes.push(['decisive', '\u{1F525}', 'Partido decisivo', stage]);
  if (tension >= 0.55 && chaos >= 0.55)
    archetypes.push(['spectacle', '\u{1F3AD}', 'Espectáculo asegurado', (tension + chaos) / 2]);
  if (chaos >= 0.6)
    archetypes.push(['chaos', '\u26A1', 'Partido abierto', chaos]);
  if (narr >= 0.4)
    archetypes.push(['rivalry', '\u2694\uFE0F', 'Clásico con historia', narr]);
  if (stars >= 0.5)
    archetypes.push(['showcase', '\u{1F451}', 'Exhibición de estrellas', stars]);
  if (tension >= 0.7 && chaos < 0.55)
    archetypes.push(['tactical', '\u{1F9E0}', 'Duelo táctico', tension]);

  if (archetypes.length > 0) {
    const best = archetypes.reduce((a, b) => (b[3] > a[3] ? b : a));
    return { key: best[0], icon: best[1], label: best[2] };
  }

  if (tension >= 0.6)
    return { key: 'balanced', icon: '\u2696\uFE0F', label: 'Partido equilibrado' };
  return { key: 'standard', icon: '\u26BD', label: 'Partido de grupo' };
}

function matchNarrative(
  home: string,
  away: string,
  stage: string,
  raw: Record<string, number>,
  entropy: number,
): string {
  const tension = raw['Competitive Tension'] ?? 0;
  const chaos = raw['Chaos Potential'] ?? 0;
  const stageRaw = raw['Match Stage'] ?? 0;
  const narr = raw['Narrative'] ?? 0;
  const stageName = STAGE_NARRATIVE[stage] ?? stage;

  const parts: string[] = [];

  if (stageRaw >= 0.75)
    parts.push(`Partido de ${stageName} con todo en juego.`);
  else if (stageRaw >= 0.35)
    parts.push(`Encuentro de ${stageName} con implicaciones en la tabla.`);
  else
    parts.push(`Duelo de ${stageName}.`);

  if (tension >= 0.55 && chaos >= 0.55)
    parts.push('Parejo y con goles esperados \u2014 la combinación que más emoción genera.');
  else if (tension >= 0.7)
    parts.push('Equipos muy parejos \u2014 resultado completamente abierto.');
  else if (chaos >= 0.6)
    parts.push('Partido abierto donde se esperan goles.');
  else if (entropy < 0.6)
    parts.push('Un favorito claro, pero el fútbol siempre sorprende.');

  if (narr >= 0.5)
    parts.push(`Historia previa entre ${home} y ${away} añade tensión.`);

  return parts.join(' ');
}

// ── Main scoring function ────────────────────────────────────────────────────

export function scoreKOMatch(
  homeCode: string,
  awayCode: string,
  stage: string,
  avgGoals: [number, number] | undefined,
  data: ScoringData,
): IntrinsicScores {
  const { profiles, teamStars, h2h } = data;

  const eloH = profiles[homeCode]?.elo ?? 1500;
  const eloA = profiles[awayCode]?.elo ?? 1500;
  const pred = computePrediction(eloH, eloA);

  // Compute all scorers
  const [tensionRaw, tensionReason] = scoreCompetitiveTension(pred);
  const [starRaw, starReason, starsArr] = scoreStarPower(homeCode, awayCode, teamStars);
  const [chaosRaw, chaosReason] = scoreChaosPotential(homeCode, awayCode, avgGoals, profiles);
  const [formRaw, formReason] = scoreForm(homeCode, awayCode, profiles);
  const [narrativeRaw, narrativeReason] = scoreNarrative(homeCode, awayCode, h2h);
  const [stageRaw, stageReason] = scoreMatchStage(stage);

  const scorers: Array<[string, number, string]> = [
    ['Competitive Tension', tensionRaw, tensionReason ? `${homeCode} vs ${awayCode} — ${tensionReason}` : ''],
    ['Star Power', starRaw, starReason],
    ['Chaos Potential', chaosRaw, chaosReason],
    ['Form', formRaw, formReason],
    ['Narrative', narrativeRaw, narrativeReason],
    ['Match Stage', stageRaw, stageReason],
  ];

  const breakdown: Record<string, number> = {};
  const raw_by_scorer: Record<string, number> = {};
  const weight_by_scorer: Record<string, number> = {};
  const reason_by_scorer: Record<string, string> = {};
  let total = 0;

  for (const [name, raw, reason] of scorers) {
    const w = WEIGHTS[name] ?? 0.10;
    const contrib = raw * w * 100;
    breakdown[name] = Math.round(contrib * 10) / 10;
    raw_by_scorer[name] = raw;
    weight_by_scorer[name] = w;
    reason_by_scorer[name] = reason;
    total += contrib;
  }

  // Espectáculo synergy: close + high-scoring
  if (tensionRaw > 0.45 && chaosRaw > 0.45) {
    const vecer = tensionRaw * chaosRaw * 6.0;
    total += vecer;
    breakdown['Espectáculo'] = Math.round(vecer * 10) / 10;
    raw_by_scorer['Espectáculo'] = Math.round(tensionRaw * chaosRaw * 10000) / 10000;
    weight_by_scorer['Espectáculo'] = 0.06;
    reason_by_scorer['Espectáculo'] = 'Partido cerrado y con goles — alto potencial de emoción';
  }

  const prediction = {
    p_home: Math.round(pred.pHome * 1000) / 1000,
    p_draw: Math.round(pred.pDraw * 1000) / 1000,
    p_away: Math.round(pred.pAway * 1000) / 1000,
    elo_home: Math.round(pred.eloHome),
    elo_away: Math.round(pred.eloAway),
    entropy: Math.round(pred.entropy * 1000) / 1000,
  };

  const archetype = matchArchetype(raw_by_scorer, pred.entropy);
  const narrative = matchNarrative(homeCode, awayCode, stage, raw_by_scorer, pred.entropy);

  // H2H records lookup — key is sorted pair, but records are stored home=first alphabetically
  const h2hKey = [homeCode, awayCode].sort().join('-');
  const h2hRec = data.h2hRecords[h2hKey];
  // If home team is NOT the first alphabetically, swap a_wins/b_wins
  const isSwapped = homeCode > awayCode;
  const swapRecord = (r: { matches: number; a_wins: number; draws: number; b_wins: number } | null) =>
    r && isSwapped ? { ...r, a_wins: r.b_wins, b_wins: r.a_wins } : r;

  return {
    breakdown,
    raw_by_scorer,
    weight_by_scorer,
    reason_by_scorer,
    detail_by_scorer: {},
    prediction,
    stars: starsArr,
    archetype,
    narrative,
    h2h: swapRecord(h2hRec?.wc ?? null),
    h2hAll: swapRecord(h2hRec?.all ?? null),
    h2hRecent: h2hRec?.recent
      ? h2hRec.recent.map(r => isSwapped ? { ...r, a_goals: r.b_goals, b_goals: r.a_goals } : r)
      : null,
    total: Math.round(Math.min(total, 100) * 10) / 10,
  };
}
