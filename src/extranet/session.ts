/**
 * Getting a logged-in browser, without ever handling a credential.
 *
 * You log in yourself, in a real browser window, including whatever 2FA your
 * account uses. Only the resulting session state is saved. The tool therefore
 * has no password to store, no TOTP secret to protect and no login form to
 * keep working -- which is both safer for you and one less thing that breaks
 * when the login page is redesigned.
 */
import { chromium, type Browser, type Page } from "playwright";
import { mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { CALENDAR_URL, LOGIN_URL, bulkEdit } from "./selectors.js";

export const STORAGE_STATE_PATH = ".auth/storage-state.json";

/** Open a browser, wait for a human to log in, save the session. */
export async function login(storageStatePath = STORAGE_STATE_PATH): Promise<void> {
  await mkdir(path.dirname(storageStatePath), { recursive: true });
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(LOGIN_URL);

  console.log(
    "\nA browser window is open. Log in there, including any 2FA step.\n" +
      "When you can see your property dashboard, press Enter here."
  );
  await new Promise<void>((resolve) => {
    process.stdin.resume();
    process.stdin.once("data", () => {
      process.stdin.pause();
      resolve();
    });
  });

  await context.storageState({ path: storageStatePath });
  await browser.close();
  console.log(`Session saved to ${storageStatePath} (gitignored). Re-run this when it expires.`);
}

export interface OpenCalendarResult {
  browser: Browser;
  page: Page;
}

/** Open the calendar with a saved session, ready for bulk edits. */
export async function openCalendar(options: {
  storageStatePath?: string;
  headless?: boolean;
}): Promise<OpenCalendarResult> {
  const storageStatePath = options.storageStatePath ?? STORAGE_STATE_PATH;
  try {
    await stat(storageStatePath);
  } catch {
    throw new Error(`No saved session at ${storageStatePath}. Run: npm run login`);
  }

  const browser = await chromium.launch({ headless: options.headless ?? false });
  const context = await browser.newContext({ storageState: storageStatePath });
  const page = await context.newPage();

  // Not "networkidle": the extranet holds long-lived analytics connections
  // open, so it can time out long after the calendar is perfectly usable.
  await page.goto(CALENDAR_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  try {
    await page.locator(bulkEdit.anyRoomPanel).first().waitFor({ state: "visible", timeout: 60_000 });
  } catch {
    await browser.close();
    throw new Error(
      "The calendar never showed any rooms. The saved session has most likely expired — " +
        "run `npm run login` again."
    );
  }
  await page.waitForTimeout(2000);
  return { browser, page };
}
