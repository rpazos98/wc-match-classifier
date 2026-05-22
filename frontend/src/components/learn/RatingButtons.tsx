import { useState, useCallback } from 'react';

interface Props {
  onRate: (rating: number) => void;
}

const RATINGS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

function ratingColor(r: number): string {
  if (r >= 8) return '#e83333';
  if (r >= 5) return '#e89515';
  return '#6a8a50';
}

export default function RatingButtons({ onRate }: Props) {
  const [chosen, setChosen] = useState<number | null>(null);

  const handleClick = useCallback(
    (r: number) => {
      if (chosen !== null) return; // already clicked
      setChosen(r);
      // Small delay for visual feedback, then fire callback
      setTimeout(() => {
        onRate(r);
        setChosen(null);
      }, 300);
    },
    [chosen, onRate],
  );

  return (
    <>
      <div className="learn-rating-label">
        ¿Qué tan imperdible es este partido? (1 = resumen · 10 = imperdible)
      </div>
      <div className="learn-rating-row">
        {RATINGS.map((r) => {
          const isChosen = chosen === r;
          const col = ratingColor(r);
          const style: React.CSSProperties =
            chosen !== null
              ? {
                  opacity: isChosen ? 1 : 0.25,
                  ...(isChosen
                    ? {
                        borderColor: col,
                        background: col + '33',
                        transform: 'translateY(-3px) scale(1.1)',
                      }
                    : {}),
                }
              : {};

          return (
            <button
              key={r}
              className="learn-rating-btn"
              data-r={r}
              style={style}
              onClick={() => handleClick(r)}
            >
              {r}
            </button>
          );
        })}
      </div>
      <div className="learn-rating-poles">
        <span>Resumen</span>
        <span>Imperdible</span>
      </div>
    </>
  );
}
