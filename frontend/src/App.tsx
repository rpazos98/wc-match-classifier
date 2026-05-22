import { useEffect, useCallback, useState } from 'react';
import { useAppState, useAppDispatch } from './state/AppContext';
import { ToastProvider, useToast } from './components/common/Toast';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import TabBar from './components/layout/TabBar';
import MatchList from './components/matches/MatchList';
import DetailPanel from './components/detail/DetailPanel';
import BracketView from './components/bracket/BracketView';
import LearnModal from './components/learn/LearnModal';
import ProfileWizard from './components/profile/ProfileWizard';
import { useMatches } from './hooks/useMatches';
import { useProfile } from './hooks/useProfile';
import { simulate } from './api/matches';

function AppInner() {
  const state = useAppState();
  const { activeTab } = state;
  const dispatch = useAppDispatch();
  const toast = useToast();

  const [profileOpen, setProfileOpen] = useState(false);
  const [learnOpen, setLearnOpen] = useState(false);

  // SWR: auto-fetch + cache matches and profile
  const { matchData, error: matchError, refresh: refreshMatches } = useMatches();
  const { profile, error: profileError } = useProfile();

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

  useEffect(() => {
    if (profile) {
      dispatch({ type: 'SET_PROFILE', profile });
    }
  }, [profile, dispatch]);

  useEffect(() => {
    if (matchError || profileError) {
      const msg = (matchError || profileError)?.message ?? 'Error desconocido';
      toast('\u26A0 Error al cargar: ' + msg);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchError, profileError]);

  const handleSimulate = useCallback(async () => {
    try {
      toast('Simulando torneo...');
      const data = await simulate();
      // Find actual winners from the representative bracket
      const allBracketMatches = data.bracket_rounds.flatMap((r: { matches: Array<{ match_num: number; winner: string; loser: string; is_final?: boolean; is_third?: boolean }> }) => r.matches);
      const finalMatch = allBracketMatches.find((m: { match_num: number }) => m.match_num === 104);
      const thirdMatch = allBracketMatches.find((m: { match_num: number }) => m.match_num === 103);

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
        matches: data.matches,
        weights: data.weights,
      });
      dispatch({ type: 'SET_TAB', tab: 'bracket' });
      toast(`Simulacion completa (semilla ${data.seed})`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast('\u26A0 Error al simular: ' + msg);
    }
  }, [dispatch, toast]);

  const handleLearnClose = useCallback(() => {
    setLearnOpen(false);
    // Refresh matches after learning (weights may have changed)
    refreshMatches();
  }, [refreshMatches]);

  const handleProfileClose = useCallback(() => {
    setProfileOpen(false);
    // Refresh matches after profile change (scores recalculated)
    refreshMatches();
  }, [refreshMatches]);

  return (
    <>
      <Header
        onOpenProfile={() => setProfileOpen(true)}
        onSimulate={handleSimulate}
        onOpenLearn={() => setLearnOpen(true)}
      />
      <div id="layout">
        <Sidebar onOpenProfile={() => setProfileOpen(true)} />
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

      <ProfileWizard
        isOpen={profileOpen}
        onClose={handleProfileClose}
      />
      <LearnModal
        isOpen={learnOpen}
        onClose={handleLearnClose}
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
