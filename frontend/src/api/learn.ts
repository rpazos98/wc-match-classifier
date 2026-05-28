import { get, post } from "./client";
import type {
  LearnMatchesResponse,
  FitRatingsResponse,
  LearnStateResponse,
  RatedMatch,
} from "../types";
import {
  loadRatedExamples,
  saveRatedExamples,
  loadLearnedWeights,
  saveLearnedWeights,
  loadFitMeta,
  saveFitMeta,
  resetLearnState,
} from "./storage";

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

export async function fitRatings(newRatings: RatedMatch[]): Promise<FitRatingsResponse> {
  // Accumulate with existing examples from localStorage
  const existing = loadRatedExamples();
  const allExamples = [...existing, ...newRatings];

  const result = await post<FitRatingsResponse>("/api/learn/fit-ratings", {
    ratings: allExamples,
  });

  // Persist results to localStorage
  saveRatedExamples(allExamples);
  saveLearnedWeights(result.weights);
  saveFitMeta({
    n: result.rating_stats?.n ?? allExamples.length,
    mean_rating: result.rating_stats?.mean ?? null,
    confidence: result.confidence,
    top_features: result.top_features?.map((f) => f.scorer).slice(0, 3) ?? [],
    last_fit: new Date().toISOString(),
  });

  return result;
}

export function resetRatings(): void {
  resetLearnState();
}

export function getLearnState(): LearnStateResponse {
  const examples = loadRatedExamples();
  const weights = loadLearnedWeights();
  const meta = loadFitMeta();
  return {
    n_examples: examples.length,
    has_learned: weights !== null,
    learned_weights: weights,
    default_weights: {},  // not needed for UI check
    fit_meta: meta,
    weight_delta: {},
  };
}
