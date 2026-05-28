/**
 * React hook for running Monte Carlo simulation in a Web Worker.
 */
import { useState, useCallback, useRef } from 'react';
import type { WorkerRequest, WorkerProgress, WorkerDone, SerializedMonteCarloResult } from './worker';
import type { SimEngine, TeamProfile, GroupMatch } from './engine';

export interface SimulationState {
  running: boolean;
  progress: number; // 0..1
  result: SerializedMonteCarloResult | null;
  elapsedMs: number | null;
  error: string | null;
}

export function useSimulation() {
  const [state, setState] = useState<SimulationState>({
    running: false,
    progress: 0,
    result: null,
    elapsedMs: null,
    error: null,
  });

  const workerRef = useRef<Worker | null>(null);

  const cancel = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.terminate();
      workerRef.current = null;
    }
    setState(s => ({ ...s, running: false }));
  }, []);

  const run = useCallback((
    groupMatches: GroupMatch[],
    teamGroups: Record<string, string>,
    profiles: Record<string, TeamProfile>,
    nSims: number,
    seed: number,
    engine: SimEngine,
  ) => {
    // Terminate any existing worker
    if (workerRef.current) workerRef.current.terminate();

    setState({ running: true, progress: 0, result: null, elapsedMs: null, error: null });

    const worker = new Worker(
      new URL('./worker.ts', import.meta.url),
      { type: 'module' },
    );
    workerRef.current = worker;

    worker.onmessage = (e: MessageEvent<WorkerProgress | WorkerDone>) => {
      const msg = e.data;
      if (msg.type === 'progress') {
        setState(s => ({ ...s, progress: msg.done / msg.total }));
      } else if (msg.type === 'done') {
        setState({
          running: false,
          progress: 1,
          result: msg.result,
          elapsedMs: msg.elapsedMs,
          error: null,
        });
        worker.terminate();
        workerRef.current = null;
      }
    };

    worker.onerror = (err) => {
      setState(s => ({ ...s, running: false, error: err.message }));
      worker.terminate();
      workerRef.current = null;
    };

    const request: WorkerRequest = { groupMatches, teamGroups, profiles, nSims, seed, engine };
    worker.postMessage(request);
  }, []);

  return { ...state, run, cancel };
}
