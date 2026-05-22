import {
  createContext,
  useContext,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react';

import type {
  Match,
  ScorerWeight,
  Profile,
  BracketRound,
  GroupStanding,
  ChampionOdds,
} from '../types';

// ── Bracket data (simulation-specific view model) ────────────────────────────

export interface BracketData {
  bracket_rounds: BracketRound[];
  standings: GroupStanding[];
  champion_odds: ChampionOdds[];
  n_sims: number;
  champion: string | null;
  runner_up: string | null;
  third_place: string | null;
}

// ── App state ────────────────────────────────────────────────────────────────

export type TabName = 'matches' | 'bracket';
export type FilterMode = 'all' | 'confirmed' | 'simulated';

export interface AppState {
  matches: Match[];
  matchById: Record<string, Match>;
  weights: Record<string, ScorerWeight>;
  defaultWeights: Record<string, number>;
  hasLearned: boolean;

  bracketData: BracketData | null;
  simulated: boolean;
  seed: number | null;

  selectedId: string | null;
  pinnedId: string | null;

  activeTab: TabName;
  filterMode: FilterMode;

  profile: Profile | null;
}

const initialState: AppState = {
  matches: [],
  matchById: {},
  weights: {},
  defaultWeights: {},
  hasLearned: false,

  bracketData: null,
  simulated: false,
  seed: null,

  selectedId: null,
  pinnedId: null,

  activeTab: 'matches',
  filterMode: 'all',

  profile: null,
};

// ── Actions ──────────────────────────────────────────────────────────────────

type Action =
  | {
      type: 'SET_MATCHES';
      matches: Match[];
      weights: Record<string, ScorerWeight>;
      defaultWeights: Record<string, number>;
      hasLearned: boolean;
    }
  | { type: 'SET_BRACKET'; bracketData: BracketData; seed: number; matches: Match[]; weights: Record<string, ScorerWeight> }
  | { type: 'CLEAR_BRACKET' }
  | { type: 'SELECT_MATCH'; id: string | null }
  | { type: 'PIN_MATCH'; id: string | null }
  | { type: 'SET_TAB'; tab: TabName }
  | { type: 'SET_FILTER'; mode: FilterMode }
  | { type: 'SET_PROFILE'; profile: Profile }
  | { type: 'UPDATE_MATCH'; match: Match }
  | { type: 'SET_LEARNED'; hasLearned: boolean };

export type AppAction = Action;

// ── Reducer ──────────────────────────────────────────────────────────────────

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
        matchById: buildMatchById(matches),
        weights: action.weights,
        defaultWeights: action.defaultWeights,
        hasLearned: action.hasLearned,
      };
    }

    case 'SET_BRACKET':
      return {
        ...state,
        bracketData: action.bracketData,
        simulated: true,
        seed: action.seed,
        matches: action.matches,
        matchById: buildMatchById(action.matches),
        weights: action.weights,
      };

    case 'CLEAR_BRACKET':
      return {
        ...state,
        bracketData: null,
        simulated: false,
        seed: null,
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

// ── Context ──────────────────────────────────────────────────────────────────

const AppStateContext = createContext<AppState>(initialState);
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

export function useAppState(): AppState {
  return useContext(AppStateContext);
}

export function useAppDispatch(): Dispatch<Action> {
  return useContext(AppDispatchContext);
}
