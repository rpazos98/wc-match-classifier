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
import { getMatches, simulate } from './api/matches';
import { getProfile } from './api/profile';

function AppInner() {
  const { activeTab } = useAppState();
  const dispatch = useAppDispatch();
  const toast = useToast();

  const [profileOpen, setProfileOpen] = useState(false);
  const [learnOpen, setLearnOpen] = useState(false);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [matchData, profile] = await Promise.all([
          getMatches(),
          getProfile(),
        ]);

        dispatch({
          type: 'SET_MATCHES',
          matches: matchData.matches,
          weights: matchData.weights,
          defaultWeights: matchData.default_weights,
          hasLearned: matchData.has_learned,
        });

        dispatch({ type: 'SET_PROFILE', profile });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        toast('\u26A0 Error al cargar: ' + msg);
      }
    }

    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleOpenProfile = useCallback(() => {
    setProfileOpen(true);
  }, []);

  const handleSimulate = useCallback(async () => {
    try {
      toast('Simulando torneo...');
      const data = await simulate();
      dispatch({
        type: 'SET_BRACKET',
        bracketData: {
          bracket_rounds: data.bracket_rounds,
          standings: data.standings,
          champion_odds: data.champion_odds,
          n_sims: data.n_sims,
          champion: data.champion_odds?.[0]?.team ?? null,
          runner_up: null,
          third_place: null,
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

  const handleOpenLearn = useCallback(() => {
    setLearnOpen(true);
  }, []);

  return (
    <>
      <Header
        onOpenProfile={handleOpenProfile}
        onSimulate={handleSimulate}
        onOpenLearn={handleOpenLearn}
      />
      <div id="layout">
        <Sidebar onOpenProfile={handleOpenProfile} />
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
        onClose={() => setProfileOpen(false)}
      />
      <LearnModal
        isOpen={learnOpen}
        onClose={() => setLearnOpen(false)}
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
