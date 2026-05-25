import { useState, useEffect, useCallback, useMemo } from 'react';
import type { Team, Match } from '../../types';
import { getTeams } from '../../api/profile';
import { previewMatch } from '../../api/matches';
import { fl } from '../../utils/flags';
import { scoreColor } from '../../utils/labels';
import ScoreRing from '../detail/ScoreRing';
import ContributionList from '../detail/ContributionList';
import ProbabilityBar from '../detail/ProbabilityBar';

const STAGES = [
  { value: 'group', label: 'Fase de Grupos' },
  { value: 'r32', label: 'Ronda de 32' },
  { value: 'r16', label: 'Octavos de Final' },
  { value: 'qf', label: 'Cuartos de Final' },
  { value: 'sf', label: 'Semifinal' },
  { value: 'third_place', label: 'Tercer Lugar' },
  { value: 'final', label: 'Final' },
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function MatchCreator({ isOpen, onClose }: Props) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [home, setHome] = useState('');
  const [away, setAway] = useState('');
  const [stage, setStage] = useState('group');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Match | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && teams.length === 0) {
      getTeams().then(setTeams).catch(() => {});
    }
  }, [isOpen, teams.length]);

  const sortedTeams = useMemo(() => {
    return [...teams].filter((t) => !t.is_placeholder).sort((a, b) => a.fifa_code.localeCompare(b.fifa_code));
  }, [teams]);

  const handleClassify = useCallback(async () => {
    if (!home || !away) return;
    if (home === away) {
      setError('Selecciona dos equipos diferentes');
      return;
    }
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const data = await previewMatch(home, away, stage);
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data.match);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al clasificar');
    } finally {
      setLoading(false);
    }
  }, [home, away, stage]);

  const handleSwap = useCallback(() => {
    setHome(away);
    setAway(home);
    setResult(null);
  }, [home, away]);

  if (!isOpen) return null;

  return (
    <div id="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div id="modal-box" style={{ maxWidth: 680 }}>
        <div className="wiz-hdr">
          <div className="wiz-hdr-top">
            <h2>Crear Partido</h2>
            <button className="btn btn-icon" onClick={onClose}>&#x2715;</button>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-sm)', padding: '0 24px 8px' }}>
            Selecciona dos equipos y una fase para ver como el clasificador evalua ese partido.
          </p>
        </div>

        <div className="wiz-body">
          {/* Team selection */}
          <div className="creator-selectors">
            <div className="creator-team-col">
              <label className="creator-label">Local</label>
              <select
                value={home}
                onChange={(e) => { setHome(e.target.value); setResult(null); }}
                className="creator-select"
              >
                <option value="">— Equipo —</option>
                {sortedTeams.map((t) => (
                  <option key={t.fifa_code} value={t.fifa_code} disabled={t.fifa_code === away}>
                    {fl(t.fifa_code)} {t.team_name} ({t.fifa_code})
                  </option>
                ))}
              </select>
              {home && (
                <div className="creator-team-badge">
                  <span style={{ fontSize: 32 }}>{fl(home)}</span>
                  <span className="creator-team-code">{home}</span>
                </div>
              )}
            </div>

            <div className="creator-vs">
              <button className="btn btn-icon creator-swap" onClick={handleSwap} title="Intercambiar">
                &#x21C4;
              </button>
              <span className="creator-vs-label">VS</span>
            </div>

            <div className="creator-team-col">
              <label className="creator-label">Visitante</label>
              <select
                value={away}
                onChange={(e) => { setAway(e.target.value); setResult(null); }}
                className="creator-select"
              >
                <option value="">— Equipo —</option>
                {sortedTeams.map((t) => (
                  <option key={t.fifa_code} value={t.fifa_code} disabled={t.fifa_code === home}>
                    {fl(t.fifa_code)} {t.team_name} ({t.fifa_code})
                  </option>
                ))}
              </select>
              {away && (
                <div className="creator-team-badge">
                  <span style={{ fontSize: 32 }}>{fl(away)}</span>
                  <span className="creator-team-code">{away}</span>
                </div>
              )}
            </div>
          </div>

          {/* Stage */}
          <div className="creator-stage-row">
            <label className="creator-label">Fase</label>
            <div className="creator-stage-chips">
              {STAGES.map((s) => (
                <button
                  key={s.value}
                  className={`creator-stage-chip${stage === s.value ? ' active' : ''}`}
                  onClick={() => { setStage(s.value); setResult(null); }}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Classify button */}
          <div style={{ textAlign: 'center', margin: '16px 0 8px' }}>
            <button
              className="btn btn-primary"
              onClick={handleClassify}
              disabled={!home || !away || home === away || loading}
              style={{ minWidth: 200, fontSize: 14 }}
            >
              {loading ? 'Clasificando...' : 'Clasificar Partido'}
            </button>
          </div>

          {error && (
            <div style={{ color: 'var(--red)', textAlign: 'center', fontSize: 12, marginTop: 4 }}>
              {error}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="creator-result">
              <div className="creator-result-header">
                <span style={{ fontSize: 20 }}>{fl(result.home)}</span>
                <span className="creator-team-code">{result.home}</span>
                <span className="creator-vs-label" style={{ margin: '0 8px' }}>vs</span>
                <span className="creator-team-code">{result.away}</span>
                <span style={{ fontSize: 20 }}>{fl(result.away)}</span>
                <span style={{ margin: '0 0 0 12px', fontSize: 11, color: 'var(--text-sm)' }}>
                  {result.stage_label}
                </span>
              </div>

              {result.archetype && (
                <div style={{ textAlign: 'center', margin: '4px 0', fontSize: 12, color: 'var(--text-sm)' }}>
                  {result.archetype.icon} {result.archetype.label}
                </div>
              )}

              {result.narrative && (
                <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--muted)', margin: '0 0 8px', fontStyle: 'italic' }}>
                  {result.narrative}
                </div>
              )}

              <div className="creator-score-section">
                <ScoreRing score={result.score} label={result.label} emoji={result.emoji} />
              </div>

              {result.prediction && (
                <div style={{ margin: '12px 0' }}>
                  <ProbabilityBar
                    prediction={result.prediction}
                    home={result.home}
                    away={result.away}
                  />
                </div>
              )}

              <div className="creator-breakdown">
                <ContributionList
                  breakdown={result.breakdown}
                  rawByScorer={result.raw_by_scorer}
                  weightByScorer={result.weight_by_scorer}
                  reasonByScorer={result.reason_by_scorer}
                  detailByScorer={result.detail_by_scorer}
                  score={result.score}
                />
              </div>

              <div className="creator-scores-row">
                <div className="creator-score-pill">
                  <span style={{ color: 'var(--text-sm)', fontSize: 10 }}>INTRINSECO</span>
                  <span style={{ color: scoreColor(result.intrinsic_score), fontWeight: 700 }}>
                    {result.intrinsic_score}
                  </span>
                </div>
                <div className="creator-score-pill">
                  <span style={{ color: 'var(--text-sm)', fontSize: 10 }}>PERSONAL</span>
                  <span style={{ color: 'var(--gold)', fontWeight: 700 }}>
                    {result.personal_score}
                  </span>
                </div>
                <div className="creator-score-pill">
                  <span style={{ color: 'var(--text-sm)', fontSize: 10 }}>BASE</span>
                  <span style={{ color: 'var(--muted)', fontWeight: 700 }}>
                    {result.base_score}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="wiz-nav">
          <button className="btn" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}
