import { describe, expect, it } from "vitest";
import {
  PricingConfigSchema,
  RoomsConfigSchema,
  SourceConfigSchema,
  assertSeasonsCoverTheYear,
  assertUniqueRoomIds,
} from "./config.js";
import type { RoomsConfig } from "./config.js";

const validRooms = {
  seasons: { High: [12, 1, 2], Low: [3, 4, 5, 6, 7, 8, 9, 10, 11] },
  ratePlans: [{ matches: "standard", includesBreakfast: false }],
  rooms: { "Example Room": { roomId: "ROOM_A", units: 2, capacity: 2 } },
};

describe("PricingConfigSchema", () => {
  it("accepts a minimal config and fills defaults", () => {
    const parsed = PricingConfigSchema.parse({
      commissionPct: 15,
      directDiscountVsGuestPricePct: 5,
    });
    expect(parsed.currency).toBe("USD");
    expect(parsed.worstCaseStack).toEqual([]);
    expect(parsed.breakfastPerPersonPerNight).toBe(0);
  });

  it("rejects a percentage outside 0-100", () => {
    expect(() =>
      PricingConfigSchema.parse({ commissionPct: 120, directDiscountVsGuestPricePct: 5 })
    ).toThrow();
  });

  it("rejects unknown keys, so a typo is not silently ignored", () => {
    expect(() =>
      PricingConfigSchema.parse({
        commissionPct: 15,
        directDiscountVsGuestPricePct: 5,
        comissionPct: 15,
      })
    ).toThrow();
  });
});

describe("RoomsConfigSchema", () => {
  it("accepts a valid config", () => {
    expect(() => RoomsConfigSchema.parse(validRooms)).not.toThrow();
  });

  it("rejects a month outside 1-12", () => {
    expect(() =>
      RoomsConfigSchema.parse({ ...validRooms, seasons: { High: [13] } })
    ).toThrow();
  });

  it("rejects a room with zero units", () => {
    expect(() =>
      RoomsConfigSchema.parse({
        ...validRooms,
        rooms: { "Example Room": { roomId: "A", units: 0, capacity: 2 } },
      })
    ).toThrow();
  });

  it("requires at least one rate plan rule", () => {
    expect(() => RoomsConfigSchema.parse({ ...validRooms, ratePlans: [] })).toThrow();
  });
});

describe("assertSeasonsCoverTheYear", () => {
  it("accepts a full, non-overlapping year", () => {
    expect(() => assertSeasonsCoverTheYear(validRooms as RoomsConfig)).not.toThrow();
  });

  it("rejects a month claimed by two seasons", () => {
    const overlapping = {
      ...validRooms,
      seasons: { High: [1, 2], Low: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
    } as RoomsConfig;
    expect(() => assertSeasonsCoverTheYear(overlapping)).toThrow(/Month 2 is in both/);
  });

  it("rejects a year with a gap", () => {
    const gapped = { ...validRooms, seasons: { High: [1, 2] } } as RoomsConfig;
    expect(() => assertSeasonsCoverTheYear(gapped)).toThrow(/No season covers month/);
  });
});

describe("SourceConfigSchema", () => {
  it("accepts a json source", () => {
    expect(SourceConfigSchema.parse({ type: "json", pricesPath: "config/prices.json" })).toMatchObject(
      { type: "json" }
    );
  });

  it("accepts a postgres source and defaults the env var name", () => {
    const parsed = SourceConfigSchema.parse({ type: "postgres", pricesQuery: "select 1" });
    expect(parsed).toMatchObject({ type: "postgres", connectionStringEnv: "DATABASE_URL" });
  });

  it("rejects an unknown source type", () => {
    expect(() => SourceConfigSchema.parse({ type: "csv", path: "x" })).toThrow();
  });
});

describe("assertUniqueRoomIds", () => {
  it("accepts rooms with distinct ids", () => {
    expect(() => assertUniqueRoomIds(validRooms as RoomsConfig)).not.toThrow();
  });

  it("rejects two rooms sharing a roomId, naming both", () => {
    const clashing = {
      ...validRooms,
      rooms: {
        "Room One": { roomId: "SAME", units: 1, capacity: 2 },
        "Room Two": { roomId: "SAME", units: 1, capacity: 2 },
      },
    } as RoomsConfig;
    expect(() => assertUniqueRoomIds(clashing)).toThrow(/"SAME".*Room One, Room Two/s);
  });
});
