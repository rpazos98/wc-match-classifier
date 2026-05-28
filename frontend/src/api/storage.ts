import type { Profile, RatedMatch, FitMeta } from "../types";

const KEYS = {
  profile: "wc26_profile",
  ratedExamples: "wc26_rated_examples",
  learnedWeights: "wc26_learned_weights",
  fitMeta: "wc26_fit_meta",
} as const;

const DEFAULT_PROFILE: Profile = {
  name: "Fan Demo",
  team_affinities: {},
  time_windows: [],
};

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write<T>(key: string, val: T): void {
  localStorage.setItem(key, JSON.stringify(val));
}

// ── Profile ──────────────────────────────────────────────────────────────────

export function loadProfile(): Profile {
  return read<Profile>(KEYS.profile) ?? DEFAULT_PROFILE;
}

export function saveProfile(p: Profile): void {
  write(KEYS.profile, p);
}

// ── Learning state ───────────────────────────────────────────────────────────

export function loadRatedExamples(): RatedMatch[] {
  return read<RatedMatch[]>(KEYS.ratedExamples) ?? [];
}

export function saveRatedExamples(examples: RatedMatch[]): void {
  write(KEYS.ratedExamples, examples);
}

export function loadLearnedWeights(): Record<string, number> | null {
  return read<Record<string, number>>(KEYS.learnedWeights);
}

export function saveLearnedWeights(w: Record<string, number> | null): void {
  if (w) write(KEYS.learnedWeights, w);
  else localStorage.removeItem(KEYS.learnedWeights);
}

export function loadFitMeta(): FitMeta | null {
  return read<FitMeta>(KEYS.fitMeta);
}

export function saveFitMeta(m: FitMeta | null): void {
  if (m) write(KEYS.fitMeta, m);
  else localStorage.removeItem(KEYS.fitMeta);
}

export function resetLearnState(): void {
  localStorage.removeItem(KEYS.ratedExamples);
  localStorage.removeItem(KEYS.learnedWeights);
  localStorage.removeItem(KEYS.fitMeta);
}
