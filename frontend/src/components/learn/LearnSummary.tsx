import type { FitRatingsResponse } from '../../types';

interface Props {
  result: FitRatingsResponse;
  onContinue: () => void;
  onReset: () => void;
  onApply: () => void;
}

export default function LearnSummary({
  result,
  onContinue,
  onReset,
  onApply,
}: Props) {
  const {
    weights: _weights,
    weight_delta,
    top_features,
    interactions,
    rating_stats,
    scorer_labels,
    total_examples,
    confidence,
    method,
  } = result;

  const n = rating_stats?.n ?? 0;
  const mean = rating_stats?.mean != null ? rating_stats.mean.toFixed(1) : '-';
  const totalStr =
    total_examples && total_examples > n
      ? ` (${total_examples} acumulados)`
      : '';

  // ── Rating distribution ───────────────────────────────────────────────────
  const dist = rating_stats?.dist ?? {};
  const maxCt = Math.max(1, ...Object.values(dist));

  function distColor(r: number): string {
    if (r >= 8) return '#e8333366';
    if (r >= 5) return '#e8951566';
    return '#4a603566';
  }

  // ── Confidence badge ──────────────────────────────────────────────────────
  const conf = confidence != null ? Math.round(confidence * 100) : null;
  const confColor =
    conf != null
      ? conf >= 60
        ? '#5ed64a'
        : conf >= 30
          ? '#e89515'
          : '#e83333'
      : undefined;

  // ── Weight deltas ─────────────────────────────────────────────────────────
  const deltas = weight_delta
    ? Object.entries(weight_delta)
        .map(([k, d]) => ({ k, d }))
        .filter((x) => Math.abs(x.d) >= 0.03)
        .sort((a, b) => Math.abs(b.d) - Math.abs(a.d))
        .slice(0, 5)
    : [];

  // ── Top features ──────────────────────────────────────────────────────────
  const maxImp = Math.max(
    0.01,
    ...top_features.map((f) => f.importance),
  );

  return (
    <div className="learn-summary">
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 20, marginBottom: 4 }}>&#x2705;</div>
        <div style={{ fontWeight: 800, fontSize: 14, color: '#fff' }}>
          Modelo actualizado con {n} partidos
          {totalStr && (
            <span
              style={{ color: 'var(--text-sm)', fontSize: 10 }}
            >
              {totalStr}
            </span>
          )}
        </div>
        <div
          style={{
            color: 'var(--text-sm)',
            fontSize: 11,
            marginTop: 2,
          }}
        >
          Rating promedio: {mean}/10
          {conf != null && (
            <span
              style={{ fontSize: 11, color: 'var(--text-sm)', marginLeft: 8 }}
            >
              Confianza:{' '}
              <b style={{ color: confColor }}>{conf}%</b>
            </span>
          )}
          {method && method !== 'prior' && (
            <span
              style={{
                fontSize: 9,
                marginLeft: 8,
                padding: '1px 5px',
                borderRadius: 3,
                background: method === 'ridge' ? '#5ed64a18' : '#e8951518',
                color: method === 'ridge' ? '#5ed64a' : '#e89515',
                textTransform: 'uppercase',
                letterSpacing: 0.5,
              }}
            >
              {method === 'ridge' ? 'Ridge ML' : 'Pearson'}
            </span>
          )}
        </div>
      </div>

      {/* Rating distribution */}
      <div className="learn-rating-dist">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((r) => {
          const ct = dist[String(r)] ?? 0;
          const h = Math.round((ct / maxCt) * 32);
          return (
            <div
              key={r}
              className="learn-dist-bar"
              style={{
                height: Math.max(3, h),
                background: distColor(r),
              }}
            >
              <span>{r}</span>
            </div>
          );
        })}
      </div>

      {/* Top features */}
      {top_features.length > 0 && (
        <div className="learn-feat-list">
          <div className="learn-rules-title">Factores más importantes</div>
          {top_features.map((f) => {
            const pct = Math.round((f.importance / maxImp) * 100);
            const label = (scorer_labels ?? {})[f.scorer] ?? f.scorer;
            return (
              <div key={f.scorer} className="learn-feat-row">
                <span className="learn-feat-name">{label}</span>
                <div className="learn-feat-bar-wrap">
                  <div
                    className="learn-feat-bar-fill"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="learn-feat-pct">{pct}%</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Learned interactions */}
      {interactions && Object.keys(interactions).length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="learn-rules-title">Combos descubiertos</div>
          <div style={{ margin: '4px 0 6px' }}>
            {Object.entries(interactions)
              .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
              .slice(0, 4)
              .map(([name, coef]) => {
                const positive = coef > 0;
                const col = positive ? '#5ed64a' : '#e83333';
                return (
                  <div
                    key={name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 11,
                      padding: '3px 0',
                      color: 'var(--text-sm)',
                    }}
                  >
                    <span
                      style={{
                        color: col,
                        fontWeight: 700,
                        fontSize: 10,
                        width: 14,
                        textAlign: 'center',
                      }}
                    >
                      {positive ? '+' : '−'}
                    </span>
                    <span style={{ flex: 1 }}>{name}</span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        color: col,
                      }}
                    >
                      {coef > 0 ? '+' : ''}{coef.toFixed(2)}
                    </span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Weight deltas */}
      {deltas.length > 0 && (
        <>
          <div className="learn-rules-title" style={{ marginTop: 12 }}>
            Pesos ajustados
          </div>
          <div style={{ margin: '4px 0 10px' }}>
            {deltas.map(({ k, d }) => {
              const label = (scorer_labels ?? {})[k] ?? k;
              const up = d > 0;
              const col = up ? '#5ed64a' : '#e83333';
              const pct = (d * 100).toFixed(1);
              return (
                <span
                  key={k}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                    margin: '2px 4px',
                    fontSize: 11,
                    color: col,
                    background: col + '18',
                    borderRadius: 4,
                    padding: '2px 6px',
                  }}
                >
                  {up ? '\u25b2' : '\u25bc'} {label} {up ? '+' : ''}
                  {pct}pt
                </span>
              );
            })}
          </div>
        </>
      )}

      {/* Actions */}
      <div
        style={{
          textAlign: 'center',
          marginTop: 18,
          display: 'flex',
          gap: 8,
          justifyContent: 'center',
          flexWrap: 'wrap',
        }}
      >
        <button
          className="btn"
          style={{
            fontSize: 12,
            padding: '8px 16px',
            color: 'var(--text-sm)',
          }}
          onClick={onContinue}
        >
          +10 partidos más
        </button>
        <button
          className="btn"
          style={{
            fontSize: 11,
            padding: '6px 12px',
            color: '#f56565',
            borderColor: '#f5656544',
          }}
          onClick={onReset}
        >
          Reiniciar
        </button>
        <button
          className="btn btn-primary"
          style={{ fontSize: 13, padding: '9px 24px' }}
          onClick={onApply}
        >
          Aplicar y cerrar
        </button>
      </div>
    </div>
  );
}
