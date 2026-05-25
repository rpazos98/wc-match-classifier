// ── Core domain types ────────────────────────────────────────────────────────

export interface Archetype {
  key: string;
  icon: string;
  label: string;
}

export interface H2HRecord {
  [key: string]: number | string;
}

export interface H2HRecentMatch {
  [key: string]: unknown;
}

export interface Star {
  name: string;
  team: string;
  overall: number;
}

export interface Prediction {
  entropy: number;
  [key: string]: number;
}

export interface Match {
  match_id: string;
  home: string;
  away: string;
  stage: string;
  stage_label: string;
  kickoff_utc: string;
  kickoff_local: string;
  venue: string;
  score: number;
  label: string;
  emoji: string;
  archetype: Archetype | null;
  narrative: string | null;
  breakdown: Record<string, number>;
  raw_by_scorer: Record<string, number>;
  weight_by_scorer: Record<string, number>;
  reason_by_scorer: Record<string, string>;
  detail_by_scorer?: Record<string, string>;
  reasons: Record<string, string>;
  prediction: Prediction | null;
  intrinsic_score: number;
  personal_score: number;
  h2h: H2HRecord | null;
  h2h_all: H2HRecord | null;
  h2h_recent: H2HRecentMatch[] | null;
  stars: Star[] | null;
  base_score: number;
  // Simulation-only fields (present after simulate)
  home_goals?: number | null;
  away_goals?: number | null;
  predicted_winner?: string | null;
  rarity?: number | null;
  home_path?: Record<string, number> | null;
  away_path?: Record<string, number> | null;
}

export interface ScorerWeight {
  max_pts: number;
  label: string;
  desc?: string;
}

// ── API response: GET /api/matches ───────────────────────────────────────────

export interface MatchesResponse {
  matches: Match[];
  weights: Record<string, ScorerWeight>;
  default_weights: Record<string, number>;
  has_learned: boolean;
}

// ── Simulation types ─────────────────────────────────────────────────────────

/** @deprecated Use Match directly — simulation fields are optional on Match */
export type SimMatch = Match;

export interface BracketMatch {
  match_num: number;
  home: string;
  away: string;
  winner: string;
  loser: string;
  is_final: boolean;
  is_third: boolean;
  winner_prob: Record<string, number>;
  home_goals: number | null;
  away_goals: number | null;
}

export interface BracketRound {
  label: string;
  matches: BracketMatch[];
}

export interface StandingRow {
  team: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  pts: number;
  qualified: boolean;
  third_place: boolean;
  [key: string]: unknown;
}

export interface GroupStanding {
  group: string;
  teams: StandingRow[];
}

export interface ChampionOdds {
  team: string;
  pct: number;
}

/** Team tournament path probabilities (R32, R16, QF, SF, F, Champ) */
export type TeamPath = Record<string, number>;

export interface SimulationResponse {
  seed: number;
  n_sims: number;
  matches: SimMatch[];
  bracket_rounds: BracketRound[];
  standings: GroupStanding[];
  champion_odds: ChampionOdds[];
  team_paths: Record<string, TeamPath>;
  weights: Record<string, ScorerWeight>;
}

// ── Profile types ────────────────────────────────────────────────────────────

export interface TimeWindow {
  weekday: number | null;
  start_hour: number;
  end_hour: number;
  timezone: string;
}

export interface Profile {
  name: string;
  team_affinities: Record<string, number>;
  time_windows: TimeWindow[];
}

export interface ProfileInput {
  name: string;
  team_affinities: Record<string, number>;
  favorite_teams?: string[];
  time_windows: TimeWindow[];
}

// ── Team & player types ──────────────────────────────────────────────────────

export interface Team {
  fifa_code: string;
  team_name: string;
  group_letter: string;
  is_placeholder: boolean;
  confederation: string | null;
  fifa_rank: number | null;
  wc_titles: number | null;
  wc_appearances: number | null;
  best_finish: string | null;
  top11_avg: number | null;
  stars_85plus: number | null;
}

// ── Learning types ───────────────────────────────────────────────────────────

export interface LearnMatch {
  match_id: string;
  home: string;
  away: string;
  stage: string;
  stage_label: string;
  kickoff_local: string;
  venue: string;
  historical: boolean;
  year: string;
  round: string;
  result: string;
  home_goals: string;
  away_goals: string;
  raw: Record<string, number>;
}

export interface LearnMatchesResponse {
  matches: LearnMatch[];
  total: number;
}

export interface RatedMatch {
  raw: Record<string, number>;
  rating: number;
}

export interface TopFeature {
  scorer: string;
  importance: number;
}

export interface RatingStats {
  mean?: number;
  min?: number;
  max?: number;
  n?: number;
  dist?: Record<string, number>;
}

export interface FitRatingsResponse {
  weights: Record<string, number>;
  weight_delta: Record<string, number>;
  top_features: TopFeature[];
  interactions: Record<string, number>;
  rating_stats: RatingStats;
  confidence: number;
  method: 'prior' | 'pearson' | 'ridge';
  scorer_labels: Record<string, string>;
  total_examples: number;
}

export interface FitMeta {
  n: number;
  mean_rating: number | null;
  confidence: number;
  top_features: string[];
  last_fit: string;
}

export interface LearnStateResponse {
  n_examples: number;
  has_learned: boolean;
  learned_weights: Record<string, number> | null;
  default_weights: Record<string, number>;
  fit_meta: FitMeta | null;
  weight_delta: Record<string, number>;
}

export interface ResetRatingsResponse {
  status: string;
  message: string;
}
