import useSWR from 'swr';
import type { MatchesResponse, Profile } from '../types';
import { applyPersonalScoring } from '../scoring/personal';

const BASE = import.meta.env.BASE_URL ?? '/';

const MD_LABELS: Record<number, string> = {
  1: 'Groups MD1',
  2: 'Groups MD2',
  3: 'Groups MD3',
};

async function fetchPrecomputed(): Promise<MatchesResponse & { groups?: Record<string, string> }> {
  const [matchRes, mdRes] = await Promise.all([
    fetch(`${BASE}data/matches.json`),
    fetch(`${BASE}data/matchdays.json`),
  ]);
  if (!matchRes.ok) throw new Error(`Failed to load matches: ${matchRes.status}`);
  const data = await matchRes.json();
  const matchdays: Record<string, number> = mdRes.ok ? await mdRes.json() : {};

  // Enrich group matches with matchday label
  for (const m of data.matches) {
    if (m.stage !== 'group') continue;
    const mn = String(parseInt(m.match_id.replace('M', ''), 10));
    const md = matchdays[mn];
    if (md && MD_LABELS[md]) {
      m.stage_label = MD_LABELS[md];
    }
  }

  return data;
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
