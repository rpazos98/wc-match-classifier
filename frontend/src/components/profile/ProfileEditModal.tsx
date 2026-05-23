import { useState, useEffect, useCallback } from 'react';
import type { Team, ProfileInput } from '../../types';
import { getTeams, updateProfile } from '../../api/profile';
import { useAppState, useAppDispatch } from '../../state/AppContext';
import { fl } from '../../utils/flags';

export type EditSection = 'name' | 'teams';

const TIER_CYCLE: Record<string, string> = { '': 'S', S: 'A', A: 'B', B: '' };
const TIER_AFFINITY: Record<string, number> = { S: 1.0, A: 0.65, B: 0.3 };
const CONF_ORDER = ['CONMEBOL', 'UEFA', 'CONCACAF', 'CAF', 'AFC', 'OFC'];
const CONF_LABELS: Record<string, string> = {
  CONMEBOL: 'CONMEBOL',
  UEFA: 'UEFA',
  CONCACAF: 'CONCACAF',
  CAF: '\u00c1frica',
  AFC: 'Asia / Medio Oriente',
  OFC: 'Ocean\u00eda',
};

const SECTION_TITLES: Record<EditSection, string> = {
  name: '\u00bfC\u00f3mo te llamamos?',
  teams: '\u00bfA qui\u00e9n vas?',
};

function tierClass(tier: string): string {
  if (tier === 'S') return 'tier-s';
  if (tier === 'A') return 'tier-a';
  if (tier === 'B') return 'tier-b';
  return '';
}

interface Props {
  section: EditSection;
  onClose: () => void;
}

export default function ProfileEditModal({ section, onClose }: Props) {
  const dispatch = useAppDispatch();
  const { profile } = useAppState();

  const [name, setName] = useState('');
  const [tierMap, setTierMap] = useState<Record<string, string>>({});
  const [teams, setTeams] = useState<Team[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const p = profile;
    setName(p?.name ?? '');

    const affs = p?.team_affinities ?? {};
    const initTiers: Record<string, string> = {};
    for (const [t, v] of Object.entries(affs)) {
      const code = t.toUpperCase();
      if (v >= 0.9) initTiers[code] = 'S';
      else if (v >= 0.5) initTiers[code] = 'A';
      else if (v > 0) initTiers[code] = 'B';
    }
    setTierMap(initTiers);

    if (section === 'teams') {
      (async () => {
        try {
          setTeams(await getTeams());
        } catch { /* */ }
      })();
    }
  }, [profile, section]);

  const toggleTeam = useCallback((code: string) => {
    setTierMap((prev) => {
      const cur = prev[code] ?? '';
      const next = TIER_CYCLE[cur];
      if (next) return { ...prev, [code]: next };
      const copy = { ...prev };
      delete copy[code];
      return copy;
    });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);

    const teamAffinities: Record<string, number> = {};
    if (section === 'teams') {
      for (const [code, tier] of Object.entries(tierMap)) {
        teamAffinities[code] = TIER_AFFINITY[tier] ?? 0;
      }
    } else {
      for (const [code, val] of Object.entries(profile?.team_affinities ?? {})) {
        teamAffinities[code] = val;
      }
    }

    const payload: ProfileInput = {
      name: section === 'name' ? (name.trim() || 'Fan') : (profile?.name ?? 'Fan'),
      team_affinities: teamAffinities,
      time_windows: profile?.time_windows ?? [],
    };

    try {
      const data = await updateProfile(payload);
      dispatch({
        type: 'SET_PROFILE',
        profile: {
          name: payload.name,
          team_affinities: teamAffinities,
          time_windows: payload.time_windows,
        },
      });
      dispatch({
        type: 'SET_MATCHES',
        matches: data.matches,
        weights: data.weights,
        defaultWeights: data.default_weights,
        hasLearned: data.has_learned,
      });
      onClose();
    } catch { /* */ } finally {
      setSaving(false);
    }
  }, [section, name, tierMap, profile, dispatch, onClose]);

  const teamsByConf: Record<string, Team[]> = {};
  for (const t of teams) {
    if (!t.is_placeholder) {
      const c = t.confederation ?? 'Other';
      (teamsByConf[c] = teamsByConf[c] ?? []).push(t);
    }
  }

  return (
    <div
      id="modal-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div id="modal-box" style={{ maxWidth: section === 'name' ? 400 : 640 }}>
        <div className="wiz-hdr">
          <div className="wiz-hdr-top">
            <h2>{SECTION_TITLES[section]}</h2>
            <button className="btn btn-icon" onClick={onClose}>&#x2715;</button>
          </div>
        </div>

        <div className="wiz-body">
          {section === 'name' && (
            <div style={{ padding: '8px 0' }}>
              <input
                type="text"
                style={{ width: '100%', maxWidth: 340 }}
                placeholder="Ej: Rodrigo"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              />
            </div>
          )}

          {section === 'teams' && (
            <div>
              <div className="wiz-step-hint" style={{ marginBottom: 12 }}>
                Click cicla el nivel:{' '}
                <span className="tier-badge tier-badge-s">S</span> Favorito →{' '}
                <span className="tier-badge tier-badge-a">A</span> Me gusta →{' '}
                <span className="tier-badge tier-badge-b">B</span> Casual → sin inter&eacute;s.
              </div>
              <div id="teams-grid">
                {CONF_ORDER.map((conf) => {
                  const confTeams = teamsByConf[conf];
                  if (!confTeams?.length) return null;
                  return (
                    <div key={conf} className="conf-block">
                      <div className="conf-title">{CONF_LABELS[conf] ?? conf}</div>
                      <div className="team-toggle-grid">
                        {confTeams.map((t) => {
                          const tier = tierMap[t.fifa_code] ?? '';
                          return (
                            <button
                              key={t.fifa_code}
                              className={`team-toggle ${tierClass(tier)}`}
                              onClick={() => toggleTeam(t.fifa_code)}
                            >
                              {fl(t.fifa_code)} {t.fifa_code}
                              {tier && (
                                <span className={`tier-badge tier-badge-${tier.toLowerCase()}`}>
                                  {' '}{tier}
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="wiz-nav">
          <button className="btn" onClick={onClose}>Cancelar</button>
          <div style={{ flex: 1 }} />
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Guardando...' : '\u2713 Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}
