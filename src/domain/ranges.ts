/**
 * Collapse per-date values into date ranges.
 *
 * An extranet bulk edit is one slow, flaky browser interaction, so a year of
 * per-date writes is both unbearable and much more likely to fail partway. A
 * season's worth of identical prices is one range and one write.
 */
export interface DateRange {
  from: string;
  to: string;
  value: number;
}

/** Entries must already be sorted by date. */
export function groupConsecutiveByValue(
  entries: Array<{ date: string; value: number }>
): DateRange[] {
  if (entries.length === 0) return [];

  const ranges: DateRange[] = [];
  let start = entries[0]!;
  let previous = entries[0]!;

  for (const current of entries.slice(1)) {
    if (current.value !== previous.value) {
      ranges.push({ from: start.date, to: previous.date, value: previous.value });
      start = current;
    }
    previous = current;
  }
  ranges.push({ from: start.date, to: previous.date, value: previous.value });
  return ranges;
}
