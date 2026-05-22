import useSWR from 'swr';
import type { Team } from '../types';
import { get } from '../api/client';

const fetcher = () => get<Team[]>('/api/teams');

export function useTeams() {
  const { data, error, isLoading } = useSWR('/api/teams', fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
  });

  return {
    teams: data ?? [],
    error,
    isLoading,
  };
}

export function usePlayers(teamCode: string | null) {
  const { data, error, isLoading } = useSWR(
    teamCode ? `/api/players/${teamCode}` : null,
    teamCode ? () => get<string[]>(`/api/players/${teamCode}`) : null,
    { revalidateOnFocus: false },
  );

  return {
    players: data ?? [],
    error,
    isLoading,
  };
}
