/**
 * Turn prices and existing bookings into a per-(room, date) plan.
 *
 * Two things are decided per date:
 *
 *   rate         -- derived from your direct price for that room and season.
 *   availability -- your unit count minus rooms already sold elsewhere, so the
 *                   OTA cannot resell a room you have already given away.
 *
 * The availability half matters more than it looks: it is the difference
 * between a channel manager and an overbooking generator.
 */
import type { PricingConfig, RoomsConfig } from "../config.js";
import type { Booking, PriceTable } from "../sources/types.js";
import { datesInMonth, nightsOfStay } from "./dates.js";
import { listedPriceFromDirect } from "./pricing.js";
import { groupConsecutiveByValue, type DateRange } from "./ranges.js";
import { seasonForMonth } from "./seasons.js";

export interface PlanRow {
  room: string;
  roomId: string;
  date: string;
  units: number;
  /** Rooms already sold on other channels for this date. */
  soldElsewhere: number;
  availability: number;
  /** Listed rate for the room-only plan. */
  rate: number;
  /** Listed rate for a breakfast-inclusive plan. */
  rateWithBreakfast: number;
}

export interface BuildPlanOptions {
  months: string[];
  pricing: PricingConfig;
  rooms: RoomsConfig;
  prices: PriceTable;
  bookings?: Booking[];
  /** Inclusive bounds, to clamp a partial first or last month. */
  startDate?: string;
  endDate?: string;
}

/** room -> date -> units already sold. */
function occupancyByRoom(bookings: Booking[]): Map<string, Map<string, number>> {
  const occupancy = new Map<string, Map<string, number>>();
  for (const booking of bookings) {
    let byDate = occupancy.get(booking.room);
    if (!byDate) occupancy.set(booking.room, (byDate = new Map()));
    for (const night of nightsOfStay(booking.checkIn, booking.checkOut)) {
      byDate.set(night, (byDate.get(night) ?? 0) + booking.quantity);
    }
  }
  return occupancy;
}

export function buildPlan(options: BuildPlanOptions): PlanRow[] {
  const { months, pricing, rooms, prices, bookings = [], startDate, endDate } = options;
  const occupancy = occupancyByRoom(bookings);

  // A booking for a room we do not price is almost always a config mistake
  // (a renamed room type), and silently ignoring it overstates availability.
  const known = new Set(Object.keys(rooms.rooms));
  const unknown = [...new Set(bookings.map((b) => b.room))].filter((r) => !known.has(r));
  if (unknown.length > 0) {
    throw new Error(
      `Bookings reference room(s) not in your rooms config: ${unknown.join(", ")}. ` +
        `Add them, or map them to the names you use.`
    );
  }

  const plan: PlanRow[] = [];
  for (const [room, config] of Object.entries(rooms.rooms)) {
    const breakfast = pricing.breakfastPerPersonPerNight * config.capacity;
    for (const month of months) {
      const season = seasonForMonth(month, rooms);
      const directPrice = prices[room]?.[season];
      if (directPrice === undefined) {
        throw new Error(
          `No price for room "${room}" in season "${season}". ` +
            `Every room needs a price for every season you are pricing.`
        );
      }
      const rate = listedPriceFromDirect(directPrice, pricing);
      const rateWithBreakfast = listedPriceFromDirect(directPrice + breakfast, pricing);

      for (const date of datesInMonth(month)) {
        if (startDate && date < startDate) continue;
        if (endDate && date > endDate) continue;
        const soldElsewhere = occupancy.get(room)?.get(date) ?? 0;
        plan.push({
          room,
          roomId: config.roomId,
          date,
          units: config.units,
          soldElsewhere,
          availability: Math.max(0, config.units - soldElsewhere),
          rate,
          rateWithBreakfast,
        });
      }
    }
  }
  return plan.sort((a, b) => a.room.localeCompare(b.room) || a.date.localeCompare(b.date));
}

export interface RoomPlan {
  room: string;
  roomId: string;
  availability: DateRange[];
  rates: DateRange[];
  ratesWithBreakfast: DateRange[];
}

/**
 * Collapse a plan into per-room date ranges ready for bulk editing.
 *
 * Rates and breakfast rates are grouped independently but from the same source
 * rows, so their boundaries coincide and the two lists stay index-aligned.
 */
export function groupPlanByRoom(plan: PlanRow[]): RoomPlan[] {
  const byRoomId = new Map<string, PlanRow[]>();
  for (const row of plan) {
    let rows = byRoomId.get(row.roomId);
    if (!rows) byRoomId.set(row.roomId, (rows = []));
    rows.push(row);
  }

  return [...byRoomId].map(([roomId, rows]) => {
    const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
    return {
      room: sorted[0]!.room,
      roomId,
      availability: groupConsecutiveByValue(
        sorted.map((r) => ({ date: r.date, value: r.availability }))
      ),
      rates: groupConsecutiveByValue(sorted.map((r) => ({ date: r.date, value: r.rate }))),
      ratesWithBreakfast: groupConsecutiveByValue(
        sorted.map((r) => ({ date: r.date, value: r.rateWithBreakfast }))
      ),
    };
  });
}
