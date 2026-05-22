import useSWR from 'swr';
import type { MatchesResponse } from '../types';
import { get } from '../api/client';

const fetcher = () => get<MatchesResponse>('/api/matches');

export function useMatches() {
  const { data, error, isLoading, mutate } = useSWR('/api/matches', fetcher, {
    revalidateOnFocus: false,
  });

  return {
    matchData: data ?? null,
    matches: data?.matches ?? [],
    weights: data?.weights ?? {},
    defaultWeights: data?.default_weights ?? {},
    hasLearned: data?.has_learned ?? false,
    error,
    isLoading,
    refresh: mutate,
  };
}
