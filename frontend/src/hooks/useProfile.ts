import useSWR from 'swr';
import type { Profile } from '../types';
import { get } from '../api/client';

const fetcher = () => get<Profile>('/api/profile');

export function useProfile() {
  const { data, error, isLoading, mutate } = useSWR('/api/profile', fetcher, {
    revalidateOnFocus: false,
  });

  return {
    profile: data ?? null,
    error,
    isLoading,
    refresh: mutate,
  };
}
