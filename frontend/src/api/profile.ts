import { get, put } from "./client";
import type { Profile, ProfileInput, MatchesResponse, Team } from "../types";

export function getProfile(): Promise<Profile> {
  return get<Profile>("/api/profile");
}

/** Updates profile and returns refreshed matches (backend re-scores on save). */
export function updateProfile(profile: ProfileInput): Promise<MatchesResponse> {
  return put<MatchesResponse>("/api/profile", profile);
}

export function getTeams(): Promise<Team[]> {
  return get<Team[]>("/api/teams");
}

export function getPlayers(teamCode: string): Promise<string[]> {
  return get<string[]>(`/api/players/${teamCode}`);
}
