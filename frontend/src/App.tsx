import { useEffect, useCallback, useState, useRef } from 'react';
import { useAppState, useAppDispatch } from './state/AppContext';
import { ToastProvider, useToast } from './components/common/Toast';
import LoadingBar from './components/common/LoadingBar';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import TabBar from './components/layout/TabBar';
import MatchList from './components/matches/MatchList';
import DetailPanel from './components/detail/DetailPanel';
import BracketView from './components/bracket/BracketView';
import LearnModal from './components/learn/LearnModal';
import MatchCreator from './components/creator/MatchCreator';
import ProfileEditModal from './components/profile/ProfileEditModal';
import type { EditSection } from './components/profile/ProfileEditModal';
import { useMatches } from './hooks/useMatches';
import { useProfile } from './hooks/useProfile';
import { simulate, loadPrecomputedSimulation } from './api/matches';
import { loadLearnedWeights } from './api/storage';
import { applyPersonalScoring } from './scoring/personal';
import type { SimulationResponse, Profile } from './types';

function AppInner() {
  const state = useAppState();
  const { activeTab } = state;
  const dispatch = useAppDispatch();
  const toast = useToast();

  const [editSection, setEditSection] = useState<EditSection | null>(null);
  const [learnOpen, setLearnOpen] = useState(false);
  const [creatorOpen, setCreatorOpen] = useState(false);
  const [hasAutoOpened, setHasAutoOpened] = useState(false);
  const precomputedLoaded = useRef(false);
  const rawSimData = useRef<SimulationResponse | null>(null);

  // Profile from localStorage
  const { profile, update: updateProfile } = useProfile();

  // SWR: auto-fetch + cache matches (depends on profile)
  const { matchData, error: matchError, isLoading: matchesLoading, refresh: refreshMatches } = useMatches(profile);

  // Sync profile → app state
  useEffect(() => {
    if (profile) {
      dispatch({ type: 'SET_PROFILE', profile });
    }
  }, [profile, dispatch]);

  // Sync SWR data → app state (skip when simulated — sim has its own matches)
  const { simulated } = state;
  useEffect(() => {
    if (matchData && !simulated) {
      dispatch({
        type: 'SET_MATCHES',
        matches: matchData.matches,
        weights: matchData.weights,
        defaultWeights: matchData.default_weights,
        hasLearned: matchData.has_learned,
      });
    }
  }, [matchData, dispatch, simulated]);

  // Load pre-computed simulation on startup
  useEffect(() => {
    if (precomputedLoaded.current) return;
    precomputedLoaded.current = true;
    loadPrecomputedSimulation()
      .then((data) => {
        rawSimData.current = data;
        applySimulation(data, profile);
      })
      .catch(() => { /* pre-computed not available, user can simulate manually */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-apply personal scoring to simulation when profile changes
  useEffect(() => {
    if (simulated && rawSimData.current && profile) {
      applySimulation(rawSimData.current, profile);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  function applySimulation(data: SimulationResponse, prof: Profile) {
    const dw = matchData?.default_weights ?? {};
    const scored = applyPersonalScoring(
      { matches: data.matches, weights: data.weights, default_weights: dw, has_learned: false },
      prof,
    );

    const allBracketMatches = data.bracket_rounds.flatMap((r) => r.matches);
    const finalMatch = allBracketMatches.find((m) => m.match_num === 104);
    const thirdMatch = allBracketMatches.find((m) => m.match_num === 103);

    dispatch({
      type: 'SET_BRACKET',
      bracketData: {
        bracket_rounds: data.bracket_rounds,
        standings: data.standings,
        champion_odds: data.champion_odds,
        n_sims: data.n_sims,
        champion: finalMatch?.winner ?? null,
        runner_up: finalMatch?.loser ?? null,
        third_place: thirdMatch?.winner ?? null,
      },
      seed: data.seed,
      matches: scored.matches,
      weights: data.weights,
    });
  }

  // Auto-open teams editor on first visit (no teams configured)
  useEffect(() => {
    if (
      profile &&
      !hasAutoOpened &&
      Object.keys(profile.team_affinities ?? {}).length === 0
    ) {
      setEditSection('teams');
      setHasAutoOpened(true);
    }
  }, [profile, hasAutoOpened]);

  // Auto-select top match when matches first load and nothing is selected
  useEffect(() => {
    if (state.matches.length > 0 && !state.selectedId) {
      dispatch({ type: 'SELECT_MATCH', id: state.matches[0].match_id });
    }
  }, [state.matches, state.selectedId, dispatch]);

  useEffect(() => {
    if (matchError) {
      const msg = matchError?.message ?? 'Error desconocido';
      toast('\u26A0 Error al cargar: ' + msg);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchError]);

  const handleSimulate = useCallback(async () => {
    try {
      dispatch({ type: 'SET_SIMULATING' });
      const data = await simulate(profile, loadLearnedWeights(), undefined, state.simEngine);
      rawSimData.current = data;
      applySimulation(data, profile);
      dispatch({ type: 'SET_TAB', tab: 'bracket' });
      toast(`Simulacion completa (semilla ${data.seed})`);
    } catch (err) {
      dispatch({ type: 'CLEAR_BRACKET' });
      const msg = err instanceof Error ? err.message : String(err);
      toast('\u26A0 Error al simular: ' + msg);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, toast, state.simEngine, profile]);

  const handleLearnClose = useCallback(() => {
    setLearnOpen(false);
    refreshMatches();
  }, [refreshMatches]);

  const handleEditClose = useCallback(() => {
    setEditSection(null);
  }, []);

  return (
    <>
      <LoadingBar
        active={matchesLoading || state.simulating}
        label={state.simulating ? 'Simulando 5000 brackets...' : matchesLoading ? 'Clasificando partidos...' : undefined}
      />
      <Header
        onOpenProfile={() => setEditSection('teams')}
        onSimulate={handleSimulate}
        onOpenLearn={() => setLearnOpen(true)}
        onOpenCreator={() => setCreatorOpen(true)}
      />
      <div id="layout">
        <Sidebar onEditSection={setEditSection} />
        <div id="main">
          <TabBar />
          {activeTab === 'matches' && (
            <div id="tab-matches" className="match-list-container">
              <MatchList />
            </div>
          )}
          {activeTab === 'bracket' && (
            <div id="tab-bracket" className="match-list-container">
              <BracketView />
            </div>
          )}
        </div>
        <DetailPanel />
      </div>

      {editSection && (
        <ProfileEditModal
          section={editSection}
          onClose={handleEditClose}
          onSave={updateProfile}
        />
      )}
      <LearnModal
        isOpen={learnOpen}
        onClose={handleLearnClose}
      />
      <MatchCreator
        isOpen={creatorOpen}
        onClose={() => setCreatorOpen(false)}
      />
    </>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
