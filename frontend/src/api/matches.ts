import { post } from "./client";
import type { Match, MatchesResponse, ScorerWeight, SimulationResponse, Profile } from "../types";

const BASE = import.meta.env.BASE_URL ?? '/';

export function getMatches(profile: Profile, learnedWeights?: Record<string, number> | null): Promise<MatchesResponse> {
  return post<MatchesResponse>("/api/matches", {
    profile,
    learned_weights: learnedWeights ?? null,
  });
}

/** Load pre-computed simulation from static JSON */
export async function loadPrecomputedSimulation(): Promise<SimulationResponse> {
  const res = await fetch(`${BASE}data/simulation.json`);
  if (!res.ok) throw new Error(`Failed to load simulation: ${res.status}`);
  return res.json();
}

/** Re-simulate via backend (slower, different seed) */
export function simulate(profile: Profile, learnedWeights?: Record<string, number> | null, seed?: number, engine?: string): Promise<SimulationResponse> {
  const body: Record<string, unknown> = { profile, learned_weights: learnedWeights ?? null };
  if (seed !== undefined) body.seed = seed;
  if (engine) body.engine = engine;
  return post<SimulationResponse>("/api/simulate", body);
}

export interface PreviewResponse {
  match: Match;
  weights: Record<string, ScorerWeight>;
  error?: string;
}

export function previewMatch(home: string, away: string, stage: string, profile: Profile, learnedWeights?: Record<string, number> | null): Promise<PreviewResponse> {
  return post<PreviewResponse>("/api/matches/preview", {
    home, away, stage,
    profile,
    learned_weights: learnedWeights ?? null,
  });
}
