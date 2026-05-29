import { useState, useCallback, useRef, useEffect } from 'react';
import type { LearnMatch, FitRatingsResponse, RatedMatch } from '../../types';
import { getLearnMatches, fitRatings, resetRatings, getLearnState } from '../../api/learn';
import { mutate } from 'swr';
import WCYearSelector from './WCYearSelector';
import LearnMatchCard from './LearnMatchCard';
import RatingButtons from './RatingButtons';
import LearnSummary from './LearnSummary';

// ── State machine ───────────────────────────────────────────────────────────

type Phase =
  | 'loading'
  | 'wc-selector'
  | 'match-rating'
  | 'batch-done'
  | 'training'
  | 'summary'
  | 'already-trained'
  | 'all-rated'
  | 'error';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function LearnModal({ isOpen, onClose }: Props) {
  // ── Internal state ──────────────────────────────────────────────────────
  const [phase, setPhase] = useState<Phase>('loading');
  const [matches, setMatches] = useState<LearnMatch[]>([]);
  const [idx, setIdx] = useState(0);
  const [ratings, setRatings] = useState<RatedMatch[]>([]);
  const seenIds = useRef<Set<string>>(new Set());
  const wcYears = useRef<number[] | null>(null);
  const [fitResult, setFitResult] = useState<FitRatingsResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [footerVisible, setFooterVisible] = useState(true);
  const [footerNote, setFooterNote] = useState('');

  // Already-trained state
  const [trainedInfo, setTrainedInfo] = useState<{
    nExamples: number;
    meanRating: number | null;
    confidence: number | null;
    topFeatures: string[];
  } | null>(null);

  // ── Progress tracking ─────────────────────────────────────────────────
  const batchLen = matches.length || 1;
  const pct = phase === 'summary' || phase === 'batch-done' ? 100 : Math.round((idx / batchLen) * 100);
  const progLabel =
    phase === 'summary' || phase === 'batch-done'
      ? `${batchLen} / ${batchLen}`
      : ratings.length > 0
        ? `${idx + 1}/${batchLen} \u00b7 ${ratings.length} rated`
        : `${idx + 1} / ${batchLen}`;

  // ── Boot: decide initial phase ────────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;
    // Reset state on open
    setMatches([]);
    setIdx(0);
    setRatings([]);
    seenIds.current = new Set();
    setFitResult(null);
    setFooterVisible(true);
    setFooterNote('');
    setErrorMsg('');

    (async () => {
      setPhase('loading');
      try {
        const state = await getLearnState();
        if (state.has_learned && state.n_examples > 0) {
          const meta = state.fit_meta;
          setTrainedInfo({
            nExamples: state.n_examples,
            meanRating: meta?.mean_rating ?? null,
            confidence: meta?.confidence ?? null,
            topFeatures: meta?.top_features ?? [],
          });
          setPhase('already-trained');
          return;
        }
      } catch {
        // non-critical
      }

      // Check localStorage for WC years
      const stored = localStorage.getItem('wc2026_remembered_wcs');
      if (stored) {
        wcYears.current = JSON.parse(stored);
        await loadBatch(15);
      } else {
        setPhase('wc-selector');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // ── Load a batch of matches ───────────────────────────────────────────
  const loadBatch = useCallback(
    async (n: number) => {
      setPhase('loading');
      setFooterVisible(true);
      try {
        const excludeParam = [...seenIds.current].join(',');
        const seed = Math.floor(Math.random() * 99999);
        const yearsParam = wcYears.current ? wcYears.current.join(',') : undefined;

        const data = await getLearnMatches({
          n,
          seed,
          exclude: excludeParam || undefined,
          years: yearsParam,
        });

        if (!data.matches || data.matches.length === 0) {
          setPhase('all-rated');
          return;
        }

        setMatches(data.matches);
        setIdx(0);
        setPhase('match-rating');
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : 'Unknown error');
        setPhase('error');
      }
    },
    [],
  );

  // ── WC year confirmation ──────────────────────────────────────────────
  const handleWcConfirm = useCallback(
    (years: number[]) => {
      wcYears.current = years;
      loadBatch(15);
    },
    [loadBatch],
  );

  // ── Rate a match ──────────────────────────────────────────────────────
  const handleRate = useCallback(
    (rating: number) => {
      const match = matches[idx];
      if (!match) return;

      setRatings((prev) => [...prev, { raw: match.raw, rating }]);
      seenIds.current.add(match.match_id);

      const nextIdx = idx + 1;
      if (nextIdx >= matches.length) {
        setFooterVisible(false);
        setPhase('batch-done');
      } else {
        setIdx(nextIdx);
      }
    },
    [matches, idx],
  );

  // ── Skip ──────────────────────────────────────────────────────────────
  const handleSkip = useCallback(() => {
    const nextIdx = idx + 1;
    if (nextIdx >= matches.length) {
      setFooterVisible(false);
      setPhase('batch-done');
    } else {
      setIdx(nextIdx);
    }
  }, [idx, matches.length]);

  // ── Submit ratings ────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    setPhase('training');
    try {
      const result = await fitRatings(ratings);
      setFitResult(result);

      // Invalidate SWR cache so App re-fetches with new weights
      mutate('/api/matches');

      setPhase('summary');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Error training');
      setPhase('error');
    }
  }, [ratings]);

  // ── Continue with more matches ────────────────────────────────────────
  const handleContinue = useCallback(() => {
    loadBatch(10);
  }, [loadBatch]);

  // ── Reset ─────────────────────────────────────────────────────────────
  const handleReset = useCallback(async () => {
    if (!window.confirm('Delete all ratings and revert to default weights?')) return;
    try {
      await resetRatings();
      localStorage.removeItem('wc2026_remembered_wcs');
      wcYears.current = null;
      mutate('/api/matches');
      onClose();
    } catch {
      // best effort
    }
  }, [onClose]);

  // ── Apply and close ───────────────────────────────────────────────────
  const handleApply = useCallback(() => {
    mutate('/api/matches');
    onClose();
  }, [onClose]);

  // ── Continue from already-trained state ───────────────────────────────
  const handleContinueFromTrained = useCallback(() => {
    loadBatch(15);
  }, [loadBatch]);

  // ── Render ────────────────────────────────────────────────────────────
  if (!isOpen) return null;

  // Update footer note for match-rating
  const currentFooterNote =
    phase === 'match-rating' && matches.length > 0
      ? `Match ${idx + 1} of ${matches.length} — rate it as you'd watch it live.`
      : footerNote;

  return (
    <div id="learn-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div id="learn-box">
        {/* Header */}
        <div className="learn-hdr">
          <h2>Learn my preferences</h2>
          <div className="learn-progress-wrap">
            <span id="learn-prog-txt">{progLabel}</span>
            <div className="learn-progress-bar">
              <div
                className="learn-progress-fill"
                id="learn-prog-fill"
                style={{ width: `${pct}%` }}
              />
            </div>
            <button
              className="btn"
              style={{ padding: '4px 10px', fontSize: 11 }}
              onClick={onClose}
            >
              &#x2715;
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="learn-body" id="learn-body">
          {phase === 'loading' && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-sm)' }}>
              Loading historical matches...
            </div>
          )}

          {phase === 'wc-selector' && (
            <WCYearSelector onConfirm={handleWcConfirm} />
          )}

          {phase === 'match-rating' && matches[idx] && (
            <>
              <div className="learn-question">
                How would you rate this match?
              </div>
              <LearnMatchCard match={matches[idx]} />
              <RatingButtons onRate={handleRate} key={matches[idx].match_id} />
            </>
          )}

          {phase === 'batch-done' && (
            <div style={{ textAlign: 'center', padding: '20px 0 10px' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>&#x1F9E0;</div>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: '#fff', marginBottom: 6 }}>
                {ratings.length} matches rated
              </h3>
              <p style={{ color: 'var(--text-sm)', fontSize: 12, marginBottom: 20 }}>
                The model will learn the factors that matter most to you.
              </p>
              <button
                className="btn btn-primary"
                style={{ fontSize: 13, padding: '9px 32px' }}
                onClick={handleSubmit}
              >
                Train model
              </button>
            </div>
          )}

          {phase === 'training' && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-sm)' }}>
              Training...
            </div>
          )}

          {phase === 'summary' && fitResult && (
            <LearnSummary
              result={fitResult}
              onContinue={handleContinue}
              onReset={handleReset}
              onApply={handleApply}
            />
          )}

          {phase === 'already-trained' && trainedInfo && (
            <div
              style={{
                background: '#1a2a1a',
                border: '1px solid rgba(94,214,74,0.2)',
                borderRadius: 6,
                padding: 14,
                marginBottom: 12,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 14,
                  letterSpacing: '1px',
                  color: 'var(--green)',
                  marginBottom: 6,
                }}
              >
                YOU ALREADY HAVE A TRAINED MODEL
              </div>
              <div style={{ color: 'var(--text-sm)' }}>
                {trainedInfo.nExamples} matches accumulated
                {trainedInfo.meanRating != null &&
                  ` \u00b7 Average ${trainedInfo.meanRating}/10`}
                {trainedInfo.confidence != null && (
                  <>
                    {' \u00b7 Confidence '}
                    <b>{Math.round(trainedInfo.confidence * 100)}%</b>
                  </>
                )}
              </div>
              {trainedInfo.topFeatures.length > 0 && (
                <div style={{ color: 'var(--muted)', marginTop: 4 }}>
                  Top: {trainedInfo.topFeatures.join(', ')}
                </div>
              )}
              <div
                style={{
                  display: 'flex',
                  gap: 8,
                  marginTop: 12,
                  flexWrap: 'wrap',
                }}
              >
                <button
                  className="btn"
                  style={{
                    fontSize: 11,
                    padding: '5px 12px',
                    color: '#f56565',
                    borderColor: '#f5656544',
                  }}
                  onClick={handleReset}
                >
                  Reset
                </button>
                <button
                  className="btn btn-primary"
                  style={{ fontSize: 11, padding: '5px 14px' }}
                  onClick={handleContinueFromTrained}
                >
                  Add more matches
                </button>
              </div>
            </div>
          )}

          {phase === 'all-rated' && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-sm)' }}>
              You've rated all available matches.
            </div>
          )}

          {phase === 'error' && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--red)' }}>
              Error: {errorMsg}
            </div>
          )}
        </div>

        {/* Footer */}
        {footerVisible && phase === 'match-rating' && (
          <div className="learn-footer">
            <span id="learn-footer-note">{currentFooterNote}</span>
            <button
              className="btn"
              style={{ fontSize: 11, padding: '4px 10px', color: 'var(--text-sm)' }}
              onClick={handleSkip}
            >
              Skip →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
