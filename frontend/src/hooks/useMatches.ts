import useSWR from 'swr';
import type { MatchesResponse, Profile } from '../types';
import { applyPersonalScoring } from '../scoring/personal';

const BASE = import.meta.env.BASE_URL ?? '/';

async function fetchPrecomputed(): Promise<MatchesResponse & { groups?: Record<string, string> }> {
  const res = await fetch(`${BASE}data/matches.json`);
  if (!res.ok) throw new Error(`Failed to load matches: ${res.status}`);
  return res.json();
}

export function useMatches(profile: Profile | null) {
  const { data: raw, error, isLoading, mutate } = useSWR(
    'precomputed-matches',
    fetchPrecomputed,
    { revalidateOnFocus: false },
  );

  // Apply personal scoring whenever raw data or profile changes
  const matchData = raw && profile
    ? applyPersonalScoring(raw, profile)
    : raw ?? null;

  return {
    matchData,
    matches: matchData?.matches ?? [],
    weights: matchData?.weights ?? {},
    defaultWeights: matchData?.default_weights ?? {},
    hasLearned: matchData?.has_learned ?? false,
    groups: raw?.groups ?? null,
    error,
    isLoading,
    refresh: mutate,
  };
}
