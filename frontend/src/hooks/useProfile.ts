import { useState, useCallback } from 'react';
import type { Profile } from '../types';
import { loadProfile, saveProfile } from '../api/storage';

export function useProfile() {
  const [profile, setProfile] = useState<Profile>(loadProfile);

  const update = useCallback((p: Profile) => {
    saveProfile(p);
    setProfile(p);
  }, []);

  return { profile, update };
}
