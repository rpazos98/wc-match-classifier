import { useAppState, useAppDispatch } from '../../state/AppContext';

export default function TabBar() {
  const { activeTab, matches, simulated } = useAppState();
  const dispatch = useAppDispatch();

  return (
    <div id="tabs">
      <button
        className={'tab-btn' + (activeTab === 'matches' ? ' active' : '')}
        onClick={() => dispatch({ type: 'SET_TAB', tab: 'matches' })}
      >
        Matches{' '}
        <span className="tab-count">{matches.length || '\u2013'}</span>
      </button>
      <button
        className={'tab-btn' + (activeTab === 'bracket' ? ' active' : '')}
        onClick={() => dispatch({ type: 'SET_TAB', tab: 'bracket' })}
        disabled={!simulated}
      >
        {'Bracket 📊'}
      </button>
    </div>
  );
}
