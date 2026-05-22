import { useAppState } from '../../state/AppContext';

export default function StatusBar() {
  const { matches, simulated, hasLearned } = useAppState();
  const n = matches.length;

  if (simulated) {
    const nGrp = matches.filter((m) => m.stage === 'group').length;
    const nKo = n - nGrp;

    return (
      <div className="match-list-status">
        <span className="mls-dot green" />
        {nGrp} grupo{' '}
        <span className="mls-dot purple" />
        {nKo} eliminatoria
        {hasLearned && (
          <>
            {' '}
            <span className="mls-dot blue" />
            personalizado
          </>
        )}
      </div>
    );
  }

  return (
    <div className="match-list-status">
      <span className="mls-dot green" />
      {n} grupo
    </div>
  );
}
