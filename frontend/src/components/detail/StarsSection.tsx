import type { Star } from '../../types';
import { fl } from '../../utils/flags';

interface StarsSectionProps {
  stars: Star[];
}

export default function StarsSection({ stars }: StarsSectionProps) {
  if (!stars || stars.length === 0) return null;

  return (
    <div style={{ padding: '10px 16px', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {stars.map((s) => (
        <span key={`${s.team}-${s.name}`} className="star-chip">
          {fl(s.team)} {s.name}{' '}
          <span className="star-ovr">{s.overall}</span>
        </span>
      ))}
    </div>
  );
}
