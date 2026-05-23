import { useAppState } from '../../state/AppContext';
import { fl } from '../../utils/flags';
import type { EditSection } from '../profile/ProfileEditModal';

interface SidebarProps {
  onEditSection: (section: EditSection) => void;
}

type TierKey = 'S' | 'A' | 'B';

export default function Sidebar({ onEditSection }: SidebarProps) {
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
  const hasTeams = tierEntries.length > 0;

  const tierGroups: Record<TierKey, string[]> = { S: [], A: [], B: [] };
  for (const [team, value] of tierEntries) {
    if (value >= 0.9) tierGroups.S.push(team);
    else if (value >= 0.5) tierGroups.A.push(team);
    else tierGroups.B.push(team);
  }

  const wEntries = Object.entries(weights);
  const maxW = wEntries.length > 0
    ? Math.max(...wEntries.map(([, w]) => w.max_pts))
    : 0;

  return (
    <aside id="sidebar">
      <div id="profile-sidebar">
        <div
          className="profile-name sidebar-editable"
          onClick={() => onEditSection('name')}
        >
          {'\u{1F464}'} {profile.name}
          <span className="sidebar-edit-hint">&#9998;</span>
        </div>

        {!hasTeams && (
          <div
            className="sidebar-cta"
            onClick={() => onEditSection('teams')}
            style={{ cursor: 'pointer' }}
          >
            <div className="sidebar-cta-icon">&#9881;</div>
            <p>Configura tus equipos para personalizar los puntajes</p>
            <span className="sidebar-cta-link">Click para comenzar</span>
          </div>
        )}

        <div
          className="sidebar-section sidebar-editable"
          onClick={() => onEditSection('teams')}
        >
          <div className="sidebar-label">
            Equipos
            <span className="sidebar-edit-hint">&#9998;</span>
          </div>
          {tierEntries.length > 0 && (
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
          )}
        </div>

        <div className="sidebar-label">Dimensiones</div>
        {wEntries.map(([name, w]) => {
          const barW = maxW > 0 ? Math.round((w.max_pts / maxW) * 100) : 0;
          const rawDelta =
            hasLearned && defaultWeights[name] != null
              ? w.max_pts - defaultWeights[name] * 100
              : null;
          const showDelta = rawDelta != null && Math.abs(rawDelta) >= 1;

          return (
            <div className="wt-row" key={name} title={w.desc || ''}>
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
