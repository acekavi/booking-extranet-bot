#!/usr/bin/env node
/**
 * Command line entry point.
 *
 *   login             log in once; saves a browser session
 *   plan              print what WOULD be written (never touches the extranet)
 *   push              write it, for real
 *   verify-selectors  check this tool's selectors still match the extranet
 *
 * `plan` is the default posture everywhere: `push` is the only command that
 * changes anything, and it still prints the plan first.
 */
import { loadConfig } from "./config.js";
import { monthsBetween, today } from "./domain/dates.js";
import { buildPlan, groupPlanByRoom, type RoomPlan } from "./domain/plan.js";
import { guestPaysFromListed, netFromListed } from "./domain/pricing.js";
import { createPriceSource } from "./sources/index.js";
import { applyAvailability, applyRates, readRatePlanLabels } from "./extranet/bulk-edit.js";
import { Journal } from "./extranet/journal.js";
import { login, openCalendar } from "./extranet/session.js";
import { bulkEdit } from "./extranet/selectors.js";

interface Args {
  command: string;
  from?: string;
  to?: string;
  startDate?: string;
  endDate?: string;
  room?: string;
  resume?: string;
  ratesOnly: boolean;
  availabilityOnly: boolean;
  headless: boolean;
}

function parseArgs(argv: string[]): Args {
  const value = (flag: string): string | undefined => {
    const index = argv.indexOf(flag);
    if (index < 0) return undefined;
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) throw new Error(`${flag} needs a value`);
    return next;
  };
  return {
    command: argv[0] ?? "",
    from: value("--from"),
    to: value("--to"),
    startDate: value("--start-date"),
    endDate: value("--end-date"),
    room: value("--room"),
    resume: value("--resume"),
    ratesOnly: argv.includes("--rates-only"),
    availabilityOnly: argv.includes("--availability-only"),
    headless: argv.includes("--headless"),
  };
}

const USAGE = `
booking-extranet-bot — derive OTA rates from your own direct prices

  npm run login
  npm run plan -- --to 2027-06
  npm run push -- --to 2027-06
  npm run verify-selectors

Options
  --from YYYY-MM       first month to price (default: this month)
  --to YYYY-MM         last month to price (required)
  --start-date DATE    clamp the first month (default: today)
  --end-date DATE      clamp the last month
  --room NAME|ID       restrict to one room
  --rates-only         do not write availability
  --availability-only  do not write rates
  --resume FILE        skip writes already recorded in a previous journal
  --headless           run without a visible browser window
`.trimStart();

async function buildRoomPlans(args: Args) {
  if (!args.to) throw new Error("--to YYYY-MM is required (the last month to price)");
  const config = await loadConfig();
  const source = createPriceSource(config.source);
  console.log(`Price source: ${source.describe}`);

  const [prices, bookings] = await Promise.all([source.prices(), source.bookings()]);
  if (bookings.length > 0) {
    console.log(`${bookings.length} booking(s) held elsewhere will be subtracted from availability.`);
  }

  const from = args.from ?? today().slice(0, 7);
  const months = monthsBetween(from, args.to);
  // Rates cannot be set for dates already past; most extranets simply refuse,
  // usually by leaving Save disabled rather than by explaining.
  const startDate = args.startDate ?? today();

  const plan = buildPlan({
    months,
    pricing: config.pricing,
    rooms: config.rooms,
    prices,
    bookings,
    startDate,
    endDate: args.endDate,
  });

  let roomPlans = groupPlanByRoom(plan);
  if (args.room) {
    roomPlans = roomPlans.filter((r) => r.room === args.room || r.roomId === args.room);
    if (roomPlans.length === 0) throw new Error(`--room "${args.room}" matched nothing in the plan`);
  }
  return { config, roomPlans, months, startDate, rowCount: plan.length };
}

function printPlan(roomPlans: RoomPlan[], config: Awaited<ReturnType<typeof loadConfig>>): void {
  for (const roomPlan of roomPlans) {
    console.log(`\n${roomPlan.room}  (roomId ${roomPlan.roomId})`);
    console.log(`  availability — ${roomPlan.availability.length} range(s)`);
    for (const range of roomPlan.availability) {
      console.log(`    ${range.from} → ${range.to}   ${range.value} to sell`);
    }
    console.log(`  rates — ${roomPlan.rates.length} range(s)`);
    for (const range of roomPlan.rates) {
      const guest = guestPaysFromListed(range.value, config.pricing);
      const net = netFromListed(range.value, config.pricing);
      console.log(
        `    ${range.from} → ${range.to}   list ${range.value.toFixed(2)}` +
          `   guest pays ~${guest.toFixed(2)}   you keep ~${net.toFixed(2)}`
      );
    }
  }
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.command === "login") return login();

  if (args.command === "verify-selectors") {
    const { browser, page } = await openCalendar({ headless: args.headless });
    try {
      const config = await loadConfig();
      const panels = page
        .locator(bulkEdit.anyRoomPanel)
        .filter({ has: page.getByRole("button", { name: bulkEdit.openButtonName }) });
      const count = await panels.count();
      console.log(`${count > 0 ? "PASS" : "FAIL"}  room panels found (${count})`);
      for (const [room, cfg] of Object.entries(config.rooms.rooms)) {
        const labels = await readRatePlanLabels(page, cfg.roomId);
        console.log(`\n${room} — ${labels.length} priceable plan(s)`);
        for (const label of labels) {
          try {
            const { includesBreakfast } = (await import("./domain/seasons.js")).resolveRatePlan(
              label,
              config.rooms.ratePlans
            );
            console.log(`   ok    "${label}" → ${includesBreakfast ? "breakfast" : "room-only"} price`);
          } catch (error) {
            console.log(`   FAIL  "${label}" → ${(error as Error).message.split(".")[0]}`);
          }
        }
      }
    } finally {
      await browser.close();
    }
    return;
  }

  if (args.command !== "plan" && args.command !== "push") {
    console.log(USAGE);
    process.exitCode = args.command ? 1 : 0;
    return;
  }

  const { config, roomPlans, months, startDate, rowCount } = await buildRoomPlans(args);
  console.log(
    `\n${months[0]} .. ${months[months.length - 1]}  (${months.length} month(s)), ` +
      `from ${startDate} — ${roomPlans.length} room(s), ${rowCount} room-nights.`
  );
  printPlan(roomPlans, config);

  if (args.command === "plan") {
    console.log("\nThis was a plan. Nothing was written. Run `npm run push` with the same flags to apply.");
    return;
  }

  const journal = new Journal(`output/journal-${Date.now()}.csv`);
  if (args.resume) {
    const skipping = await journal.resumeFrom(args.resume);
    console.log(`\nResuming: ${skipping} write(s) from ${args.resume} will be skipped.`);
  }

  const { browser, page } = await openCalendar({ headless: args.headless });
  let written = 0;
  let skipped = 0;
  try {
    for (const roomPlan of roomPlans) {
      if (!args.ratesOnly) {
        for (const range of roomPlan.availability) {
          const entry = {
            roomId: roomPlan.roomId,
            room: roomPlan.room,
            kind: "availability" as const,
            from: range.from,
            to: range.to,
            value: range.value,
          };
          if (journal.isDone(entry)) {
            skipped++;
            continue;
          }
          await applyAvailability(page, roomPlan.roomId, range);
          await journal.record(entry);
          written++;
        }
      }

      if (args.availabilityOnly) continue;

      for (const [index, range] of roomPlan.rates.entries()) {
        const breakfastRange = roomPlan.ratesWithBreakfast[index];
        const entry = {
          roomId: roomPlan.roomId,
          room: roomPlan.room,
          kind: "rate" as const,
          from: range.from,
          to: range.to,
          value: range.value,
        };
        if (journal.isDone(entry)) {
          skipped++;
          continue;
        }
        const { wroteBreakfastPlan } = await applyRates(
          page,
          roomPlan.roomId,
          range,
          breakfastRange,
          config.rooms.ratePlans
        );
        await journal.record(entry);
        written++;
        // Only record the breakfast rate if a breakfast plan was really in the
        // panel. Plans an OTA derives from yours never appear there, and
        // logging one would claim a write that never happened.
        if (breakfastRange && wroteBreakfastPlan) {
          await journal.record({
            roomId: roomPlan.roomId,
            room: roomPlan.room,
            kind: "rate-breakfast",
            from: breakfastRange.from,
            to: breakfastRange.to,
            value: breakfastRange.value,
          });
          written++;
        }
      }
    }
  } finally {
    await browser.close();
    console.log(
      `\n${written} write(s) applied${skipped ? `, ${skipped} skipped as already done` : ""}.` +
        (written > 0 ? `\nJournal: ${journal.path}` : "")
    );
    if (written > 0) {
      console.log(`If this run was interrupted, resume with:  --resume ${journal.path}`);
    }
  }
}

main().catch((error: Error) => {
  console.error(`\n${error.message}`);
  process.exitCode = 1;
});
