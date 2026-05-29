import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { Team, Match } from '../../types';
import { getTeams } from '../../api/profile';
import { loadProfile } from '../../api/storage';
import { scoreKOMatch, loadScoringData, type ScoringData } from '../../scoring/classify';
import type { TeamProfile } from '../../simulation/engine';
import { fl } from '../../utils/flags';
import { scoreColor, LBL_IMP, LBL_VALE, LBL_RES } from '../../utils/labels';
import ScoreRing from '../detail/ScoreRing';
import ContributionList from '../detail/ContributionList';
import ProbabilityBar from '../detail/ProbabilityBar';

const BASE = import.meta.env.BASE_URL ?? '/';

const STAGES = [
  { value: 'group', label: 'Group Stage' },
  { value: 'r32', label: 'Round of 32' },
  { value: 'r16', label: 'Round of 16' },
  { value: 'qf', label: 'Quarter-finals' },
  { value: 'sf', label: 'Semi-finals' },
  { value: 'third_place', label: 'Third Place' },
  { value: 'final', label: 'Final' },
];

const STAGE_LABELS: Record<string, string> = {
  group: 'Group Stage',
  r32: 'Round of 32',
  r16: 'Round of 16',
  qf: 'Quarter-finals',
  sf: 'Semi-finals',
  third_place: 'Third Place',
  final: 'Grand Final!',
};

const PERSONAL_WEIGHT_FAV = 0.19;

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function MatchCreator({ isOpen, onClose }: Props) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [home, setHome] = useState('');
  const [away, setAway] = useState('');
  const [stage, setStage] = useState('group');
  const [result, setResult] = useState<Match | null>(null);
  const [error, setError] = useState('');
  const scoringDataRef = useRef<ScoringData | null>(null);
  // pairing key (sorted codes) → matchday (1|2|3)
  const matchdayLookupRef = useRef<Record<string, number>>({});

  // Load teams + scoring data + matchday lookup once
  useEffect(() => {
    if (isOpen && teams.length === 0) {
      getTeams().then(setTeams).catch(() => {});
    }
    if (isOpen && !scoringDataRef.current) {
      fetch(`${BASE}data/team_profiles.json`)
        .then(r => r.json())
        .then((profiles: Record<string, TeamProfile>) =>
          loadScoringData(profiles).then(sd => { scoringDataRef.current = sd; }),
        )
        .catch(() => {});
    }
    if (isOpen && Object.keys(matchdayLookupRef.current).length === 0) {
      Promise.all([
        fetch(`${BASE}data/matches.json`).then(r => r.json()),
        fetch(`${BASE}data/matchdays.json`).then(r => r.json()),
      ]).then(([matchesData, matchdays]: [{ matches: Array<{ match_id: string; home: string; away: string; stage: string }> }, Record<string, number>]) => {
        const lookup: Record<string, number> = {};
        for (const m of matchesData.matches) {
          if (m.stage !== 'group') continue;
          const mn = String(parseInt(m.match_id.replace('M', ''), 10));
          const md = matchdays[mn];
          if (md) {
            const key = [m.home, m.away].sort().join('-');
            lookup[key] = md;
          }
        }
        matchdayLookupRef.current = lookup;
      }).catch(() => {});
    }
  }, [isOpen, teams.length]);

  const sortedTeams = useMemo(() => {
    return [...teams].filter((t) => !t.is_placeholder).sort((a, b) => a.fifa_code.localeCompare(b.fifa_code));
  }, [teams]);

  // Derive group/matchday info for the selected pairing
  const groupInfo = useMemo(() => {
    if (stage !== 'group' || !home || !away) return null;
    const hTeam = teams.find(t => t.fifa_code === home);
    const aTeam = teams.find(t => t.fifa_code === away);
    if (!hTeam || !aTeam) return null;
    const sameGroup = hTeam.group_letter && hTeam.group_letter === aTeam.group_letter;
    const key = [home, away].sort().join('-');
    const md = matchdayLookupRef.current[key];
    return {
      sameGroup,
      group: sameGroup ? hTeam.group_letter : null,
      matchday: md ?? null,
    };
  }, [stage, home, away, teams]);

  // Auto-classify whenever home, away, or stage changes
  useEffect(() => {
    if (!home || !away || home === away || !scoringDataRef.current) {
      return;
    }
    classify();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [home, away, stage]);

  function classify() {
    if (!home || !away || home === away || !scoringDataRef.current) return;
    setError('');

    const data = scoringDataRef.current;

    // Look up matchday for group stage pairings
    let matchday: number | undefined;
    if (stage === 'group') {
      const key = [home, away].sort().join('-');
      matchday = matchdayLookupRef.current[key];
    }

    const intrinsic = scoreKOMatch(home, away, stage, undefined, data, matchday);

    // Personal scoring
    const profile = loadProfile();
    const affinities: Record<string, number> = {};
    for (const [k, v] of Object.entries(profile.team_affinities)) {
      affinities[k.toUpperCase()] = v;
    }

    let personalTotal = 0;
    const breakdown = { ...intrinsic.breakdown };
    const rawByScorer = { ...intrinsic.raw_by_scorer };
    const weightByScorer = { ...intrinsic.weight_by_scorer };
    const reasonByScorer = { ...intrinsic.reason_by_scorer };

    if (Object.keys(affinities).length > 0) {
      // Favorite Team
      const aH = affinities[home] ?? 0;
      const aA = affinities[away] ?? 0;
      if (aH > 0 || aA > 0) {
        const hi = Math.max(aH, aA);
        const lo = Math.min(aH, aA);
        const favRaw = Math.min(1.0, hi + 0.3 * lo);
        const favContrib = favRaw * PERSONAL_WEIGHT_FAV * 100;
        breakdown['Favorite Team'] = Math.round(favContrib * 10) / 10;
        rawByScorer['Favorite Team'] = favRaw;
        weightByScorer['Favorite Team'] = PERSONAL_WEIGHT_FAV;
        personalTotal += favContrib;

        // Momentum synergy
        const stageRaw = rawByScorer['Match Stage'] ?? 0;
        if (favRaw > 0.3 && stageRaw > 0.35) {
          const synergy = favRaw * stageRaw * 8.0;
          breakdown['Momentum'] = Math.round(synergy * 10) / 10;
          rawByScorer['Momentum'] = Math.round(favRaw * stageRaw * 10000) / 10000;
          weightByScorer['Momentum'] = 0.08;
          personalTotal += synergy;
        }
      }
    }

    const totalScore = Math.round(Math.min(intrinsic.total + personalTotal, 100) * 10) / 10;
    const label = totalScore >= 60 ? LBL_IMP : totalScore >= 30 ? LBL_VALE : LBL_RES;
    const emoji = totalScore >= 60 ? '\u{1F525}' : totalScore >= 30 ? '\u{1F440}' : '\u{1F4CB}';

    const match: Match = {
      match_id: `PREVIEW_${home}_${away}`,
      home,
      away,
      stage,
      stage_label: stage === 'group' && matchday
        ? `Group Stage — Matchday ${matchday}`
        : (STAGE_LABELS[stage] ?? stage),
      kickoff_utc: new Date().toISOString(),
      kickoff_local: '',
      venue: 'Hypothetical',
      score: totalScore,
      label,
      emoji,
      archetype: intrinsic.archetype,
      narrative: intrinsic.narrative,
      breakdown,
      raw_by_scorer: rawByScorer,
      weight_by_scorer: weightByScorer,
      reason_by_scorer: reasonByScorer,
      detail_by_scorer: intrinsic.detail_by_scorer,
      reasons: reasonByScorer,
      prediction: intrinsic.prediction as Match['prediction'],
      intrinsic_score: intrinsic.total,
      personal_score: Math.round(personalTotal),
      base_score: intrinsic.total,
      h2h: intrinsic.h2h,
      h2h_all: intrinsic.h2hAll,
      h2h_recent: intrinsic.h2hRecent,
      stars: intrinsic.stars,
    };

    setResult(match);
  }

  const handleSwap = useCallback(() => {
    setHome(away);
    setAway(home);
  }, [home, away]);

  if (!isOpen) return null;

  return (
    <div id="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div id="modal-box" style={{ maxWidth: 680 }}>
        <div className="wiz-hdr">
          <div className="wiz-hdr-top">
            <h2>Create Match</h2>
            <button className="btn btn-icon" onClick={onClose}>&#x2715;</button>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-sm)', padding: '0 24px 8px' }}>
            Select two teams and a stage to see how the classifier evaluates that match.
          </p>
        </div>

        <div className="wiz-body">
          {/* Team selection */}
          <div className="creator-selectors">
            <div className="creator-team-col">
              <label className="creator-label">Home</label>
              <select
                value={home}
                onChange={(e) => { setHome(e.target.value); }}
                className="creator-select"
              >
                <option value="">— Team —</option>
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
              <button className="btn btn-icon creator-swap" onClick={handleSwap} title="Swap">
                &#x21C4;
              </button>
              <span className="creator-vs-label">VS</span>
            </div>

            <div className="creator-team-col">
              <label className="creator-label">Away</label>
              <select
                value={away}
                onChange={(e) => { setAway(e.target.value); }}
                className="creator-select"
              >
                <option value="">— Team —</option>
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
            <label className="creator-label">Stage</label>
            <div className="creator-stage-chips">
              {STAGES.map((s) => (
                <button
                  key={s.value}
                  className={`creator-stage-chip${stage === s.value ? ' active' : ''}`}
                  onClick={() => { setStage(s.value); }}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Group/matchday badge */}
          {groupInfo && (
            <div style={{ textAlign: 'center', margin: '8px 0 0', fontSize: 12 }}>
              {groupInfo.sameGroup ? (
                <span style={{ color: 'var(--text-sm)', background: 'var(--surface)', padding: '4px 12px', borderRadius: 6 }}>
                  Group {groupInfo.group}
                  {groupInfo.matchday && <> &middot; <strong>Matchday {groupInfo.matchday}</strong></>}
                </span>
              ) : (
                <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>
                  Different groups — hypothetical matchup
                </span>
              )}
            </div>
          )}

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
                  <span style={{ color: 'var(--text-sm)', fontSize: 10 }}>INTRINSIC</span>
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
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
