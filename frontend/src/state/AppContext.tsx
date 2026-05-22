import {
  createContext,
  useContext,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react';

// ── Domain types ──────────────────────────────────────────────────────────────

export interface MatchPrediction {
  p_home:   number;
  p_draw:   number;
  p_away:   number;
  elo_home: number;
  elo_away: number;
  entropy:  number;
}

export interface Archetype {
  icon:  string;
  label: string;
}

export interface H2HRecord {
  wins_home: number;
  wins_away: number;
  draws:     number;
  played:    number;
}

export interface H2HMatch {
  year:       number;
  tournament: string;
  home:       string;
  away:       string;
  home_goals: number;
  away_goals: number;
}

export interface Star {
  name:    string;
  team:    string;
  overall: number;
}

export interface Match {
  match_id:         string;
  home:             string;
  away:             string;
  stage:            string;
  stage_label:      string;
  kickoff_utc:      string;
  kickoff_local:    string;
  venue:            string;
  score:            number;
  label:            string;
  emoji:            string;
  archetype:        Archetype | null;
  narrative:        string | null;
  breakdown:        Record<string, number>;
  raw_by_scorer:    Record<string, number>;
  weight_by_scorer: Record<string, number>;
  reason_by_scorer: Record<string, string>;
  reasons:          string[];
  prediction:       MatchPrediction | null;
  intrinsic_score:  number;
  personal_score:   number;
  h2h:              H2HRecord | null;
  h2h_all:          H2HRecord | null;
  h2h_recent:       H2HMatch[] | null;
  stars:            Star[] | null;
  base_score:       number;
  // Fields added by simulation
  home_goals?:       number | null;
  away_goals?:       number | null;
  predicted_winner?: string | null;
  rarity?:           number | null;
}

export interface WeightInfo {
  max_pts: number;
  label:   string;
}

export interface TimeWindow {
  weekday:    number | null;
  start_hour: number;
  end_hour:   number;
  timezone:   string;
}

export interface Profile {
  name:             string;
  team_affinities:  Record<string, number>;
  favorite_players: string[];
  time_windows:     TimeWindow[];
}

export interface BracketGroup {
  group:    string;
  teams:    { code: string; pts: number; gd: number; gf: number }[];
}

export interface BracketData {
  groups:   BracketGroup[];
  rounds:   Record<string, Match[]>;
  champion: string | null;
}

// ── App state ─────────────────────────────────────────────────────────────────

export type TabName    = 'matches' | 'bracket';
export type FilterMode = 'all' | 'confirmed' | 'simulated';

export interface AppState {
  // Data
  matches:        Match[];
  matchById:      Record<string, Match>;
  weights:        Record<string, WeightInfo>;
  defaultWeights: Record<string, number>;
  hasLearned:     boolean;

  // Simulation
  bracketData:    BracketData | null;
  simulated:      boolean;
  seed:           number | null;

  // UI selection
  selectedId:     string | null;
  pinnedId:       string | null;

  // Navigation / filtering
  activeTab:      TabName;
  filterMode:     FilterMode;

  // User
  profile:        Profile | null;
}

const initialState: AppState = {
  matches:        [],
  matchById:      {},
  weights:        {},
  defaultWeights: {},
  hasLearned:     false,

  bracketData:    null,
  simulated:      false,
  seed:           null,

  selectedId:     null,
  pinnedId:       null,

  activeTab:      'matches',
  filterMode:     'all',

  profile:        null,
};

// ── Actions ───────────────────────────────────────────────────────────────────

type Action =
  | {
      type: 'SET_MATCHES';
      matches:        Match[];
      weights:        Record<string, WeightInfo>;
      defaultWeights: Record<string, number>;
      hasLearned:     boolean;
    }
  | { type: 'SET_BRACKET';   bracketData: BracketData; seed: number }
  | { type: 'CLEAR_BRACKET' }
  | { type: 'SELECT_MATCH';  id: string | null }
  | { type: 'PIN_MATCH';     id: string | null }
  | { type: 'SET_TAB';       tab: TabName }
  | { type: 'SET_FILTER';    mode: FilterMode }
  | { type: 'SET_PROFILE';   profile: Profile }
  | { type: 'UPDATE_MATCH';  match: Match }
  | { type: 'SET_LEARNED';   hasLearned: boolean };

export type AppAction = Action;

// ── Reducer ───────────────────────────────────────────────────────────────────

function buildMatchById(matches: Match[]): Record<string, Match> {
  const map: Record<string, Match> = {};
  for (const m of matches) map[m.match_id] = m;
  return map;
}

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_MATCHES': {
      const matches = action.matches;
      return {
        ...state,
        matches,
        matchById:      buildMatchById(matches),
        weights:        action.weights,
        defaultWeights: action.defaultWeights,
        hasLearned:     action.hasLearned,
      };
    }

    case 'SET_BRACKET':
      return {
        ...state,
        bracketData: action.bracketData,
        simulated:   true,
        seed:        action.seed,
      };

    case 'CLEAR_BRACKET':
      return {
        ...state,
        bracketData: null,
        simulated:   false,
        seed:        null,
      };

    case 'SELECT_MATCH':
      return { ...state, selectedId: action.id };

    case 'PIN_MATCH':
      return {
        ...state,
        pinnedId: state.pinnedId === action.id ? null : action.id,
      };

    case 'SET_TAB':
      return { ...state, activeTab: action.tab };

    case 'SET_FILTER':
      return { ...state, filterMode: action.mode };

    case 'SET_PROFILE':
      return { ...state, profile: action.profile };

    case 'UPDATE_MATCH': {
      const updated = action.match;
      const matches = state.matches.map((m) =>
        m.match_id === updated.match_id ? updated : m,
      );
      return {
        ...state,
        matches,
        matchById: { ...state.matchById, [updated.match_id]: updated },
      };
    }

    case 'SET_LEARNED':
      return { ...state, hasLearned: action.hasLearned };

    default:
      return state;
  }
}

// ── Context ───────────────────────────────────────────────────────────────────

const AppStateContext    = createContext<AppState>(initialState);
const AppDispatchContext = createContext<Dispatch<Action>>(() => {
  throw new Error('AppDispatchContext used outside provider');
});

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  return (
    <AppStateContext.Provider value={state}>
      <AppDispatchContext.Provider value={dispatch}>
        {children}
      </AppDispatchContext.Provider>
    </AppStateContext.Provider>
  );
}

/** Read the full app state. */
export function useAppState(): AppState {
  return useContext(AppStateContext);
}

/** Get the dispatch function for app actions. */
export function useAppDispatch(): Dispatch<Action> {
  return useContext(AppDispatchContext);
}
