/**
 * Where prices and existing bookings come from.
 *
 * Deliberately tiny. Anything that can produce a price table is a valid
 * source: a JSON file, your website's database, a spreadsheet export, an API.
 * Keeping this interface narrow is what lets the SQL for a particular schema
 * live in a user's private config rather than in this repo.
 */

/** room name -> season name -> your direct price. */
export type PriceTable = Record<string, Record<string, number>>;

/** A stay already sold somewhere other than the OTA being pushed to. */
export interface Booking {
  reference: string;
  room: string;
  /** ISO YYYY-MM-DD, check-in inclusive. */
  checkIn: string;
  /** ISO YYYY-MM-DD, check-out exclusive. */
  checkOut: string;
  /** Units of that room type held by this booking. */
  quantity: number;
}

export interface PriceSource {
  /** Human-readable, for logs. Must not contain credentials. */
  readonly describe: string;
  prices(): Promise<PriceTable>;
  /** Stays to subtract from availability. Empty if the source has none. */
  bookings(): Promise<Booking[]>;
}
