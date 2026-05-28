/**
 * Client-side personal scoring — computes Favorite Team, Same Group,
 * and synergy bonuses (Momento) from pre-computed match data + user profile.
 *
 * All other scorers are pre-computed server-side and loaded from static JSON.
 */

import type { Match, Profile, MatchesResponse } from "../types";

const PERSONAL_SCORERS = new Set(["Favorite Team", "Same Group", "Momento"]);

interface MatchWithGroups extends Match {
  home_group?: string | null;
  away_group?: string | null;
}

/** Favorite Team: min(1.0, hi + 0.3 * lo) */
function scoreFavoriteTeam(
  home: string,
  away: string,
  affinities: Record<string, number>,
): number {
  const aH = affinities[home] ?? 0;
  const aA = affinities[away] ?? 0;
  if (aH === 0 && aA === 0) return 0;
  const hi = Math.max(aH, aA);
  const lo = Math.min(aH, aA);
  return Math.min(1.0, hi + 0.3 * lo);
}

/** Same Group: only for group stage, scales by affinity */
function scoreSameGroup(
  match: MatchWithGroups,
  affinities: Record<string, number>,
  groups: Record<string, string>,
): number {
  if (match.stage !== "group") return 0;

  const favs = Object.entries(affinities).filter(([, a]) => a > 0);
  if (favs.length === 0) return 0;

  const home = match.home;
  const away = match.away;

  // Fav team is playing
  const playing = [home, away].filter((t) => (affinities[t] ?? 0) > 0);
  if (playing.length > 0) {
    return Math.max(...playing.map((t) => affinities[t]));
  }

  // Other teams in same group as a fav
  const favGroups = new Set(favs.map(([t]) => groups[t]).filter(Boolean));
  const matchGroups = new Set([groups[home], groups[away]].filter(Boolean));
  for (const g of matchGroups) {
    if (favGroups.has(g)) {
      const fav = favs.find(([t]) => groups[t] === g);
      return fav ? 0.7 * fav[1] : 0;
    }
  }

  return 0;
}

/**
 * Re-score matches with personal dimensions based on user profile.
 * Intrinsic scorers (Tension, Stage, Stars, Chaos, Form, Narrative) stay unchanged.
 */
export function applyPersonalScoring(
  data: MatchesResponse & { groups?: Record<string, string> },
  profile: Profile,
): MatchesResponse {
  const affinities: Record<string, number> = {};
  for (const [k, v] of Object.entries(profile.team_affinities)) {
    affinities[k.toUpperCase()] = v;
  }

  const groups = data.groups ?? {};
  const hasAffinities = Object.keys(affinities).length > 0;
  const weights = data.default_weights;

  const scored = data.matches.map((m) => {
    const match = m as MatchWithGroups;

    // Start from intrinsic score (non-personal breakdown)
    let total = 0;
    const newBreakdown = { ...match.breakdown };
    const newRaw = { ...match.raw_by_scorer };
    const newWeight = { ...match.weight_by_scorer };
    const newReason = { ...match.reason_by_scorer };
    const newDetail = { ...(match.detail_by_scorer ?? {}) };

    // Remove old personal scores
    for (const k of PERSONAL_SCORERS) {
      delete newBreakdown[k];
      delete newRaw[k];
      delete newWeight[k];
      delete newReason[k];
      delete newDetail[k];
    }
    // Also remove Espectáculo synergy key — we'll recompute
    delete newBreakdown["Espectáculo"];
    delete newRaw["Espectáculo"];

    // Sum intrinsic contributions
    for (const v of Object.values(newBreakdown)) {
      total += v;
    }

    if (hasAffinities) {
      // Favorite Team
      const favRaw = scoreFavoriteTeam(match.home, match.away, affinities);
      const favWeight = weights["Favorite Team"] ?? 0.19;
      const favContrib = favRaw * favWeight * 100;
      newRaw["Favorite Team"] = favRaw;
      newWeight["Favorite Team"] = favWeight;
      newBreakdown["Favorite Team"] = Math.round(favContrib * 10) / 10;
      total += favContrib;

      // Same Group
      const sgRaw = scoreSameGroup(match, affinities, groups);
      const sgWeight = weights["Same Group"] ?? 0.03;
      const sgContrib = sgRaw * sgWeight * 100;
      newRaw["Same Group"] = sgRaw;
      newWeight["Same Group"] = sgWeight;
      newBreakdown["Same Group"] = Math.round(sgContrib * 10) / 10;
      total += sgContrib;

      // Momento synergy: fav × stage × 8
      const stageRaw = newRaw["Match Stage"] ?? 0;
      if (favRaw > 0.3 && stageRaw > 0.35) {
        const synergy = favRaw * stageRaw * 8.0;
        newBreakdown["Momento"] = Math.round(synergy * 10) / 10;
        newRaw["Momento"] = Math.round(favRaw * stageRaw * 10000) / 10000;
        newWeight["Momento"] = 0.08;
        total += synergy;
      }
    }

    // Espectáculo synergy: tension × chaos × 6
    const tensionRaw = newRaw["Competitive Tension"] ?? 0;
    const chaosRaw = newRaw["Chaos Potential"] ?? 0;
    if (tensionRaw > 0.45 && chaosRaw > 0.45) {
      const vecer = tensionRaw * chaosRaw * 6.0;
      newBreakdown["Espectáculo"] = Math.round(vecer * 10) / 10;
      newRaw["Espectáculo"] = Math.round(tensionRaw * chaosRaw * 10000) / 10000;
      newWeight["Espectáculo"] = 0.06;
      total += vecer;
    }

    const finalScore = Math.round(Math.min(total, 100) * 10) / 10;
    const label =
      finalScore >= 60
        ? "Imperdible"
        : finalScore >= 30
          ? "Vale la pena"
          : "Para ver el resumen";
    const emoji =
      finalScore >= 60 ? "🔥" : finalScore >= 30 ? "👀" : "📋";

    const personalTotal = Math.round(
      (newBreakdown["Favorite Team"] ?? 0) +
      (newBreakdown["Same Group"] ?? 0) +
      (newBreakdown["Momento"] ?? 0),
    );

    return {
      ...match,
      score: finalScore,
      label,
      emoji,
      breakdown: newBreakdown,
      raw_by_scorer: newRaw,
      weight_by_scorer: newWeight,
      reason_by_scorer: newReason,
      detail_by_scorer: newDetail,
      intrinsic_score: Math.round((total - personalTotal) * 10) / 10,
      personal_score: personalTotal,
    };
  });

  // Sort by score descending
  scored.sort((a, b) => b.score - a.score);

  return {
    matches: scored,
    weights: data.weights,
    default_weights: data.default_weights,
    has_learned: false,
  };
}