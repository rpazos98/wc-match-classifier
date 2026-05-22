import { useAppState } from '../../state/AppContext';
import { fl } from '../../utils/flags';

interface SidebarProps {
  onOpenProfile: () => void;
}

type TierKey = 'S' | 'A' | 'B';

export default function Sidebar({ onOpenProfile }: SidebarProps) {
  const { profile, weights, defaultWeights, hasLearned } = useAppState();

  if (!profile) {
    return (
      <aside id="sidebar">
        <div id="profile-sidebar">
          <div style={{ color: 'var(--muted)', fontSize: '11px' }}>Cargando...</div>
        </div>
      </aside>
    );
  }

  const affinities = profile.team_affinities ?? {};
  const tierEntries = Object.entries(affinities).sort((a, b) => b[1] - a[1]);

  const tierGroups: Record<TierKey, string[]> = { S: [], A: [], B: [] };
  for (const [team, value] of tierEntries) {
    if (value >= 0.9) tierGroups.S.push(team);
    else if (value >= 0.5) tierGroups.A.push(team);
    else tierGroups.B.push(team);
  }

  const DAYS = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];

  const wEntries = Object.entries(weights);
  const maxW = wEntries.length > 0
    ? Math.max(...wEntries.map(([, w]) => w.max_pts))
    : 0;

  return (
    <aside id="sidebar" onClick={onOpenProfile} style={{ cursor: 'pointer' }}>
      <div id="profile-sidebar">
        <div className="profile-name">{'\u{1F464}'} {profile.name}</div>

        {tierEntries.length > 0 && (
          <>
            <div className="sidebar-label">Equipos</div>
            <div>
              {(['S', 'A', 'B'] as TierKey[]).map((tier) =>
                tierGroups[tier].map((team) => (
                  <span className="team-chip" key={team}>
                    <span className={`tier-badge tier-badge-${tier.toLowerCase()}`}>
                      {tier}
                    </span>{' '}
                    {fl(team)} {team}
                  </span>
                )),
              )}
            </div>
          </>
        )}

        {profile.favorite_players.length > 0 && (
          <>
            <div className="sidebar-label">Jugadores</div>
            {profile.favorite_players.slice(0, 8).map((player) => (
              <div className="player-item" key={player}>
                {'· '}{player}
              </div>
            ))}
            {profile.favorite_players.length > 8 && (
              <div className="player-item" style={{ color: 'var(--muted)' }}>
                {'...+'}{profile.favorite_players.length - 8}{' mas'}
              </div>
            )}
          </>
        )}

        {profile.time_windows.length > 0 && (
          <>
            <div className="sidebar-label">Disponibilidad</div>
            {profile.time_windows.map((w, i) => {
              const day =
                w.weekday !== null && w.weekday !== undefined
                  ? DAYS[w.weekday]
                  : 'Todos';
              const tz = w.timezone.split('/').pop()?.replace(/_/g, ' ') ?? '';
              return (
                <div key={i}>
                  <div className="avail-item">
                    {day} {String(w.start_hour).padStart(2, '0')}
                    {'\u2013'}
                    {String(w.end_hour).padStart(2, '0')}h
                  </div>
                  <div
                    className="avail-item"
                    style={{ fontSize: '10px', color: 'var(--muted)' }}
                  >
                    {tz}
                  </div>
                </div>
              );
            })}
          </>
        )}

        <div className="sidebar-label">Dimensiones</div>
        {wEntries.map(([name, w]) => {
          const barW = maxW > 0 ? Math.round((w.max_pts / maxW) * 100) : 0;
          const rawDelta =
            hasLearned && defaultWeights[name] != null
              ? w.max_pts - defaultWeights[name] * 100
              : null;
          const showDelta = rawDelta != null && Math.abs(rawDelta) >= 1;

          return (
            <div className="wt-row" key={name}>
              <span className="wt-name">{w.label}</span>
              <div className="wt-bar-bg">
                <div className="wt-bar" style={{ width: `${barW}%` }} />
              </div>
              <span className="wt-pct">
                {Math.round(w.max_pts)}%
                {showDelta && (
                  <span
                    style={{
                      fontSize: '8px',
                      fontWeight: 700,
                      color: rawDelta! > 0 ? '#3dd6c8' : '#e06060',
                      marginLeft: '2px',
                    }}
                  >
                    {rawDelta! > 0 ? '+' : ''}
                    {rawDelta!.toFixed(0)}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
