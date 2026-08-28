import { describe, expect, it } from "vitest";
import { buildPlan, groupPlanByRoom } from "./plan.js";
import type { PricingConfig, RoomsConfig } from "../config.js";
import type { Booking, PriceTable } from "../sources/types.js";

const pricing: PricingConfig = {
  currency: "USD",
  commissionPct: 20,
  discounts: { tier2: 20, mobile: 10 },
  worstCaseStack: ["tier2", "mobile"],
  directDiscountVsGuestPricePct: 10,
  nonRefundableDiscountPct: 10,
  breakfastPerPersonPerNight: 10,
};

const rooms: RoomsConfig = {
  seasons: { High: [1], Low: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
  ratePlans: [{ matches: "standard", includesBreakfast: false }],
  rooms: { "Example Room": { roomId: "ROOM_A", units: 3, capacity: 2 } },
};

const prices: PriceTable = { "Example Room": { High: 100, Low: 50 } };

const base = { pricing, rooms, prices };

describe("buildPlan", () => {
  it("produces one row per room per date", () => {
    const plan = buildPlan({ ...base, months: ["2027-01"] });
    expect(plan).toHaveLength(31);
    expect(plan[0]!.date).toBe("2027-01-01");
  });

  it("prices each month by its season", () => {
    const plan = buildPlan({ ...base, months: ["2027-01", "2027-02"] });
    const january = plan.find((r) => r.date === "2027-01-15")!;
    const february = plan.find((r) => r.date === "2027-02-15")!;
    expect(january.rate).toBeGreaterThan(february.rate);
  });

  it("adds breakfast for the whole room, not per booking", () => {
    const row = buildPlan({ ...base, months: ["2027-01"] })[0]!;
    // capacity 2 x 10 = 20 on top of the 100 direct price.
    expect(row.rateWithBreakfast).toBeGreaterThan(row.rate);
  });

  it("sets availability to the full unit count when nothing is sold", () => {
    expect(buildPlan({ ...base, months: ["2027-01"] })[0]!.availability).toBe(3);
  });

  it("subtracts bookings held elsewhere, counting quantity", () => {
    const bookings: Booking[] = [
      { reference: "A", room: "Example Room", checkIn: "2027-01-10", checkOut: "2027-01-12", quantity: 2 },
    ];
    const plan = buildPlan({ ...base, months: ["2027-01"], bookings });
    expect(plan.find((r) => r.date === "2027-01-10")!.availability).toBe(1);
    expect(plan.find((r) => r.date === "2027-01-11")!.availability).toBe(1);
    // Check-out day is not a night held.
    expect(plan.find((r) => r.date === "2027-01-12")!.availability).toBe(3);
  });

  it("never reports negative availability when oversold", () => {
    const bookings: Booking[] = [
      { reference: "A", room: "Example Room", checkIn: "2027-01-10", checkOut: "2027-01-11", quantity: 9 },
    ];
    const plan = buildPlan({ ...base, months: ["2027-01"], bookings });
    expect(plan.find((r) => r.date === "2027-01-10")!.availability).toBe(0);
  });

  it("clamps to the given start and end dates", () => {
    const plan = buildPlan({
      ...base,
      months: ["2027-01"],
      startDate: "2027-01-10",
      endDate: "2027-01-12",
    });
    expect(plan.map((r) => r.date)).toEqual(["2027-01-10", "2027-01-11", "2027-01-12"]);
  });

  it("refuses a booking for a room it does not price", () => {
    const bookings: Booking[] = [
      { reference: "A", room: "Ghost Room", checkIn: "2027-01-10", checkOut: "2027-01-11", quantity: 1 },
    ];
    expect(() => buildPlan({ ...base, months: ["2027-01"], bookings })).toThrow(/Ghost Room/);
  });

  it("refuses a season with no price rather than inventing one", () => {
    const partial: PriceTable = { "Example Room": { High: 100 } };
    expect(() => buildPlan({ ...base, prices: partial, months: ["2027-02"] })).toThrow(
      /No price for room "Example Room" in season "Low"/
    );
  });
});

describe("groupPlanByRoom", () => {
  it("collapses a season into a single rate range", () => {
    const plan = buildPlan({ ...base, months: ["2027-01"] });
    const [roomPlan] = groupPlanByRoom(plan);
    expect(roomPlan!.rates).toHaveLength(1);
    expect(roomPlan!.rates[0]).toMatchObject({ from: "2027-01-01", to: "2027-01-31" });
  });

  it("splits rates at a season boundary", () => {
    const plan = buildPlan({ ...base, months: ["2027-01", "2027-02"] });
    expect(groupPlanByRoom(plan)[0]!.rates).toHaveLength(2);
  });

  it("keeps rate and breakfast ranges index-aligned", () => {
    const plan = buildPlan({ ...base, months: ["2027-01", "2027-02"] });
    const roomPlan = groupPlanByRoom(plan)[0]!;
    expect(roomPlan.ratesWithBreakfast).toHaveLength(roomPlan.rates.length);
    roomPlan.rates.forEach((range, index) => {
      expect(roomPlan.ratesWithBreakfast[index]!.from).toBe(range.from);
      expect(roomPlan.ratesWithBreakfast[index]!.to).toBe(range.to);
    });
  });

  it("splits availability where a booking lands", () => {
    const bookings: Booking[] = [
      { reference: "A", room: "Example Room", checkIn: "2027-01-10", checkOut: "2027-01-12", quantity: 1 },
    ];
    const plan = buildPlan({ ...base, months: ["2027-01"], bookings });
    expect(groupPlanByRoom(plan)[0]!.availability).toHaveLength(3);
  });
});
