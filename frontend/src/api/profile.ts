import type { Profile, Team } from "../types";
import { loadProfile, saveProfile } from "./storage";

const BASE = import.meta.env.BASE_URL ?? '/';

export function getProfile(): Profile {
  return loadProfile();
}

export function updateProfile(profile: Profile): void {
  saveProfile(profile);
}

export async function getTeams(): Promise<Team[]> {
  const res = await fetch(`${BASE}data/teams.json`);
  if (!res.ok) throw new Error(`Failed to load teams: ${res.status}`);
  return res.json();
}
