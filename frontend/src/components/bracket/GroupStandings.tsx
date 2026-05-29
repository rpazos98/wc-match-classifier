import type { GroupStanding, Match } from '../../types';
import { fl } from '../../utils/flags';

interface Props {
  standings: GroupStanding[];
  matches?: Match[];   // group stage matches with scores
}

export default function GroupStandings({ standings, matches }: Props) {
  // Extract best third-place teams (qualified via third_place flag)
  const allThirds = standings
    .map((grp) => {
      const third = grp.teams[2]; // 3rd place in each group
      return third ? { ...third, group: grp.group } : null;
    })
    .filter((t): t is NonNullable<typeof t> => t != null)
    .sort((a, b) => {
      // FIFA criteria: pts → gd → gf
      if (b.pts !== a.pts) return b.pts - a.pts;
      if (b.gd !== a.gd) return b.gd - a.gd;
      return b.gf - a.gf;
    });

  // qualifiedThirds = first 8, rest eliminated (used in render below)

  // Group matches by group letter
  const matchesByGroup: Record<string, Match[]> = {};
  if (matches) {
    for (const m of matches) {
      if (m.stage !== 'group') continue;
      // Find which group this match belongs to
      for (const grp of standings) {
        const teamCodes = grp.teams.map((t) => t.team);
        if (teamCodes.includes(m.home) && teamCodes.includes(m.away)) {
          if (!matchesByGroup[grp.group]) matchesByGroup[grp.group] = [];
          matchesByGroup[grp.group].push(m);
          break;
        }
      }
    }
  }

  return (
    <>
      <div className="bracket-section-title">Group Stage</div>
      <div className="group-grid">
        {standings.map((grp) => (
          <div className="group-card" key={grp.group} style={{ minWidth: 200 }}>
            <div className="gc-hdr">Group {grp.group}</div>

            {/* Standings table */}
            <div style={{ display: 'flex', gap: 0, padding: '4px 10px 2px', fontSize: 9, color: 'var(--muted)', fontWeight: 700, letterSpacing: '0.5px' }}>
              <span style={{ flex: 1 }}>Team</span>
              <span style={{ width: 28, textAlign: 'center' }}>Pts</span>
              <span style={{ width: 28, textAlign: 'center' }}>GD</span>
              <span style={{ width: 28, textAlign: 'center' }}>GF</span>
              <span style={{ width: 16 }}></span>
            </div>
            {grp.teams.map((t, i) => {
              const cls = t.qualified
                ? 'qua'
                : t.third_place
                  ? 'thi'
                  : 'eli';
              const adv = t.qualified ? '\u2713' : t.third_place ? '*' : '';
              return (
                <div className={`gc-row ${cls}`} key={t.team}>
                  <span style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ fontSize: 9, color: 'var(--muted)', width: 12 }}>{i + 1}</span>
                    {fl(t.team)} {t.team}
                  </span>
                  <span className="gc-pts" style={{ width: 28, textAlign: 'center', fontWeight: 800 }}>{t.pts}</span>
                  <span className="gc-pts" style={{ width: 28, textAlign: 'center' }}>{t.gd > 0 ? '+' : ''}{t.gd}</span>
                  <span className="gc-pts" style={{ width: 28, textAlign: 'center' }}>{t.gf}</span>
                  <span className="gc-adv">{adv}</span>
                </div>
              );
            })}

            {/* Group match results */}
            {matchesByGroup[grp.group] && matchesByGroup[grp.group].length > 0 && (
              <div style={{ borderTop: '1px solid var(--border)', padding: '4px 10px 6px' }}>
                {matchesByGroup[grp.group].map((m) => (
                  <div key={m.match_id} style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    fontSize: 10, padding: '2px 0', color: 'var(--text-sm)',
                  }}>
                    <span style={{ flex: 1, textAlign: 'right', fontWeight: 600 }}>
                      {fl(m.home)} {m.home}
                    </span>
                    <span style={{
                      fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: 11,
                      color: 'var(--text)', minWidth: 32, textAlign: 'center',
                    }}>
                      {m.home_goals ?? '?'}-{m.away_goals ?? '?'}
                    </span>
                    <span style={{ flex: 1, fontWeight: 600 }}>
                      {m.away} {fl(m.away)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Best third-place teams */}
      {allThirds.length > 0 && (
        <>
          <div className="bracket-section-title" style={{ marginTop: 24 }}>
            Best Third-Place Teams
          </div>
          <div style={{
            background: 'var(--surf2)', border: '1px solid var(--border)',
            borderRadius: 8, overflow: 'hidden', maxWidth: 500, marginBottom: 24,
          }}>
            {/* Header */}
            <div style={{
              display: 'flex', gap: 0, padding: '6px 12px',
              fontSize: 9, color: 'var(--muted)', fontWeight: 700,
              letterSpacing: '0.5px', borderBottom: '1px solid var(--border)',
              background: 'var(--border2)',
            }}>
              <span style={{ width: 24 }}>#</span>
              <span style={{ flex: 1 }}>Team</span>
              <span style={{ width: 40, textAlign: 'center' }}>Group</span>
              <span style={{ width: 36, textAlign: 'center' }}>Pts</span>
              <span style={{ width: 36, textAlign: 'center' }}>GD</span>
              <span style={{ width: 36, textAlign: 'center' }}>GF</span>
              <span style={{ width: 60, textAlign: 'center' }}>Status</span>
            </div>
            {allThirds.map((t, i) => {
              const qualifies = i < 8;
              return (
                <div key={t.team} style={{
                  display: 'flex', alignItems: 'center', gap: 0,
                  padding: '5px 12px', fontSize: 12, fontWeight: 600,
                  borderBottom: i === 7 ? '2px solid var(--amber)' : '1px solid rgba(30,48,24,0.6)',
                  color: qualifies ? 'var(--text)' : 'var(--muted)',
                  background: qualifies ? 'rgba(232,149,21,0.04)' : 'transparent',
                }}>
                  <span style={{ width: 24, fontSize: 10, color: 'var(--muted)' }}>{i + 1}</span>
                  <span style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
                    {fl(t.team)} {t.team}
                  </span>
                  <span style={{ width: 40, textAlign: 'center', fontSize: 10, color: 'var(--text-sm)' }}>{t.group}</span>
                  <span style={{
                    width: 36, textAlign: 'center',
                    fontFamily: 'var(--font-mono)', fontWeight: 800,
                  }}>{t.pts}</span>
                  <span style={{
                    width: 36, textAlign: 'center',
                    fontFamily: 'var(--font-mono)',
                    color: t.gd > 0 ? 'var(--green)' : t.gd < 0 ? 'var(--red)' : 'var(--text-sm)',
                  }}>{t.gd > 0 ? '+' : ''}{t.gd}</span>
                  <span style={{
                    width: 36, textAlign: 'center',
                    fontFamily: 'var(--font-mono)',
                  }}>{t.gf}</span>
                  <span style={{
                    width: 60, textAlign: 'center', fontSize: 9, fontWeight: 800,
                    color: qualifies ? 'var(--green)' : 'var(--red)',
                  }}>
                    {qualifies ? '\u2713 Qualifies' : '\u2717 Eliminated'}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
