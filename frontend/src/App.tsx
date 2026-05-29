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
import { loadPrecomputedSimulation } from './api/matches';
import { applyPersonalScoring } from './scoring/personal';
import { loadScoringData, type ScoringData } from './scoring/classify';
import { useSimulation, convertToSimulationResponse } from './simulation';
import type { TeamProfile, GroupMatch } from './simulation';
import type { SimulationResponse, Profile } from './types';

const BASE = import.meta.env.BASE_URL ?? '/';

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

  // Simulation data loaded once
  const [teamProfiles, setTeamProfiles] = useState<Record<string, TeamProfile> | null>(null);
  const [teamGroups, setTeamGroups] = useState<Record<string, string> | null>(null);
  const [groupMatches, setGroupMatches] = useState<GroupMatch[] | null>(null);
  const scoringDataRef = useRef<ScoringData | null>(null);

  // FE simulation worker
  const sim = useSimulation();

  // Profile from localStorage
  const { profile, update: updateProfile } = useProfile();

  // SWR: auto-fetch + cache matches (depends on profile)
  const { matchData, groups: rawGroups, error: matchError, isLoading: matchesLoading, refresh: refreshMatches } = useMatches(profile);

  // Load team profiles + scoring data for FE simulation
  useEffect(() => {
    fetch(`${BASE}data/team_profiles.json`)
      .then(r => r.json())
      .then((profiles: Record<string, TeamProfile>) => {
        setTeamProfiles(profiles);
        // Load scoring data (stars, h2h) once profiles are ready
        loadScoringData(profiles).then(sd => { scoringDataRef.current = sd; });
      })
      .catch(() => {});
  }, []);

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

  // Extract group matches + teamGroups from matchData when available
  useEffect(() => {
    if (matchData) {
      const gm = matchData.matches
        .filter(m => m.stage === 'group')
        .map(m => ({ match_id: m.match_id, home: m.home, away: m.away }));
      setGroupMatches(gm);
    }
  }, [matchData]);

  useEffect(() => {
    if (rawGroups) setTeamGroups(rawGroups);
  }, [rawGroups]);

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

  // When FE simulation completes, convert + apply
  useEffect(() => {
    if (!sim.result || !matchData || !profile) return;

    const data = convertToSimulationResponse(
      sim.result,
      matchData.matches.filter(m => m.stage === 'group'),
      sim.result.nSims,
      matchData.weights,
      matchData.default_weights,
      scoringDataRef.current,
    );

    rawSimData.current = data;
    applySimulation(data, profile);
    dispatch({ type: 'SET_TAB', tab: 'bracket' });
    toast(`Simulacion completa — ${sim.result.nSims} sims en ${Math.round(sim.elapsedMs ?? 0)}ms`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim.result]);

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

  const handleSimulate = useCallback(() => {
    if (!teamProfiles || !teamGroups || !groupMatches) {
      toast('\u26A0 Datos no cargados aún');
      return;
    }

    dispatch({ type: 'SET_SIMULATING' });
    const seed = Date.now();
    sim.run(groupMatches, teamGroups, teamProfiles, 5000, seed, state.simEngine);
  }, [dispatch, toast, state.simEngine, teamProfiles, teamGroups, groupMatches, sim]);

  const handleLearnClose = useCallback(() => {
    setLearnOpen(false);
    refreshMatches();
  }, [refreshMatches]);

  const handleEditClose = useCallback(() => {
    setEditSection(null);
  }, []);

  const isSimulating = state.simulating || sim.running;
  const simProgress = sim.running ? Math.round(sim.progress * 100) : 0;

  return (
    <>
      <LoadingBar
        active={matchesLoading || isSimulating}
        label={
          isSimulating
            ? `Simulando 5000 brackets... ${simProgress}%`
            : matchesLoading
              ? 'Clasificando partidos...'
              : undefined
        }
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
