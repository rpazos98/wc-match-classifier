/**
 * Preference learning — TypeScript port of classifier/learning.py.
 *
 * Ridge regression with interaction features, Pearson fallback for < 5 samples,
 * Bayesian blend with default weights using confidence ramp.
 *
 * No external dependencies — matrix math is inlined.
 */

// ── Constants ────────────────────────────────────────────────────────────────

export const SCORER_NAMES = [
  "Favorite Team",
  "Competitive Tension",
  "Match Stage",
  "Star Power",
  "Chaos Potential",
  "Form",
  "Narrative",
  "Same Group",
] as const;

const INTERACTION_PAIRS: [string, string][] = [
  ["Favorite Team", "Match Stage"],
  ["Competitive Tension", "Star Power"],
  ["Chaos Potential", "Match Stage"],
  ["Competitive Tension", "Narrative"],
  ["Favorite Team", "Star Power"],
  ["Chaos Potential", "Narrative"],
  ["Competitive Tension", "Chaos Potential"],
];

const INTERACTION_NAMES = INTERACTION_PAIRS.map(([a, b]) => `${a} × ${b}`);

export const DEFAULT_WEIGHTS: Record<string, number> = {
  "Favorite Team": 0.19,
  "Competitive Tension": 0.18,
  "Match Stage": 0.17,
  "Star Power": 0.17,
  "Chaos Potential": 0.12,
  "Form": 0.08,
  "Narrative": 0.06,
  "Same Group": 0.03,
};

const RAMP_N = 20;
const N_BASE = SCORER_NAMES.length;
const N_INTERACT = INTERACTION_PAIRS.length;
// const N_FEATURES = N_BASE + N_INTERACT;

// ── Types ────────────────────────────────────────────────────────────────────

export interface RatedExample {
  raw: Record<string, number>;
  rating: number;
}

export interface TopFeature {
  scorer: string;
  importance: number;
}

export interface RatingStats {
  mean: number;
  min: number;
  max: number;
  n: number;
  dist: Record<string, number>;
}

export interface FitResult {
  weights: Record<string, number>;
  weight_delta: Record<string, number>;
  top_features: TopFeature[];
  interactions: Record<string, number>;
  rating_stats: RatingStats;
  confidence: number;
  method: "prior" | "pearson" | "ridge";
  scorer_labels?: Record<string, string>;
  total_examples?: number;
}

// ── Feature matrix ───────────────────────────────────────────────────────────

function buildFeatureRow(raw: Record<string, number>): number[] {
  const row: number[] = [];
  for (const s of SCORER_NAMES) row.push(raw[s] ?? 0.5);
  for (const [a, b] of INTERACTION_PAIRS) row.push((raw[a] ?? 0.5) * (raw[b] ?? 0.5));
  return row;
}

function buildFeatureMatrix(examples: RatedExample[]): { X: number[][]; y: number[] } {
  const X = examples.map((ex) => buildFeatureRow(ex.raw));
  const y = examples.map((ex) => ex.rating);
  return { X, y };
}

// ── Matrix math (small matrices only) ────────────────────────────────────────

function transpose(A: number[][]): number[][] {
  const rows = A.length, cols = A[0].length;
  const T: number[][] = Array.from({ length: cols }, () => new Array(rows));
  for (let i = 0; i < rows; i++)
    for (let j = 0; j < cols; j++)
      T[j][i] = A[i][j];
  return T;
}

function matMul(A: number[][], B: number[][]): number[][] {
  const m = A.length, n = B[0].length, p = B.length;
  const C: number[][] = Array.from({ length: m }, () => new Array(n).fill(0));
  for (let i = 0; i < m; i++)
    for (let j = 0; j < n; j++)
      for (let k = 0; k < p; k++)
        C[i][j] += A[i][k] * B[k][j];
  return C;
}

function matVecMul(A: number[][], v: number[]): number[] {
  return A.map((row) => row.reduce((s, a, i) => s + a * v[i], 0));
}

/** Gauss-Jordan inversion for small square matrices. */
function invert(M: number[][]): number[][] {
  const n = M.length;
  // Augment [M | I]
  const A = M.map((row, i) => {
    const aug = new Array(2 * n).fill(0);
    for (let j = 0; j < n; j++) aug[j] = row[j];
    aug[n + i] = 1;
    return aug;
  });

  for (let col = 0; col < n; col++) {
    // Partial pivot
    let maxRow = col;
    for (let r = col + 1; r < n; r++)
      if (Math.abs(A[r][col]) > Math.abs(A[maxRow][col])) maxRow = r;
    [A[col], A[maxRow]] = [A[maxRow], A[col]];

    const pivot = A[col][col];
    if (Math.abs(pivot) < 1e-12) {
      // Singular — add regularization and retry shouldn't happen with Ridge
      A[col][col] += 1e-6;
    }
    const inv = 1 / A[col][col];
    for (let j = 0; j < 2 * n; j++) A[col][j] *= inv;

    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const factor = A[r][col];
      for (let j = 0; j < 2 * n; j++) A[r][j] -= factor * A[col][j];
    }
  }

  return A.map((row) => row.slice(n));
}

// ── Ridge regression ────────────────────────────────────────────────────────

function ridgeFit(
  X: number[][],
  y: number[],
  alpha = 1.0,
): { coefs: number[]; intercept: number } {
  const n = X.length;
  const p = X[0].length;

  // Center y
  const yMean = y.reduce((s, v) => s + v, 0) / n;
  const yc = y.map((v) => v - yMean);

  // Center X columns
  const colMeans = new Array(p).fill(0);
  for (let j = 0; j < p; j++) {
    for (let i = 0; i < n; i++) colMeans[j] += X[i][j];
    colMeans[j] /= n;
  }
  const Xc = X.map((row) => row.map((v, j) => v - colMeans[j]));

  // XtX + αI
  const Xt = transpose(Xc);
  const XtX = matMul(Xt, Xc);
  for (let i = 0; i < p; i++) XtX[i][i] += alpha;

  // Xty
  const Xty = matVecMul(Xt, yc);

  // Solve: coefs = (XtX)^-1 Xty
  const XtXinv = invert(XtX);
  const coefs = matVecMul(XtXinv, Xty);

  // Intercept
  const intercept = yMean - colMeans.reduce((s, m, j) => s + m * coefs[j], 0);

  return { coefs, intercept };
}

function ridgePredict(
  X: number[][],
  coefs: number[],
  intercept: number,
): number[] {
  return X.map((row) => row.reduce((s, v, j) => s + v * coefs[j], 0) + intercept);
}

// ── Extract weights from Ridge ──────────────────────────────────────────────

function ridgeToWeights(coefs: number[]): Record<string, number> {
  const baseCoefs = coefs.slice(0, N_BASE);
  const importance = baseCoefs.map((c) => Math.max(0, c));
  const sum = importance.reduce((s, v) => s + v, 0);

  if (sum < 1e-9) {
    return Object.fromEntries(SCORER_NAMES.map((n) => [n, 1 / N_BASE]));
  }

  return Object.fromEntries(
    SCORER_NAMES.map((n, i) => [n, Math.round((importance[i] / sum) * 10000) / 10000]),
  );
}

function ridgeToInteractions(coefs: number[]): Record<string, number> {
  const interCoefs = coefs.slice(N_BASE);
  const result: Record<string, number> = {};
  for (let i = 0; i < N_INTERACT; i++) {
    const v = Math.round(interCoefs[i] * 10000) / 10000;
    if (Math.abs(v) > 0.1) result[INTERACTION_NAMES[i]] = v;
  }
  return result;
}

// ── Pearson correlation ─────────────────────────────────────────────────────

function pearson(x: number[], y: number[]): number {
  const n = x.length;
  if (n < 3) return 0;
  const mx = x.reduce((s, v) => s + v, 0) / n;
  const my = y.reduce((s, v) => s + v, 0) / n;
  let num = 0, dx2 = 0, dy2 = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - mx, dy = y[i] - my;
    num += dx * dy;
    dx2 += dx * dx;
    dy2 += dy * dy;
  }
  const denom = Math.sqrt(dx2 * dy2);
  return denom < 1e-9 ? 0 : num / denom;
}

function pearsonWeights(X: number[][], y: number[]): Record<string, number> {
  const raw = SCORER_NAMES.map((_, i) => Math.max(0, pearson(X.map((r) => r[i]), y)));
  const sum = raw.reduce((s, v) => s + v, 0);
  if (sum < 1e-9) return Object.fromEntries(SCORER_NAMES.map((n) => [n, 1 / N_BASE]));
  return Object.fromEntries(SCORER_NAMES.map((n, i) => [n, Math.round((raw[i] / sum) * 10000) / 10000]));
}

// ── Bayesian blend ──────────────────────────────────────────────────────────

function blend(
  prior: Record<string, number>,
  data: Record<string, number>,
  nRatings: number,
): Record<string, number> {
  const alpha = Math.min(1.0, nRatings / RAMP_N);
  const blended: Record<string, number> = {};
  for (const name of SCORER_NAMES) {
    blended[name] = (1 - alpha) * (prior[name] ?? 0) + alpha * (data[name] ?? 0);
  }
  const total = Object.values(blended).reduce((s, v) => s + v, 0);
  if (total > 0) {
    for (const name of SCORER_NAMES) blended[name] = Math.round((blended[name] / total) * 10000) / 10000;
  }
  return blended;
}

// ── Active learning: uncertainty estimation ─────────────────────────────────

export function predictUncertainty(
  ratedExamples: RatedExample[],
  candidateRaws: Record<string, number>[],
  nBootstrap = 50,
): number[] {
  if (ratedExamples.length < 5) {
    return candidateRaws.map((raw) => {
      const vec = buildFeatureRow(raw);
      const mean = vec.reduce((s, v) => s + v, 0) / vec.length;
      return Math.sqrt(vec.reduce((s, v) => s + (v - mean) ** 2, 0) / vec.length);
    });
  }

  const { X: Xtrain, y: ytrain } = buildFeatureMatrix(ratedExamples);
  const Xcand = candidateRaws.map(buildFeatureRow);
  const n = ytrain.length;

  // Simple seeded random for reproducibility
  let seed = 42;
  const rand = () => { seed = (seed * 1664525 + 1013904223) & 0x7fffffff; return seed / 0x7fffffff; };

  const predictions: number[][] = Array.from({ length: Xcand.length }, () => []);

  for (let b = 0; b < nBootstrap; b++) {
    const idx = Array.from({ length: n }, () => Math.floor(rand() * n));
    const Xb = idx.map((i) => Xtrain[i]);
    const yb = idx.map((i) => ytrain[i]);
    const { coefs, intercept } = ridgeFit(Xb, yb);
    const preds = ridgePredict(Xcand, coefs, intercept);
    for (let j = 0; j < Xcand.length; j++) predictions[j].push(preds[j]);
  }

  return predictions.map((preds) => {
    const mean = preds.reduce((s, v) => s + v, 0) / preds.length;
    return Math.sqrt(preds.reduce((s, v) => s + (v - mean) ** 2, 0) / preds.length);
  });
}

// ── Public API ──────────────────────────────────────────────────────────────

export function fitFromRatings(ratedExamples: RatedExample[]): FitResult {
  if (!ratedExamples.length) {
    return {
      weights: { ...DEFAULT_WEIGHTS },
      weight_delta: Object.fromEntries(SCORER_NAMES.map((n) => [n, 0])),
      top_features: [],
      interactions: {},
      rating_stats: { mean: 0, min: 0, max: 0, n: 0, dist: {} },
      confidence: 0,
      method: "prior",
    };
  }

  const { X, y } = buildFeatureMatrix(ratedExamples);
  const nSamples = y.length;

  let dataWeights: Record<string, number>;
  let interactions: Record<string, number> = {};
  let method: "pearson" | "ridge";

  if (nSamples < 5) {
    dataWeights = pearsonWeights(X, y);
    method = "pearson";
  } else {
    const { coefs } = ridgeFit(X, y);
    dataWeights = ridgeToWeights(coefs);
    interactions = ridgeToInteractions(coefs);
    method = "ridge";
  }

  const weights = blend(DEFAULT_WEIGHTS, dataWeights, nSamples);

  const topFeatures = Object.entries(weights)
    .map(([scorer, importance]) => ({ scorer, importance: Math.round(importance * 10000) / 10000 }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 6);

  const topInteractions = Object.fromEntries(
    Object.entries(interactions)
      .filter(([, v]) => Math.abs(v) > 0.1)
      .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a)),
  );

  const mean = y.reduce((s, v) => s + v, 0) / y.length;
  const dist: Record<string, number> = {};
  for (const r of y) {
    const k = String(Math.round(r));
    dist[k] = (dist[k] ?? 0) + 1;
  }

  return {
    weights,
    weight_delta: Object.fromEntries(
      SCORER_NAMES.map((n) => [n, Math.round((weights[n] - (DEFAULT_WEIGHTS[n] ?? 0)) * 10000) / 10000]),
    ),
    top_features: topFeatures,
    interactions: topInteractions,
    rating_stats: {
      mean: Math.round(mean * 10) / 10,
      min: Math.min(...y),
      max: Math.max(...y),
      n: y.length,
      dist,
    },
    confidence: Math.round(Math.min(1.0, y.length / RAMP_N) * 100) / 100,
    method,
  };
}
