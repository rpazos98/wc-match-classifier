import { useAppState, useAppDispatch, type FilterMode } from '../../state/AppContext';

const filters: { mode: FilterMode; label: string }[] = [
  { mode: 'all',       label: 'Todos' },
  { mode: 'confirmed', label: 'Confirmados' },
  { mode: 'simulated', label: 'Simulados' },
];

export default function FilterBar() {
  const { simulated, filterMode } = useAppState();
  const dispatch = useAppDispatch();

  if (!simulated) return null;

  return (
    <div className="match-filter-bar">
      {filters.map(({ mode, label }) => (
        <button
          key={mode}
          className={`filter-btn${filterMode === mode ? ' active' : ''}`}
          onClick={() => dispatch({ type: 'SET_FILTER', mode })}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
