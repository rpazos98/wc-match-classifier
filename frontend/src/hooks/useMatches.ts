import useSWR from 'swr';
import type { Profile } from '../types';
import { getMatches } from '../api/matches';
import { loadLearnedWeights } from '../api/storage';

export function useMatches(profile: Profile | null) {
  const key = profile ? ['matches', JSON.stringify(profile.team_affinities)] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => getMatches(profile!, loadLearnedWeights()),
    { revalidateOnFocus: false },
  );

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
