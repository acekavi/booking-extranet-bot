import type { RoomsConfig } from "../config.js";

/** Which season a "YYYY-MM" month falls in. */
export function seasonForMonth(yearMonth: string, rooms: RoomsConfig): string {
  const month = Number(yearMonth.slice(5, 7));
  for (const [season, months] of Object.entries(rooms.seasons)) {
    if (months.includes(month)) return season;
  }
  // loadConfig() rejects gaps up front, so reaching here means the config was
  // built in memory rather than loaded.
  throw new Error(`No season covers month ${yearMonth}`);
}

/**
 * Which configured rate plan an extranet dropdown label refers to.
 *
 * Throws rather than guessing, in both directions: an unmatched label means
 * the operator has not told us whether it includes breakfast, and an
 * ambiguous one means their rules overlap. Either way the safe move is to stop
 * before writing a price to a live listing.
 */
export function resolveRatePlan(
  label: string,
  ratePlans: RoomsConfig["ratePlans"]
): { includesBreakfast: boolean } {
  const normalised = label.toLowerCase();
  const matched = ratePlans.filter((plan) => normalised.includes(plan.matches.toLowerCase()));
  if (matched.length === 0) {
    throw new Error(
      `Rate plan "${label}" matches no rule in your rooms config. Add a ratePlans ` +
        `entry saying whether it includes breakfast before pushing prices.`
    );
  }
  if (matched.length > 1) {
    const rules = matched.map((m) => `"${m.matches}"`).join(", ");
    throw new Error(
      `Rate plan "${label}" matches ${matched.length} rules (${rules}) — ` +
        `make the rules unambiguous.`
    );
  }
  return { includesBreakfast: matched[0]!.includesBreakfast };
}
