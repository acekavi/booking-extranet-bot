import { describe, expect, it } from "vitest";
import {
  guestPaysFromListed,
  listedPriceFromDirect,
  netFromListed,
  nonRefundablePrice,
  round2,
  undercutsDirect,
  worstCaseMultiplier,
} from "./pricing.js";
import type { PricingConfig } from "../config.js";

// Deliberately round, obviously-fake numbers: fixtures must never double as a
// record of anyone's real commercial terms.
const pricing: PricingConfig = {
  currency: "USD",
  commissionPct: 20,
  discounts: { tier1: 10, tier2: 20, mobile: 10 },
  worstCaseStack: ["tier2", "mobile"],
  directDiscountVsGuestPricePct: 10,
  nonRefundableDiscountPct: 10,
  breakfastPerPersonPerNight: 0,
};

describe("worstCaseMultiplier", () => {
  it("compounds discounts multiplicatively, not additively", () => {
    // 20% then 10% leaves 0.72 of the price, not 0.70.
    expect(worstCaseMultiplier(pricing)).toBeCloseTo(0.72, 10);
  });

  it("is 1 when no discounts are stacked", () => {
    expect(worstCaseMultiplier({ ...pricing, worstCaseStack: [] })).toBe(1);
  });

  it("names the offending key when the stack refers to an unknown discount", () => {
    expect(() => worstCaseMultiplier({ ...pricing, worstCaseStack: ["genius9"] })).toThrow(
      /"genius9".*not defined in discounts/s
    );
  });
});

describe("listedPriceFromDirect", () => {
  it("inflates the direct price to survive the discount stack", () => {
    // 100 / 0.9 = 111.11 the guest pays; / 0.72 = 154.32 listed.
    expect(listedPriceFromDirect(100, pricing)).toBe(154.32);
  });

  it("leaves a worst-case guest paying more on the OTA than direct", () => {
    const direct = 100;
    const listed = listedPriceFromDirect(direct, pricing);
    expect(guestPaysFromListed(listed, pricing)).toBeGreaterThan(direct);
  });

  it("keeps that guarantee across a wide range of prices", () => {
    for (const direct of [12.5, 30, 47.99, 100, 250, 1000]) {
      const listed = listedPriceFromDirect(direct, pricing);
      expect(guestPaysFromListed(listed, pricing)).toBeGreaterThanOrEqual(direct);
    }
  });

  it("charges the guest exactly the configured premium over direct", () => {
    const listed = listedPriceFromDirect(90, pricing);
    // directDiscountVsGuestPricePct = 10, so direct is 10% below what the
    // guest pays on the OTA: 90 / 0.9 = 100.
    expect(guestPaysFromListed(listed, pricing)).toBeCloseTo(100, 1);
  });
});

describe("netFromListed", () => {
  it("applies the discount stack and then commission", () => {
    // 154.32 * 0.72 = 111.11 paid; * 0.8 = 88.89 kept.
    expect(netFromListed(154.32, pricing)).toBe(88.89);
  });

  it("shows the direct booking keeping more than the OTA at the same guest price", () => {
    const direct = 100;
    const listed = listedPriceFromDirect(direct, pricing);
    expect(netFromListed(listed, pricing)).toBeLessThan(direct);
  });
});

describe("nonRefundablePrice", () => {
  it("discounts the flexible rate", () => {
    expect(nonRefundablePrice(100, pricing)).toBe(90);
  });
});

describe("undercutsDirect", () => {
  const direct = 100;
  const listed = listedPriceFromDirect(direct, pricing); // guest pays ~111.11

  it("flags a plan that drops the guest below the direct price", () => {
    // -20% on top of the stack puts the guest at ~88.89, under direct.
    expect(undercutsDirect(listed, -20, direct, pricing)).toBe(true);
  });

  it("accepts a plan that stays above the direct price", () => {
    expect(undercutsDirect(listed, -5, direct, pricing)).toBe(false);
  });

  it("accepts a plan priced above the standard rate", () => {
    expect(undercutsDirect(listed, 25, direct, pricing)).toBe(false);
  });
});

describe("round2", () => {
  it("rounds to cents without float dust", () => {
    expect(round2(1.005)).toBe(1.01);
    expect(round2(0.1 + 0.2)).toBe(0.3);
  });
});
