import { get } from "./client";
import type { Profile, Team } from "../types";
import { loadProfile, saveProfile } from "./storage";

export function getProfile(): Profile {
  return loadProfile();
}

export function updateProfile(profile: Profile): void {
  saveProfile(profile);
}

export function getTeams(): Promise<Team[]> {
  return get<Team[]>("/api/teams");
}
