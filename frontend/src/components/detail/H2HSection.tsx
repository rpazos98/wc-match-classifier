interface H2HRecord {
  matches: number;
  a_wins: number;
  draws: number;
  b_wins: number;
  [key: string]: unknown;
}

interface H2HRecentMatch {
  date: string;
  tournament: string;
  a_goals: number;
  b_goals: number;
}

interface H2HSectionProps {
  home: string;
  away: string;
  h2h: H2HRecord | null;
  h2hAll: H2HRecord | null;
  h2hRecent: H2HRecentMatch[] | null;
}

function H2HBar({ h }: { h: H2HRecord }) {
  const t = h.matches;
  const wH = Math.round((h.a_wins / t) * 100);
  const wD = Math.round((h.draws / t) * 100);
  const wA = Math.round((h.b_wins / t) * 100);

  return (
    <div
      className="pred-bar"
      style={{ height: 14, borderRadius: 3 }}
    >
      <div
        className="pred-seg"
        style={{
          width: `${wH}%`,
          background: '#3a7bd5',
          fontSize: 9,
        }}
      >
        {h.a_wins || ''}
      </div>
      <div
        className="pred-seg"
        style={{
          width: `${wD}%`,
          background: '#555',
          fontSize: 9,
          minWidth: h.draws ? 18 : 0,
        }}
      >
        {h.draws || ''}
      </div>
      <div
        className="pred-seg"
        style={{
          width: `${wA}%`,
          background: '#d35400',
          fontSize: 9,
        }}
      >
        {h.b_wins || ''}
      </div>
    </div>
  );
}

export default function H2HSection({
  home,
  away,
  h2h,
  h2hAll,
  h2hRecent,
}: H2HSectionProps) {
  if (home === 'TBD' || away === 'TBD') return null;

  return (
    <div className="det-h2h">
      <div className="det-section-title">Head to Head</div>

      {/* World Cup record */}
      <div className="h2h-label">World Cups</div>
      {h2h && h2h.matches > 0 ? (
        <>
          <div className="h2h-summary">
            {h2h.matches}p: {home} {h2h.a_wins}W &middot; {h2h.draws}D
            &middot; {h2h.b_wins}W {away}
          </div>
          <H2HBar h={h2h} />
        </>
      ) : (
        <div className="h2h-summary">First time</div>
      )}

      {/* All-competition record */}
      {h2hAll && h2hAll.matches > 0 && (
        <>
          <div className="h2h-label" style={{ marginTop: 8 }}>
            All matches
          </div>
          <div className="h2h-summary">
            {h2hAll.matches}p: {home} {h2hAll.a_wins}W &middot;{' '}
            {h2hAll.draws}D &middot; {h2hAll.b_wins}W {away}
          </div>
          <H2HBar h={h2hAll} />
        </>
      )}

      {/* Recent matches */}
      {h2hRecent && h2hRecent.length > 0 && (
        <>
          <div className="h2h-label" style={{ marginTop: 8 }}>
            Recent matches
          </div>
          {h2hRecent.map((r, i) => {
            const result =
              r.a_goals > r.b_goals
                ? 'W'
                : r.a_goals < r.b_goals
                  ? 'L'
                  : 'D';
            const resultCol =
              result === 'W'
                ? 'var(--green)'
                : result === 'L'
                  ? '#e06060'
                  : 'var(--text-sm)';
            const tourney = r.tournament.replace('FIFA ', '');
            return (
              <div key={i} className="h2h-match">
                <span className="h2h-date">{r.date}</span>
                <span className="h2h-result" style={{ color: resultCol }}>
                  {r.a_goals}-{r.b_goals}
                </span>
                <span className="h2h-tourney">{tourney}</span>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
