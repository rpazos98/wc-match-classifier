import { useAppState } from '../../state/AppContext';

interface HeaderProps {
  onOpenProfile: () => void;
  onSimulate: () => void;
  onOpenLearn: () => void;
}

export default function Header({ onOpenProfile, onSimulate, onOpenLearn }: HeaderProps) {
  const { simulated, hasLearned, seed, activeTab } = useAppState();

  const steps = [
    { num: 1, label: 'Perfil',       done: true,        active: false,                onClick: onOpenProfile },
    { num: 2, label: 'Partidos',     done: false,       active: activeTab === 'matches', onClick: undefined },
    { num: 3, label: simulated ? 'Simulado' : 'Simular', done: simulated, active: false, onClick: onSimulate },
    { num: 4, label: 'Personalizar', done: hasLearned,  active: false,                onClick: onOpenLearn },
  ];

  return (
    <header id="header">
      <div className="header-top">
        <h1>{'🏆 Tu Tiempo, Tu Mundial 2026'}</h1>
        <div className="header-meta">
          {simulated && seed != null && (
            <span id="seed-badge">Seed #{seed}</span>
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
            >
              <span className="pipe-num">{step.num}</span>
              <span className="pipe-label">{step.label}</span>
            </button>
          </span>
        ))}
        <div className="pipe-spacer" />
        {simulated && (
          <button className="btn btn-icon" onClick={onSimulate} title="Re-simular con nueva semilla">
            🔄
          </button>
        )}
      </div>
    </header>
  );
}
