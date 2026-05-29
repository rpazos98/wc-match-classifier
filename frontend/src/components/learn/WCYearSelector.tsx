import { useState } from 'react';

interface WCYearInfo {
  year: number;
  host: string;
  flag: string;
}

const WC_YEARS_INFO: WCYearInfo[] = [
  { year: 2022, host: 'Qatar',          flag: '\u{1F1F6}\u{1F1E6}' },
  { year: 2018, host: 'Russia',         flag: '\u{1F1F7}\u{1F1FA}' },
  { year: 2014, host: 'Brazil',          flag: '\u{1F1E7}\u{1F1F7}' },
  { year: 2010, host: 'South Africa',   flag: '\u{1F1FF}\u{1F1E6}' },
  { year: 2006, host: 'Germany',        flag: '\u{1F1E9}\u{1F1EA}' },
  { year: 2002, host: 'Korea/Japan',    flag: '\u{1F1F0}\u{1F1F7}' },
  { year: 1998, host: 'France',         flag: '\u{1F1EB}\u{1F1F7}' },
  { year: 1994, host: 'United States',  flag: '\u{1F1FA}\u{1F1F8}' },
  { year: 1990, host: 'Italy',          flag: '\u{1F1EE}\u{1F1F9}' },
  { year: 1986, host: 'Mexico',         flag: '\u{1F1F2}\u{1F1FD}' },
  { year: 1982, host: 'Spain',          flag: '\u{1F1EA}\u{1F1F8}' },
  { year: 1978, host: 'Argentina',      flag: '\u{1F1E6}\u{1F1F7}' },
  { year: 1974, host: 'Germany',         flag: '\u{1F1E9}\u{1F1EA}' },
  { year: 1970, host: 'Mexico',         flag: '\u{1F1F2}\u{1F1FD}' },
  { year: 1966, host: 'England',        flag: '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}' },
];

interface Props {
  onConfirm: (years: number[]) => void;
}

export default function WCYearSelector({ onConfirm }: Props) {
  const [checked, setChecked] = useState<Set<number>>(
    () => new Set(WC_YEARS_INFO.map((w) => w.year)),
  );

  function toggle(year: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(year)) next.delete(year);
      else next.add(year);
      return next;
    });
  }

  function handleConfirm() {
    const years = [...checked];
    if (years.length === 0) return;
    localStorage.setItem('wc2026_remembered_wcs', JSON.stringify(years));
    onConfirm(years);
  }

  return (
    <>
      <div style={{ textAlign: 'center', marginBottom: 14 }}>
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 14,
            letterSpacing: '1.5px',
            color: 'var(--gold)',
            marginBottom: 8,
          }}
        >
          WHICH WORLD CUPS DO YOU REMEMBER?
        </div>
        <div
          style={{
            color: 'var(--text-sm)',
            fontSize: 12,
            lineHeight: 1.6,
            maxWidth: 380,
            margin: '0 auto',
          }}
        >
          Select the World Cups you watched or have good memories of.
          <br />
          We'll show you matches you actually know.
        </div>
      </div>

      <div className="wc-check-grid">
        {WC_YEARS_INFO.map((w) => (
          <label key={w.year} className="wc-check" data-yr={w.year}>
            <input
              type="checkbox"
              value={w.year}
              checked={checked.has(w.year)}
              onChange={() => toggle(w.year)}
            />
            <span className="wc-check-label">
              {w.flag} {w.year} {w.host}
            </span>
          </label>
        ))}
      </div>

      <div style={{ textAlign: 'center', marginTop: 16 }}>
        <button
          className="btn btn-primary"
          style={{ fontSize: 13, padding: '8px 24px' }}
          onClick={handleConfirm}
          disabled={checked.size === 0}
        >
          Start →
        </button>
      </div>
    </>
  );
}
