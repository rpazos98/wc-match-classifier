import { useAppState, useAppDispatch } from '../../state/AppContext';
import type { SimEngine } from '../../state/AppContext';

interface HeaderProps {
  onOpenProfile: () => void;
  onSimulate: () => void;
  onOpenLearn: () => void;
  onOpenCreator: () => void;
}

export default function Header({ onOpenProfile, onSimulate, onOpenLearn, onOpenCreator }: HeaderProps) {
  const { simulating, simulated, hasLearned, seed, activeTab, profile, simEngine } = useAppState();
  const dispatch = useAppDispatch();

  const hasProfile = profile && Object.keys(profile.team_affinities ?? {}).length > 0;

  const steps = [
    { num: 1, label: 'Perfil',        done: !!hasProfile, active: false,                   onClick: onOpenProfile, disabled: false },
    { num: 2, label: 'Partidos',      done: simulated,   active: activeTab === 'matches',  onClick: () => dispatch({ type: 'SET_TAB', tab: 'matches' }), disabled: false },
    { num: 3, label: 'Personalizar',  done: hasLearned,  active: false,                    onClick: onOpenLearn,   disabled: false },
  ];

  return (
    <header id="header">
      <div className="header-top">
        <div>
          <h1>{'🏆 Tu Tiempo, Tu Mundial 2026'}</h1>
          <p className="header-subtitle">
            Clasificador personalizado de partidos — descubre cuales no te puedes perder
          </p>
        </div>
        <div className="header-meta">
          <div className="engine-toggle">
            {(['classic', 'fte538'] as SimEngine[]).map((eng) => (
              <button
                key={eng}
                className={'engine-btn' + (simEngine === eng ? ' active' : '')}
                onClick={() => dispatch({ type: 'SET_ENGINE', engine: eng })}
                disabled={simulating}
                title={eng === 'classic' ? 'Motor clásico: ELO → resultado → goles' : 'Motor 538: xG → Poisson → resultado'}
              >
                {eng === 'classic' ? 'Clásico' : '538'}
              </button>
            ))}
          </div>
          {simulating && (
            <span id="seed-badge" style={{ color: 'var(--amber)' }}>
              ⏳ 5000 simulaciones...
            </span>
          )}
          {!simulating && simulated && seed != null && (
            <span id="seed-badge">🎲 semilla {seed}</span>
          )}
        </div>
      </div>
      <div className="header-pipeline">
        {steps.map((step, i) => (
          <span key={step.num} style={{ display: 'contents' }}>
            {i > 0 && <span className="pipe-arrow">{'›'}</span>}
            <button
              className={
                'pipe-step' +
                (step.done ? ' done' : '') +
                (step.active ? ' active' : '')
              }
              onClick={step.onClick}
              disabled={step.disabled}
            >
              <span className="pipe-num">{step.num}</span>
              <span className="pipe-label">{step.label}</span>
            </button>
          </span>
        ))}
        <div className="pipe-spacer" />
        <button className="btn btn-icon" onClick={onOpenCreator} title="Crear partido hipotetico">
          &#x2795;
        </button>
        <button
          className="btn btn-icon"
          onClick={onSimulate}
          disabled={simulating}
          title={simulated ? 'Re-simular con nueva semilla' : 'Simular 5000 brackets'}
        >
          {simulating ? '⏳' : simulated ? '🔄' : '▶️'}
        </button>
      </div>
    </header>
  );
}
