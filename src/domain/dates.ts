/** Date helpers. All dates are ISO "YYYY-MM-DD" strings in the property's own timezone. */

/**
 * Today, in the machine's LOCAL timezone.
 *
 * Deliberately not toISOString(), which is UTC. A property east of UTC gets
 * yesterday's date for the first hours of every local day, and extranets
 * reject prices for past dates -- usually by leaving Save quietly disabled
 * rather than by saying so, which is a miserable thing to debug.
 */
export function today(): string {
  return new Date().toLocaleDateString("en-CA");
}

/** The nights a stay occupies: check-in inclusive, check-out exclusive. */
export function nightsOfStay(checkIn: string, checkOut: string): string[] {
  const nights: string[] = [];
  let current = Date.parse(`${checkIn}T00:00:00Z`);
  const end = Date.parse(`${checkOut}T00:00:00Z`);
  if (Number.isNaN(current) || Number.isNaN(end)) {
    throw new Error(`Invalid stay dates: "${checkIn}" -> "${checkOut}"`);
  }
  while (current < end) {
    nights.push(new Date(current).toISOString().slice(0, 10));
    current += 86_400_000;
  }
  return nights;
}

/** Every date in a "YYYY-MM" month. */
export function datesInMonth(yearMonth: string): string[] {
  const [year, month] = yearMonth.split("-").map(Number);
  if (!year || !month || month < 1 || month > 12) {
    throw new Error(`Invalid month "${yearMonth}", expected YYYY-MM`);
  }
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return Array.from(
    { length: days },
    (_, i) => `${year}-${String(month).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`
  );
}

/** Inclusive list of "YYYY-MM" months from one to another. */
export function monthsBetween(fromMonth: string, toMonth: string): string[] {
  const [fy, fm] = fromMonth.split("-").map(Number);
  const [ty, tm] = toMonth.split("-").map(Number);
  if (!fy || !fm || !ty || !tm) {
    throw new Error(`Invalid month range "${fromMonth}".."${toMonth}", expected YYYY-MM`);
  }
  if (ty * 12 + tm < fy * 12 + fm) {
    throw new Error(`Month range runs backwards: "${fromMonth}" is after "${toMonth}"`);
  }
  const months: string[] = [];
  for (let y = fy, m = fm; y * 12 + m <= ty * 12 + tm; m === 12 ? ((m = 1), y++) : m++) {
    months.push(`${y}-${String(m).padStart(2, "0")}`);
  }
  return months;
}
