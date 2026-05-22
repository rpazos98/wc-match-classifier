import { get, post } from "./client";
import type { MatchesResponse, SimulationResponse } from "../types";

export function getMatches(): Promise<MatchesResponse> {
  return get<MatchesResponse>("/api/matches");
}

export function simulate(seed?: number): Promise<SimulationResponse> {
  return post<SimulationResponse>("/api/simulate", seed !== undefined ? { seed } : {});
}
