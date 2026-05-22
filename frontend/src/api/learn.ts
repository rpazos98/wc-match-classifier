import { get, post, del } from "./client";
import type {
  LearnMatchesResponse,
  FitRatingsResponse,
  ResetRatingsResponse,
  LearnStateResponse,
  RatedMatch,
} from "../types";

export interface LearnMatchesParams {
  n?: number;
  seed?: number;
  exclude?: string;
  years?: string;
}

export function getLearnMatches(params?: LearnMatchesParams): Promise<LearnMatchesResponse> {
  return get<LearnMatchesResponse>("/api/learn/matches", {
    n: params?.n,
    seed: params?.seed,
    exclude: params?.exclude,
    years: params?.years,
  });
}

export function fitRatings(ratings: RatedMatch[]): Promise<FitRatingsResponse> {
  return post<FitRatingsResponse>("/api/learn/fit-ratings", { ratings });
}

export function resetRatings(): Promise<ResetRatingsResponse> {
  return del<ResetRatingsResponse>("/api/learn/ratings");
}

export function getLearnState(): Promise<LearnStateResponse> {
  return get<LearnStateResponse>("/api/learn/state");
}
