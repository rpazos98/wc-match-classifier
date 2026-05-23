import { useAppState } from '../../state/AppContext';

interface HeaderProps {
  onOpenProfile: () => void;
  onSimulate: () => void;
  onOpenLearn: () => void;
}

export default function Header({ onOpenProfile, onSimulate, onOpenLearn }: HeaderProps) {
  const { simulating, simulated, hasLearned, seed, activeTab, profile } = useAppState();

  const hasProfile = profile && Object.keys(profile.team_affinities ?? {}).length > 0;

  const simLabel = simulating
    ? 'Simulando...'
    : simulated
      ? 'Simulado'
      : 'Simular';

  const steps = [
    { num: 1, label: 'Perfil',        done: !!hasProfile, active: false,                    onClick: onOpenProfile, disabled: false },
    { num: 2, label: 'Partidos',      done: false,       active: activeTab === 'matches',  onClick: undefined,     disabled: false },
    { num: 3, label: simLabel,        done: simulated,   active: simulating,               onClick: onSimulate,    disabled: simulating },
    { num: 4, label: 'Personalizar',  done: hasLearned,  active: false,                    onClick: onOpenLearn,   disabled: false },
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
        {simulated && !simulating && (
          <button className="btn btn-icon" onClick={onSimulate} title="Re-simular con nueva semilla">
            🔄
          </button>
        )}
      </div>
    </header>
  );
}
