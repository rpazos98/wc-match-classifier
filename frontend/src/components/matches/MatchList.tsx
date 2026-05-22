import { useMemo } from 'react';
import type { Match } from '../../types/index';
import { useAppState } from '../../state/AppContext';
import { LBL_IMP, LBL_VALE, LBL_RES } from '../../utils/labels';

import FilterBar from './FilterBar';
import StatusBar from './StatusBar';
import MatchSectionHeader from './MatchSectionHeader';
import MatchCard from './MatchCard';
import MatchRow from './MatchRow';

const LABEL_ORDER = [LBL_IMP, LBL_VALE, LBL_RES] as const;

export default function MatchList() {
  const { matches, filterMode, simulated } = useAppState();

  // Apply filter
  const filtered = useMemo(() => {
    if (filterMode === 'confirmed') {
      return matches.filter((m) => m.stage === 'group' || !simulated);
    }
    if (filterMode === 'simulated') {
      return matches.filter((m) => m.stage !== 'group' && simulated);
    }
    return matches;
  }, [matches, filterMode, simulated]);

  // Group by label, sort by score descending within each group
  const groups = useMemo(() => {
    const map = new Map<string, Match[]>(
      LABEL_ORDER.map((l) => [l, []]),
    );
    for (const m of filtered) {
      const bucket = map.get(m.label);
      if (bucket) bucket.push(m);
    }
    const result: { label: string; items: Match[] }[] = [];
    for (const label of LABEL_ORDER) {
      const items = map.get(label)!;
      if (items.length > 0) {
        items.sort((a, b) => b.score - a.score);
        result.push({ label, items });
      }
    }
    return result;
  }, [filtered]);

  return (
    <>
      <StatusBar />
      <FilterBar />
      <div id="match-list">
        {groups.map(({ label, items }) => (
          <div key={label}>
            <MatchSectionHeader
              label={label}
              count={items.length}
              emoji={items[0].emoji}
            />
            {items.map((m) =>
              label === LBL_IMP ? (
                <MatchCard key={m.match_id} match={m} />
              ) : (
                <MatchRow key={m.match_id} match={m} />
              ),
            )}
          </div>
        ))}
      </div>
    </>
  );
}
