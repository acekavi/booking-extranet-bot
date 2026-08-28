/**
 * Driving the calendar's Bulk Edit panel.
 *
 * Almost everything below is a workaround for a specific, reproducible
 * misbehaviour of that panel. The comments explain WHY each one exists,
 * because every one of them looks like superstition until it is removed and
 * the run starts failing again. If you are adapting this to another extranet,
 * read the comments before deleting anything.
 */
import type { Page } from "playwright";
import type { RoomsConfig } from "../config.js";
import type { DateRange } from "../domain/ranges.js";
import { resolveRatePlan } from "../domain/seasons.js";
import { bulkEdit, roomPanel } from "./selectors.js";

/** A small randomised pause, so the tool does not hammer the panel. */
function pause(): number {
  return 400 + Math.floor(Math.random() * 600);
}

async function closeAnyOpenPanel(page: Page): Promise<void> {
  const closeButton = page.locator(bulkEdit.closeButton);
  if ((await closeButton.count()) > 0) {
    await closeButton.first().click();
    // Closing plays a transition, and parts of the panel keep intercepting
    // clicks while it runs. Waiting for the fader to detach is necessary but
    // NOT sufficient -- a real settle delay was needed too, most visibly right
    // after a save, when the success banner keeps the panel alive longer.
    await page.waitForTimeout(1000);
  }
  await page
    .locator(bulkEdit.modalFader)
    .waitFor({ state: "detached", timeout: 5000 })
    .catch(() => {});
}

async function openPanel(page: Page, roomId: string): Promise<void> {
  await closeAnyOpenPanel(page);
  const panel = page.locator(roomPanel(roomId));
  if ((await panel.count()) === 0) {
    throw new Error(
      `No room panel for roomId "${roomId}". Check the roomId in your rooms config ` +
        `against the extranet calendar.`
    );
  }
  await panel.getByRole("button", { name: bulkEdit.openButtonName }).first().click();
  await page.waitForTimeout(500);
}

async function setDateRange(page: Page, range: DateRange): Promise<void> {
  await page.locator(bulkEdit.dateFrom).fill(range.from);
  await page.locator(bulkEdit.dateUntil).fill(range.to);
  // The datepicker popup closes on neither Escape nor fill(). Left open, it
  // covers the accordion toggles and swallows the next click. Clicking any
  // stable static text elsewhere in the panel dismisses it.
  await page.getByText(bulkEdit.weekdayLabelText).click();
}

async function waitForSaveConfirmation(page: Page): Promise<void> {
  // The success banner is the only honest signal that the save round-trip
  // finished and the panel has settled. A fixed delay races it.
  await page.getByText(bulkEdit.saveSuccessText).waitFor({ state: "visible", timeout: 10_000 });
}

/**
 * Type a price and read it back.
 *
 * fill() sets the DOM value and fires one synthetic event, which this
 * React-controlled input ignores: its internal state stays empty, Save never
 * enables, and the run dies on an opaque timeout with a field that looks
 * correct on screen. Real keystrokes update it properly.
 *
 * The read-back is not paranoia. A price is being written to a live listing;
 * if a future change breaks the typing again, failing here is much better than
 * silently publishing whatever the field happens to contain.
 */
async function typePrice(page: Page, selector: string, price: string): Promise<void> {
  const input = page.locator(selector);
  await input.click();
  await input.press("Control+a");
  await input.press("Delete");
  await page.waitForTimeout(150);
  await input.pressSequentially(price, { delay: 60 });
  await page.waitForTimeout(300);
  const readBack = await input.inputValue();
  if (readBack !== price) {
    throw new Error(
      `Price field ${selector} reads back "${readBack}" after typing "${price}" — refusing to save`
    );
  }
}

/**
 * Wait for Save to enable, then click it.
 *
 * Save enables asynchronously once the panel has validated every price row,
 * and how long that takes varies -- occupancy-based pricing revalidates far
 * more slowly. Clicking blind after a fixed wait fails intermittently with a
 * bare "element is not enabled", which tells you nothing. So poll for the
 * state, and if it never arrives, report what the panel actually contained.
 */
async function clickSaveWhenEnabled(page: Page, what: string): Promise<void> {
  const save = page.getByRole("button", { name: bulkEdit.saveButtonName }).first();
  try {
    await save.waitFor({ state: "visible", timeout: 10_000 });
    // Poll the locator itself. Matching buttons by textContent in
    // page.waitForFunction never matches this one -- its label is wrapped in
    // spans, so only the accessible name matches -- and reports "never
    // enabled" for a button that is in fact enabled.
    const deadline = Date.now() + 20_000;
    for (;;) {
      if (await save.isEnabled()) break;
      if (Date.now() > deadline) throw new Error("timeout");
      await page.waitForTimeout(250);
    }
  } catch {
    throw new Error(`Save never enabled for ${what}.\n${await describePanel(page)}`);
  }
  await save.click();
}

/** A snapshot of the panel, for when something times out and you need to know why. */
async function describePanel(page: Page): Promise<string> {
  const rows = await page.locator(bulkEdit.anyPriceInput).count();
  const filled: string[] = [];
  for (let i = 0; i < rows; i++) {
    const value = await page.locator(bulkEdit.priceInput(i)).inputValue().catch(() => "?");
    const plan = await page.locator(bulkEdit.priceSelect(i)).inputValue().catch(() => "?");
    filled.push(`${i}[plan=${plan}]="${value}"`);
  }
  const from = await page.locator(bulkEdit.dateFrom).inputValue().catch(() => "?");
  const to = await page.locator(bulkEdit.dateUntil).inputValue().catch(() => "?");
  const weekdays = await page.locator('input[type="checkbox"]:checked').count().catch(() => -1);
  return (
    `   dates: from="${from}" to="${to}"  weekdays checked: ${weekdays}\n` +
    `   ${rows} price row(s): ${filled.join(", ") || "(none)"}`
  );
}

export async function applyAvailability(
  page: Page,
  roomId: string,
  range: DateRange
): Promise<void> {
  await openPanel(page, roomId);
  await setDateRange(page, range);
  await page.getByRole("button", { name: bulkEdit.roomsToSellToggle }).click();
  await page.waitForTimeout(300);
  await page.locator(bulkEdit.roomsToSellInput).fill(String(range.value));
  await clickSaveWhenEnabled(page, `availability ${range.from}..${range.to}`);
  await waitForSaveConfirmation(page);
  await page.waitForTimeout(pause());
}

/** Selectable rate plans in the Prices dropdown; the blank placeholder is skipped. */
async function ratePlanOptions(page: Page): Promise<{ value: string; label: string }[]> {
  const found: { value: string; label: string }[] = [];
  for (const option of await page.locator(`${bulkEdit.priceSelect(0)} option`).all()) {
    const value = await option.getAttribute("value");
    if (!value) continue;
    found.push({ value, label: ((await option.textContent()) ?? "").trim() });
  }
  return found;
}

export interface RateWriteResult {
  wroteBreakfastPlan: boolean;
}

/**
 * Write one date range's rates, retrying once.
 *
 * The panel is intermittent: the same code that drives a hundred saves in one
 * run can leave Save disabled on the first action of the next, with dates,
 * plan and price all verifiably correct. Reopening it clears the condition.
 * One retry means a transient hiccup does not abandon a run halfway and leave
 * a listing half-updated.
 */
export async function applyRates(
  page: Page,
  roomId: string,
  range: DateRange,
  breakfastRange: DateRange | undefined,
  ratePlans: RoomsConfig["ratePlans"]
): Promise<RateWriteResult> {
  try {
    return await attemptRates(page, roomId, range, breakfastRange, ratePlans);
  } catch (error) {
    const first = (error as Error).message.split("\n")[0];
    console.log(`   retrying ${range.from}..${range.to} after: ${first}`);
    await closeAnyOpenPanel(page);
    await page.waitForTimeout(2500);
    return await attemptRates(page, roomId, range, breakfastRange, ratePlans);
  }
}

async function attemptRates(
  page: Page,
  roomId: string,
  range: DateRange,
  breakfastRange: DateRange | undefined,
  ratePlans: RoomsConfig["ratePlans"]
): Promise<RateWriteResult> {
  await openPanel(page, roomId);
  await setDateRange(page, range);
  await page.getByRole("button", { name: bulkEdit.pricesToggle }).click();
  await page.waitForTimeout(300);

  // Every option must be filled in ONE session, not one per save: with
  // occupancy-based pricing the panel lists a variant per guest count and
  // leaves Save disabled until all of them have a price.
  const options = await ratePlanOptions(page);
  if (options.length === 0) {
    throw new Error(`No rate plans available for roomId ${roomId} — is the room still sellable?`);
  }

  let wroteBreakfastPlan = false;
  for (const [index, option] of options.entries()) {
    const { includesBreakfast } = resolveRatePlan(option.label, ratePlans);
    if (includesBreakfast) {
      if (breakfastRange === undefined) {
        throw new Error(
          `Rate plan "${option.label}" includes breakfast, but no breakfast-inclusive ` +
            `rate was computed for ${range.from}..${range.to}`
        );
      }
      wroteBreakfastPlan = true;
    }
    const price = (includesBreakfast ? breakfastRange!.value : range.value).toFixed(2);

    if (index > 0) {
      // "Add more" appends another rate-plan row. Both Prices and Restrictions
      // render an add-entry button, so take the first.
      await page.locator(bulkEdit.addEntry).first().click();
      await page.locator(bulkEdit.priceSelect(index)).waitFor({ state: "visible", timeout: 10_000 });
    }
    await page.locator(bulkEdit.priceSelect(index)).selectOption(option.value);
    // Choosing a plan re-renders its price row. Typing immediately lands on
    // the node being replaced: the DOM value looks right but React never sees
    // the input, so Save stays disabled. Let the re-render settle.
    await page.waitForTimeout(500);
    await typePrice(page, bulkEdit.priceInput(index), price);
  }

  await clickSaveWhenEnabled(page, `rates ${range.from}..${range.to}`);
  await waitForSaveConfirmation(page);
  await page.waitForTimeout(pause());
  return { wroteBreakfastPlan };
}

/** Read-only: the rate plan labels the panel offers for a room. */
export async function readRatePlanLabels(page: Page, roomId: string): Promise<string[]> {
  await openPanel(page, roomId);
  await page.getByRole("button", { name: bulkEdit.pricesToggle }).click();
  await page.waitForTimeout(600);
  return (await ratePlanOptions(page)).map((option) => option.label);
}
