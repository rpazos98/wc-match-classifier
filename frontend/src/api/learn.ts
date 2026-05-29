import { get } from "./client";
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
import { fitFromRatings } from "../scoring/learning";

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

export function fitRatings(newRatings: RatedMatch[]): FitRatingsResponse {
  // Accumulate with existing examples from localStorage
  const existing = loadRatedExamples();
  const allExamples = [...existing, ...newRatings];

  // Run Ridge/Pearson regression client-side
  const result = fitFromRatings(allExamples);

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

  return {
    ...result,
    scorer_labels: {},
    total_examples: allExamples.length,
  };
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
    default_weights: {},
    fit_meta: meta,
    weight_delta: {},
  };
}
