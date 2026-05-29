/**
 * Web Worker entry point for Monte Carlo simulation.
 * Runs off the main thread to keep UI responsive.
 */
import { runMonteCarlo, type SimEngine, type TeamProfile, type GroupMatch } from './engine';

export interface WorkerRequest {
  groupMatches: GroupMatch[];
  teamGroups: Record<string, string>;
  profiles: Record<string, TeamProfile>;
  nSims: number;
  seed: number;
  engine: SimEngine;
}

export interface WorkerProgress {
  type: 'progress';
  done: number;
  total: number;
}

export interface WorkerDone {
  type: 'done';
  /** Serializable version of MonteCarloResult */
  result: SerializedMonteCarloResult;
  elapsedMs: number;
}

export interface SerializedMonteCarloResult {
  nSims: number;
  championCounts: Record<string, number>;
  finalistCounts: Record<string, number>;
  semifinalCounts: Record<string, number>;
  matchWinnerCounts: Record<number, Record<string, number>>;
  matchParticipantCounts: Record<number, Record<string, number>>;
  matchAvgGoals: Record<number, [number, number]>;
  representative: {
    matchWinners: Record<number, string>;
    matchLosers: Record<number, string>;
    matchScores: Record<number, [number, number]>;
    matchHome: Record<number, string>;
    matchAway: Record<number, string>;
    standings: Record<string, Array<{ team: string; pts: number; gd: number; gf: number }>>;
  };
}

function mapToObj<K extends string | number, V>(m: Map<K, V>): Record<string, V> {
  const obj: Record<string, V> = {};
  for (const [k, v] of m) obj[String(k)] = v;
  return obj;
}

function nestedMapToObj(m: Map<number, Map<string, number>>): Record<number, Record<string, number>> {
  const obj: Record<number, Record<string, number>> = {};
  for (const [k, v] of m) obj[k] = mapToObj(v);
  return obj;
}

self.onmessage = (e: MessageEvent<WorkerRequest>) => {
  const { groupMatches, teamGroups, profiles, nSims, seed, engine } = e.data;
  const t0 = performance.now();

  const result = runMonteCarlo(
    groupMatches,
    teamGroups,
    profiles,
    nSims,
    seed,
    engine,
    (done, total) => {
      (self as unknown as Worker).postMessage({ type: 'progress', done, total } satisfies WorkerProgress);
    },
  );

  const rep = result.representative;
  const serialized: SerializedMonteCarloResult = {
    nSims: result.nSims,
    championCounts: mapToObj(result.championCounts),
    finalistCounts: mapToObj(result.finalistCounts),
    semifinalCounts: mapToObj(result.semifinalCounts),
    matchWinnerCounts: nestedMapToObj(result.matchWinnerCounts),
    matchParticipantCounts: nestedMapToObj(result.matchParticipantCounts),
    matchAvgGoals: mapToObj(result.matchAvgGoals) as Record<number, [number, number]>,
    representative: {
      matchWinners: mapToObj(rep.matchWinners),
      matchLosers: mapToObj(rep.matchLosers),
      matchScores: mapToObj(rep.matchScores) as Record<number, [number, number]>,
      matchHome: mapToObj(rep.matchHome),
      matchAway: mapToObj(rep.matchAway),
      standings: (() => {
        const s: Record<string, Array<{ team: string; pts: number; gd: number; gf: number }>> = {};
        for (const [grp, rows] of rep.standings) s[grp] = rows;
        return s;
      })(),
    },
  };

  (self as unknown as Worker).postMessage({
    type: 'done',
    result: serialized,
    elapsedMs: performance.now() - t0,
  } satisfies WorkerDone);
};
