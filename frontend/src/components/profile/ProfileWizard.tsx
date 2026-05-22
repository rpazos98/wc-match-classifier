import { useState, useEffect, useCallback, useRef } from 'react';
import type { Team, ProfileInput, TimeWindow } from '../../types';
import { getTeams, getPlayers, updateProfile } from '../../api/profile';
import { useAppState, useAppDispatch } from '../../state/AppContext';
import { fl } from '../../utils/flags';

// ── Constants ───────────────────────────────────────────────────────────────

const WIZ_STEPS = ['Nombre', 'Equipos', 'Jugadores', 'Horarios', 'Resumen'];
const TIER_CYCLE: Record<string, string> = { '': 'S', S: 'A', A: 'B', B: '' };
const TIER_AFFINITY: Record<string, number> = { S: 1.0, A: 0.65, B: 0.3 };
const CONF_ORDER = ['CONMEBOL', 'UEFA', 'CONCACAF', 'CAF', 'AFC', 'OFC'];
const CONF_LABELS: Record<string, string> = {
  CONMEBOL: 'CONMEBOL',
  UEFA: 'UEFA',
  CONCACAF: 'CONCACAF',
  CAF: 'África',
  AFC: 'Asia / Medio Oriente',
  OFC: 'Oceanía',
};
const DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const DAY_ABBRS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

// ── Timezone options ────────────────────────────────────────────────────────

const TZ_GROUPS: { label: string; options: { value: string; label: string }[] }[] = [
  {
    label: 'América del Norte / Centro',
    options: [
      { value: 'America/Mexico_City', label: 'México (Ciudad de México)' },
      { value: 'America/Monterrey', label: 'México (Monterrey)' },
      { value: 'America/Tijuana', label: 'México (Tijuana / Baja)' },
      { value: 'America/New_York', label: 'EE.UU. Este (Nueva York)' },
      { value: 'America/Chicago', label: 'EE.UU. Centro (Chicago)' },
      { value: 'America/Denver', label: 'EE.UU. Montaña (Denver)' },
      { value: 'America/Los_Angeles', label: 'EE.UU. Pacífico (Los Ángeles)' },
      { value: 'America/Toronto', label: 'Canadá (Toronto)' },
      { value: 'America/Vancouver', label: 'Canadá (Vancouver)' },
      { value: 'America/Panama', label: 'Panamá' },
      { value: 'America/Costa_Rica', label: 'Costa Rica' },
      { value: 'America/El_Salvador', label: 'El Salvador / Guatemala' },
      { value: 'America/Tegucigalpa', label: 'Honduras / Nicaragua' },
      { value: 'America/Santo_Domingo', label: 'República Dominicana' },
      { value: 'America/Port-au-Prince', label: 'Haití' },
    ],
  },
  {
    label: 'América del Sur',
    options: [
      { value: 'America/Argentina/Buenos_Aires', label: 'Argentina (Buenos Aires)' },
      { value: 'America/Sao_Paulo', label: 'Brasil (São Paulo)' },
      { value: 'America/Manaus', label: 'Brasil (Manaos)' },
      { value: 'America/Santiago', label: 'Chile' },
      { value: 'America/Bogota', label: 'Colombia / Ecuador / Perú' },
      { value: 'America/Lima', label: 'Perú' },
      { value: 'America/Caracas', label: 'Venezuela' },
      { value: 'America/La_Paz', label: 'Bolivia / Paraguay' },
      { value: 'America/Asuncion', label: 'Paraguay' },
      { value: 'America/Montevideo', label: 'Uruguay' },
      { value: 'America/Guyana', label: 'Guyana / Trinidad' },
    ],
  },
  {
    label: 'Europa',
    options: [
      { value: 'Europe/London', label: 'Reino Unido (Londres)' },
      { value: 'Europe/Lisbon', label: 'Portugal (Lisboa)' },
      { value: 'Europe/Madrid', label: 'España (Madrid)' },
      { value: 'Europe/Paris', label: 'Francia / Bélgica / Países Bajos' },
      { value: 'Europe/Berlin', label: 'Alemania / Austria / Suiza' },
      { value: 'Europe/Rome', label: 'Italia' },
      { value: 'Europe/Amsterdam', label: 'Países Bajos' },
      { value: 'Europe/Warsaw', label: 'Polonia / Serbia / Croacia' },
      { value: 'Europe/Belgrade', label: 'Serbia / Bosnia' },
      { value: 'Europe/Bucharest', label: 'Rumanía' },
      { value: 'Europe/Helsinki', label: 'Finlandia' },
      { value: 'Europe/Oslo', label: 'Noruega / Suecia / Dinamarca' },
      { value: 'Europe/Zurich', label: 'Suiza' },
      { value: 'Europe/Istanbul', label: 'Turquía' },
      { value: 'Europe/Moscow', label: 'Rusia (Moscú)' },
    ],
  },
  {
    label: 'África',
    options: [
      { value: 'Africa/Casablanca', label: 'Marruecos' },
      { value: 'Africa/Algiers', label: 'Argelia / Túnez' },
      { value: 'Africa/Cairo', label: 'Egipto' },
      { value: 'Africa/Lagos', label: 'Nigeria / Camerún / Costa de Marfil' },
      { value: 'Africa/Accra', label: 'Ghana' },
      { value: 'Africa/Johannesburg', label: 'Sudáfrica' },
      { value: 'Africa/Senegal', label: 'Senegal' },
    ],
  },
  {
    label: 'Oriente Medio / Asia',
    options: [
      { value: 'Asia/Riyadh', label: 'Arabia Saudita' },
      { value: 'Asia/Qatar', label: 'Qatar' },
      { value: 'Asia/Jordan', label: 'Jordania' },
      { value: 'Asia/Baghdad', label: 'Irak' },
      { value: 'Asia/Tehran', label: 'Irán' },
      { value: 'Asia/Tashkent', label: 'Uzbekistán' },
      { value: 'Asia/Tokyo', label: 'Japón' },
      { value: 'Asia/Seoul', label: 'Corea del Sur' },
      { value: 'Asia/Shanghai', label: 'China' },
      { value: 'Asia/Kolkata', label: 'India' },
      { value: 'Asia/Dubai', label: 'Emiratos Árabes' },
    ],
  },
  {
    label: 'Oceanía',
    options: [
      { value: 'Pacific/Auckland', label: 'Nueva Zelanda' },
      { value: 'Australia/Sydney', label: 'Australia (Sydney)' },
      { value: 'Australia/Melbourne', label: 'Australia (Melbourne)' },
      { value: 'Australia/Perth', label: 'Australia (Perth)' },
    ],
  },
  {
    label: 'UTC',
    options: [{ value: 'UTC', label: 'UTC' }],
  },
];

// ── Helper components ───────────────────────────────────────────────────────

function tierClass(tier: string): string {
  if (tier === 'S') return 'tier-s';
  if (tier === 'A') return 'tier-a';
  if (tier === 'B') return 'tier-b';
  return '';
}

function TierBadge({ tier }: { tier: string }) {
  if (!tier) return null;
  return (
    <span className={`tier-badge tier-badge-${tier.toLowerCase()}`}>
      {' '}{tier}
    </span>
  );
}

// ── Props ───────────────────────────────────────────────────────────────────

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

// ── Availability day row ────────────────────────────────────────────────────

interface DayRowData {
  enabled: boolean;
  startHour: number;
  endHour: number;
}

function AvailabilityRow({
  day,
  data,
  onChange,
}: {
  day: string;
  data: DayRowData;
  onChange: (d: DayRowData) => void;
}) {
  return (
    <div className="day-row">
      <input
        type="checkbox"
        checked={data.enabled}
        onChange={(e) => onChange({ ...data, enabled: e.target.checked })}
      />
      <label>{day}</label>
      <div className={`day-slider-wrap${data.enabled ? '' : ' off'}`}>
        <input
          type="range"
          className="time-slider"
          min={0}
          max={23}
          value={data.startHour}
          disabled={!data.enabled}
          onChange={(e) =>
            onChange({
              ...data,
              startHour: Math.min(parseInt(e.target.value), data.endHour - 1),
            })
          }
          style={{ flex: 1 }}
        />
        <input
          type="range"
          className="time-slider"
          min={0}
          max={23}
          value={data.endHour}
          disabled={!data.enabled}
          onChange={(e) =>
            onChange({
              ...data,
              endHour: Math.max(parseInt(e.target.value), data.startHour + 1),
            })
          }
          style={{ flex: 1 }}
        />
        <span className="slider-val">
          {data.enabled ? `${data.startHour}:00 – ${data.endHour}:00` : '–'}
        </span>
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export default function ProfileWizard({ isOpen, onClose }: Props) {
  const dispatch = useAppDispatch();
  const { profile } = useAppState();

  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [tierMap, setTierMap] = useState<Record<string, string>>({});
  const [teams, setTeams] = useState<Team[]>([]);
  const [playersByTeam, setPlayersByTeam] = useState<Record<string, string[]>>({});
  const [selectedPlayers, setSelectedPlayers] = useState<Set<string>>(new Set());
  const [timezone, setTimezone] = useState('America/Mexico_City');
  const [availability, setAvailability] = useState<DayRowData[]>(
    Array.from({ length: 7 }, () => ({ enabled: false, startHour: 14, endHour: 23 })),
  );
  const [saving, setSaving] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  // ── Init on open ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;

    setStep(0);

    // Populate from existing profile
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

    const tzVal = p?.time_windows?.[0]?.timezone ?? 'America/Mexico_City';
    setTimezone(tzVal);

    // Availability from profile
    const wMap: Record<number, TimeWindow> = {};
    for (const w of p?.time_windows ?? []) {
      if (w.weekday !== null && w.weekday !== undefined) wMap[w.weekday] = w;
    }
    setAvailability(
      Array.from({ length: 7 }, (_, i) => {
        const w = wMap[i];
        return w
          ? { enabled: true, startHour: w.start_hour, endHour: w.end_hour }
          : { enabled: false, startHour: 14, endHour: 23 };
      }),
    );

    setSelectedPlayers(new Set((p?.favorite_players ?? []).map((pl) => pl.toLowerCase())));

    // Fetch teams
    (async () => {
      try {
        const t = await getTeams();
        setTeams(t);
      } catch {
        // fallback
      }
    })();
  }, [isOpen, profile]);

  // ── Navigation ────────────────────────────────────────────────────────
  const goto = useCallback(
    (n: number) => {
      setStep(n);
      bodyRef.current?.scrollTo(0, 0);
    },
    [],
  );

  const wizNext = useCallback(async () => {
    if (step === WIZ_STEPS.length - 1) {
      // Save
      await handleSave();
      return;
    }
    const nextStep = step + 1;
    goto(nextStep);

    // Load players when entering step 2
    if (step === 1) {
      const sel = Object.keys(tierMap);
      const toFetch = sel.filter((c) => !playersByTeam[c]);
      if (toFetch.length) {
        try {
          const results = await Promise.all(
            toFetch.map(async (c) => {
              const players = await getPlayers(c);
              return [c, players] as const;
            }),
          );
          setPlayersByTeam((prev) => {
            const next = { ...prev };
            for (const [code, players] of results) {
              next[code] = players;
            }
            return next;
          });
        } catch {
          // non-critical
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, tierMap, playersByTeam]);

  const wizPrev = useCallback(() => {
    if (step === 0) return;
    goto(step - 1);
  }, [step, goto]);

  // ── Team toggle ───────────────────────────────────────────────────────
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

  // ── Player toggle ─────────────────────────────────────────────────────
  const togglePlayer = useCallback((playerName: string) => {
    setSelectedPlayers((prev) => {
      const next = new Set(prev);
      const key = playerName.toLowerCase();
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // ── Save ──────────────────────────────────────────────────────────────
  const handleSave = useCallback(async () => {
    setSaving(true);
    const teamAffinities: Record<string, number> = {};
    for (const [code, tier] of Object.entries(tierMap)) {
      teamAffinities[code] = TIER_AFFINITY[tier] ?? 0;
    }

    const windows: TimeWindow[] = [];
    for (let i = 0; i < 7; i++) {
      const a = availability[i];
      if (a.enabled) {
        windows.push({
          weekday: i,
          start_hour: a.startHour,
          end_hour: a.endHour,
          timezone,
        });
      }
    }

    // Collect actual player names (case-preserved)
    const allPlayers: string[] = [];
    for (const code of Object.keys(tierMap)) {
      for (const p of (playersByTeam[code] ?? []).slice(0, 10)) {
        if (selectedPlayers.has(p.toLowerCase())) {
          allPlayers.push(p);
        }
      }
    }

    const payload: ProfileInput = {
      name: name.trim() || 'Fan',
      team_affinities: teamAffinities,
      favorite_players: allPlayers,
      time_windows: windows,
    };

    try {
      const data = await updateProfile(payload);

      dispatch({
        type: 'SET_PROFILE',
        profile: {
          name: payload.name,
          team_affinities: teamAffinities,
          favorite_players: allPlayers,
          time_windows: windows,
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
    } catch {
      // error handling could be improved
    } finally {
      setSaving(false);
    }
  }, [
    name, tierMap, availability, timezone, selectedPlayers,
    playersByTeam, dispatch, onClose,
  ]);

  // ── Derived data ──────────────────────────────────────────────────────

  // Teams grouped by confederation
  const teamsByConf: Record<string, Team[]> = {};
  for (const t of teams) {
    if (!t.is_placeholder) {
      const c = t.confederation ?? 'Other';
      (teamsByConf[c] = teamsByConf[c] ?? []).push(t);
    }
  }

  // Players from selected teams
  const visiblePlayers: { name: string; code: string }[] = [];
  const seenPlayers = new Set<string>();
  for (const code of Object.keys(tierMap)) {
    for (const p of (playersByTeam[code] ?? []).slice(0, 10)) {
      if (!seenPlayers.has(p)) {
        seenPlayers.add(p);
        visiblePlayers.push({ name: p, code });
      }
    }
  }

  // Summary data
  const tiers: Record<string, string[]> = { S: [], A: [], B: [] };
  for (const [code, tier] of Object.entries(tierMap)) {
    if (tiers[tier]) tiers[tier].push(code);
  }

  const summaryPlayers = visiblePlayers.filter((p) =>
    selectedPlayers.has(p.name.toLowerCase()),
  );

  const summaryWindows = availability
    .map((a, i) => (a.enabled ? { day: DAY_ABBRS[i], start: a.startHour, end: a.endHour } : null))
    .filter(Boolean) as { day: string; start: number; end: number }[];

  // ── Render ────────────────────────────────────────────────────────────
  if (!isOpen) return null;

  const isLast = step === WIZ_STEPS.length - 1;

  return (
    <div
      id="modal-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div id="modal-box">
        {/* Header */}
        <div className="wiz-hdr">
          <div className="wiz-hdr-top">
            <h2>Configura tu perfil</h2>
            <button className="btn btn-icon" onClick={onClose}>
              &#x2715;
            </button>
          </div>

          {/* Step dots */}
          <div className="wiz-steps-bar" id="wiz-steps-bar">
            {WIZ_STEPS.map((label, i) => {
              const cls = i === step ? 'active' : i < step ? 'done' : '';
              const icon = i < step ? '\u2713' : String(i + 1);
              return (
                <span key={i} style={{ display: 'contents' }}>
                  {i > 0 && (
                    <div className={`wiz-line${i <= step ? ' done' : ''}`} />
                  )}
                  <div className={`wiz-dot ${cls}`}>
                    <div className="wiz-dot-circle">{icon}</div>
                    <div className="wiz-dot-label">{label}</div>
                  </div>
                </span>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="wiz-body" ref={bodyRef}>
          {/* Step 0: Name */}
          <div className={`wiz-step${step === 0 ? ' active' : ''}`}>
            <div className="wiz-step-title">¿Cómo te llamamos?</div>
            <div className="wiz-step-hint">
              Tu nombre aparece en el panel lateral del clasificador.
            </div>
            <input
              type="text"
              style={{ width: '100%', maxWidth: 340 }}
              placeholder="Ej: Rodrigo"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* Step 1: Teams */}
          <div className={`wiz-step${step === 1 ? ' active' : ''}`}>
            <div className="wiz-step-title">¿A quién vas?</div>
            <div className="wiz-step-hint">
              Click cicla el nivel:{' '}
              <span className="tier-badge tier-badge-s">S</span> Favorito →{' '}
              <span className="tier-badge tier-badge-a">A</span> Me gusta →{' '}
              <span className="tier-badge tier-badge-b">B</span> Casual → sin interés.
            </div>
            <div id="teams-grid">
              {CONF_ORDER.map((conf) => {
                const confTeams = teamsByConf[conf];
                if (!confTeams?.length) return null;
                return (
                  <div key={conf} className="conf-block">
                    <div className="conf-title">
                      {CONF_LABELS[conf] ?? conf}
                    </div>
                    <div className="team-toggle-grid">
                      {confTeams.map((t) => {
                        const tier = tierMap[t.fifa_code] ?? '';
                        return (
                          <button
                            key={t.fifa_code}
                            className={`team-toggle ${tierClass(tier)}`}
                            data-code={t.fifa_code}
                            onClick={() => toggleTeam(t.fifa_code)}
                          >
                            {fl(t.fifa_code)} {t.fifa_code}
                            <TierBadge tier={tier} />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Step 2: Players */}
          <div className={`wiz-step${step === 2 ? ' active' : ''}`}>
            <div className="wiz-step-title">Jugadores favoritos</div>
            <div className="wiz-step-hint">
              De tus equipos seleccionados. Puedes saltarte este paso.
            </div>
            <div className="player-grid" id="players-grid">
              {visiblePlayers.length === 0 ? (
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {Object.keys(tierMap).length === 0
                    ? 'Selecciona equipos arriba'
                    : 'Cargando...'}
                </span>
              ) : (
                visiblePlayers.map((p) => (
                  <label key={p.name} className="player-cb-lbl">
                    <input
                      type="checkbox"
                      name="player"
                      value={p.name}
                      checked={selectedPlayers.has(p.name.toLowerCase())}
                      onChange={() => togglePlayer(p.name)}
                    />
                    <span>{p.name}</span>
                  </label>
                ))
              )}
            </div>
          </div>

          {/* Step 3: Availability */}
          <div className={`wiz-step${step === 3 ? ' active' : ''}`}>
            <div className="wiz-step-title">
              ¿Cuándo puedes ver los partidos?
            </div>
            <div className="wiz-step-hint">
              Marca los días y ajusta el rango horario en tu zona.
            </div>

            <div className="modal-lbl" style={{ marginTop: 0 }}>
              Zona horaria
            </div>
            <select
              style={{ width: 280 }}
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              {TZ_GROUPS.map((g) => (
                <optgroup key={g.label} label={g.label}>
                  {g.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>

            <div className="modal-lbl">Disponibilidad (hora local)</div>
            <div id="avail-rows">
              {DAYS.map((day, i) => (
                <AvailabilityRow
                  key={i}
                  day={day}
                  data={availability[i]}
                  onChange={(d) =>
                    setAvailability((prev) => {
                      const next = [...prev];
                      next[i] = d;
                      return next;
                    })
                  }
                />
              ))}
            </div>
          </div>

          {/* Step 4: Summary */}
          <div className={`wiz-step${step === 4 ? ' active' : ''}`}>
            <div className="wiz-step-title">¿Todo se ve bien?</div>
            <div className="wiz-step-hint">
              Presiona Guardar para aplicar tu perfil al clasificador.
            </div>
            <div id="wiz-summary">
              {/* Teams summary */}
              <div className="wiz-summary-section">
                <div className="wiz-summary-label">Equipos</div>
                {(['S', 'A', 'B'] as const).map((t) => {
                  if (!tiers[t].length) return null;
                  const label =
                    t === 'S' ? 'Favorito' : t === 'A' ? 'Me gusta' : 'Casual';
                  return (
                    <div key={t} style={{ marginBottom: 8 }}>
                      <span
                        className={`tier-badge tier-badge-${t.toLowerCase()}`}
                      >
                        {t}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          color: 'var(--text-sm)',
                          marginLeft: 4,
                        }}
                      >
                        {label}
                      </span>
                      <div
                        style={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 4,
                          marginTop: 5,
                        }}
                      >
                        {tiers[t].map((code) => (
                          <span key={code} className="wiz-summary-tag">
                            {fl(code)} {code}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {Object.keys(tierMap).length === 0 && (
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}>
                    Sin equipos seleccionados
                  </span>
                )}
              </div>

              {/* Players summary */}
              <div className="wiz-summary-section">
                <div className="wiz-summary-label">Jugadores favoritos</div>
                {summaryPlayers.length > 0 ? (
                  <div
                    style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}
                  >
                    {summaryPlayers.map((p) => (
                      <span key={p.name} className="wiz-summary-tag">
                        {p.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}>
                    Ninguno seleccionado
                  </span>
                )}
              </div>

              {/* Availability summary */}
              <div className="wiz-summary-section">
                <div className="wiz-summary-label">Horarios</div>
                <div
                  style={{
                    color: 'var(--text-sm)',
                    fontSize: 11,
                    marginBottom: 8,
                  }}
                >
                  {timezone}
                </div>
                {summaryWindows.length > 0 ? (
                  <div
                    style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}
                  >
                    {summaryWindows.map((w) => (
                      <span key={w.day} className="wiz-summary-tag">
                        {w.day} {w.start}:00–{w.end}:00
                      </span>
                    ))}
                  </div>
                ) : (
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}>
                    Sin restricción de horario
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="wiz-nav">
          <button className="btn" onClick={onClose}>
            Cancelar
          </button>
          <div style={{ flex: 1 }} />
          <button
            className="btn"
            id="wiz-btn-prev"
            onClick={wizPrev}
            disabled={step === 0}
          >
            ← Anterior
          </button>
          <button
            className="btn btn-primary"
            id="wiz-btn-next"
            onClick={wizNext}
            disabled={saving}
          >
            {saving
              ? 'Guardando...'
              : isLast
                ? '\u2713 Guardar'
                : 'Siguiente →'}
          </button>
        </div>
      </div>
    </div>
  );
}
