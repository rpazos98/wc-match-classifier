import { scoreColor } from '../../utils/labels';

interface ScoreRingProps {
  score: number;
  label: string;
  emoji: string;
}

export default function ScoreRing({ score, label, emoji }: ScoreRingProps) {
  const pct = score / 100;
  const R = 26;
  const circ = 2 * Math.PI * R;
  const dash = (pct * circ).toFixed(2);
  const gap = (circ - pct * circ).toFixed(2);
  const color = scoreColor(score);

  // Label badge colours
  const lColors: Record<string, string> = {
    Imperdible: '#e83333',
    'Vale la pena': '#e89515',
    'Para ver el resumen': '#4a6035',
  };
  const lColor = lColors[label] ?? '#4a6035';

  return (
    <>
      <div className="score-ring-wrap">
        <div className="score-ring">
          <svg viewBox="0 0 60 60" width={88} height={88}>
            <circle
              cx={30}
              cy={30}
              r={R}
              fill="none"
              stroke="var(--surf2)"
              strokeWidth={5}
            />
            <circle
              cx={30}
              cy={30}
              r={R}
              fill="none"
              stroke={color}
              strokeWidth={5}
              strokeDasharray={`${dash} ${gap}`}
              strokeLinecap="round"
            />
          </svg>
          <div className="score-val">
            <span className="score-num" style={{ color }}>
              {score}
            </span>
            <span className="score-sub">/ 100</span>
          </div>
        </div>
      </div>
      <span
        className="label-badge"
        style={{
          background: `${lColor}22`,
          color: lColor,
          border: `1px solid ${lColor}44`,
        }}
      >
        {emoji} {label}
      </span>
    </>
  );
}
