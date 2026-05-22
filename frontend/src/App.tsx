import { useEffect, useCallback } from 'react';
import { useAppState, useAppDispatch } from './state/AppContext';
import { ToastProvider, useToast } from './components/common/Toast';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import TabBar from './components/layout/TabBar';
import { getMatches } from './api/matches';
import { getProfile } from './api/profile';

function AppInner() {
  const { activeTab } = useAppState();
  const dispatch = useAppDispatch();
  const toast = useToast();

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
  }, [dispatch, toast]);

  const handleOpenProfile = useCallback(() => {
    // TODO: open profile modal
  }, []);

  const handleSimulate = useCallback(() => {
    // TODO: trigger simulation
  }, []);

  const handleOpenLearn = useCallback(() => {
    // TODO: open learn modal
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
              {/* TODO: MatchList component */}
              <div style={{ color: 'var(--muted)', padding: '20px', fontSize: '13px' }}>
                Match list placeholder
              </div>
            </div>
          )}
          {activeTab === 'bracket' && (
            <div id="tab-bracket">
              {/* TODO: BracketView component */}
              <div style={{ color: 'var(--muted)', padding: '20px', fontSize: '13px' }}>
                Bracket view placeholder
              </div>
            </div>
          )}
        </div>
        {/* Detail panel placeholder */}
        <div id="detail-panel" style={{ display: 'none' }}>
          {/* TODO: DetailPanel component */}
        </div>
      </div>
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
