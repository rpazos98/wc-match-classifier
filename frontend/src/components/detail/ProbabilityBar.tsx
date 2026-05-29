import type { Prediction as MatchPrediction } from '../../types';
import { fl } from '../../utils/flags';

interface ProbabilityBarProps {
  prediction: MatchPrediction;
  home: string;
  away: string;
}

export default function ProbabilityBar({
  prediction,
  home,
  away,
}: ProbabilityBarProps) {
  const pH = Math.round(prediction.p_home * 100);
  const pD = Math.round(prediction.p_draw * 100);
  const pA = Math.round(prediction.p_away * 100);

  return (
    <div className="det-pred">
      <div className="det-section-title">Probabilities</div>
      <div className="pred-bar-wrap">
        <div className="pred-bar">
          <div className="pred-seg pred-home" style={{ width: `${pH}%` }}>
            {pH}%
          </div>
          <div className="pred-seg pred-draw" style={{ width: `${pD}%` }}>
            {pD}%
          </div>
          <div className="pred-seg pred-away" style={{ width: `${pA}%` }}>
            {pA}%
          </div>
        </div>
        <div className="pred-labels">
          <span>
            {fl(home)} {home}
          </span>
          <span style={{ color: 'var(--muted)' }}>Draw</span>
          <span>
            {fl(away)} {away}
          </span>
        </div>
      </div>
      <div className="pred-elo">
        ELO: {home} {prediction.elo_home} &mdash; {away} {prediction.elo_away}
      </div>
    </div>
  );
}
