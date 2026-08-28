/**
 * The pricing model.
 *
 * The direct price you charge on your own website is the MASTER. Booking.com
 * rates are derived from it, not the other way round.
 *
 * Why that direction matters. On Booking.com a guest can stack loyalty and
 * device discounts, and the platform takes commission on top. If you set the
 * Booking.com price first and then discount it for direct guests, you are
 * discounting a number nobody actually pays -- and once a guest has enough
 * loyalty status, "direct" ends up MORE expensive than the OTA. That is a real
 * mistake and an easy one: it looks correct in a spreadsheet, and it silently
 * inverts your channel strategy.
 *
 * So the arithmetic runs the other way:
 *
 *   guest pays on the OTA = direct price / (1 - directDiscountPct/100)
 *   listed price          = guest pays / worstCaseDiscountMultiplier
 *
 * The listed price is deliberately inflated: it is a buffer that absorbs the
 * discount stack, and nobody in the worst case pays it. Commission does not
 * appear in it -- commission decides what you NET, not what the guest is shown.
 */
import type { PricingConfig } from "../config.js";

/** Round to cents, avoiding the usual float dust (0.1 + 0.2 problem). */
export function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

/**
 * Combined multiplier for the worst-case discount stack, e.g. a top-tier
 * loyalty discount AND a mobile discount applying to the same booking.
 *
 * Discounts compound multiplicatively rather than adding: 20% then 10% leaves
 * 0.8 * 0.9 = 0.72, not 0.70. Adding them would under-price every room.
 */
export function worstCaseMultiplier(pricing: PricingConfig): number {
  return pricing.worstCaseStack.reduce((multiplier, key) => {
    const pct = pricing.discounts[key];
    if (pct === undefined) {
      throw new Error(
        `worstCaseStack refers to "${key}", which is not defined in discounts. ` +
          `Known discounts: ${Object.keys(pricing.discounts).join(", ") || "(none)"}`
      );
    }
    return multiplier * (1 - pct / 100);
  }, 1);
}

/**
 * The listed OTA price that sits far enough above `directPrice` that even a
 * fully-discounted guest still pays more there than booking with you directly.
 */
export function listedPriceFromDirect(directPrice: number, pricing: PricingConfig): number {
  const guestPaysOnOta = directPrice / (1 - pricing.directDiscountVsGuestPricePct / 100);
  return round2(guestPaysOnOta / worstCaseMultiplier(pricing));
}

/** What a worst-case-discounted guest actually pays at `listedPrice`. */
export function guestPaysFromListed(listedPrice: number, pricing: PricingConfig): number {
  return round2(listedPrice * worstCaseMultiplier(pricing));
}

/** What you keep from an OTA stay at `listedPrice`, after discounts and commission. */
export function netFromListed(listedPrice: number, pricing: PricingConfig): number {
  const guestPays = listedPrice * worstCaseMultiplier(pricing);
  return round2(guestPays * (1 - pricing.commissionPct / 100));
}

/** A non-refundable variant, priced below the flexible rate. */
export function nonRefundablePrice(flexiblePrice: number, pricing: PricingConfig): number {
  return round2(flexiblePrice * (1 - pricing.nonRefundableDiscountPct / 100));
}

/**
 * Does a rate plan undercut the direct price for a worst-case guest?
 *
 * Any extra plan (a weekly rate, a last-minute deal) applies ON TOP of the
 * discount stack, so it can quietly drop below your direct price and undo the
 * whole model. Nothing in an extranet will warn you; this does.
 */
export function undercutsDirect(
  listedPrice: number,
  planModifierPct: number,
  directPrice: number,
  pricing: PricingConfig
): boolean {
  const planListed = listedPrice * (1 + planModifierPct / 100);
  return guestPaysFromListed(planListed, pricing) < directPrice;
}
