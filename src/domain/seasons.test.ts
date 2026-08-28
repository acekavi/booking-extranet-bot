import { describe, expect, it } from "vitest";
import { resolveRatePlan, seasonForMonth } from "./seasons.js";
import type { RoomsConfig } from "../config.js";

const rooms: RoomsConfig = {
  seasons: { High: [12, 1, 2], Low: [3, 4, 5, 6, 7, 8, 9, 10, 11] },
  ratePlans: [
    { matches: "standard", includesBreakfast: false },
    { matches: "breakfast", includesBreakfast: true },
  ],
  rooms: { "Example Room": { roomId: "ROOM_A", units: 1, capacity: 2 } },
};

describe("seasonForMonth", () => {
  it("finds the season a month belongs to", () => {
    expect(seasonForMonth("2027-01", rooms)).toBe("High");
    expect(seasonForMonth("2027-06", rooms)).toBe("Low");
  });

  it("handles December without treating 12 as 2", () => {
    expect(seasonForMonth("2027-12", rooms)).toBe("High");
  });

  it("throws for a month no season covers", () => {
    const gapped: RoomsConfig = { ...rooms, seasons: { High: [1] } };
    expect(() => seasonForMonth("2027-07", gapped)).toThrow(/No season covers/);
  });
});

describe("resolveRatePlan", () => {
  it("matches case-insensitively on a substring", () => {
    expect(resolveRatePlan("Standard Rates", rooms.ratePlans)).toEqual({
      includesBreakfast: false,
    });
    expect(resolveRatePlan("Room + BREAKFAST", rooms.ratePlans)).toEqual({
      includesBreakfast: true,
    });
  });

  it("refuses to guess at an unknown plan", () => {
    expect(() => resolveRatePlan("Weekly Deal", rooms.ratePlans)).toThrow(/matches no rule/);
  });

  it("refuses when the rules are ambiguous", () => {
    const ambiguous = [
      { matches: "rate", includesBreakfast: false },
      { matches: "standard", includesBreakfast: true },
    ];
    expect(() => resolveRatePlan("Standard Rate", ambiguous)).toThrow(/matches 2 rules/);
  });
});
