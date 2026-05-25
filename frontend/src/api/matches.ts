import { get, post } from "./client";
import type { Match, MatchesResponse, ScorerWeight, SimulationResponse } from "../types";

export function getMatches(): Promise<MatchesResponse> {
  return get<MatchesResponse>("/api/matches");
}

export function simulate(seed?: number, engine?: string): Promise<SimulationResponse> {
  const body: Record<string, unknown> = {};
  if (seed !== undefined) body.seed = seed;
  if (engine) body.engine = engine;
  return post<SimulationResponse>("/api/simulate", body);
}

export interface PreviewResponse {
  match: Match;
  weights: Record<string, ScorerWeight>;
  error?: string;
}

export function previewMatch(home: string, away: string, stage: string): Promise<PreviewResponse> {
  return post<PreviewResponse>("/api/matches/preview", { home, away, stage });
}
