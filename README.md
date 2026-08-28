# booking-extranet-bot

Set your Booking.com rates and availability from your own direct prices, instead of the other way round.

Point it at the prices you charge on your own website. It works out what the listed OTA rate has to be so that a guest with every discount stacked still pays more there than booking with you directly, subtracts rooms you have already sold elsewhere, and writes both to the extranet calendar.

```
npm run login                      # log in once, in a real browser
npm run plan -- --to 2027-06       # see what it would write
npm run push -- --to 2027-06       # write it
```

---

## Why direction matters

On an OTA you pay commission, and guests stack loyalty and device discounts on top. The listed price is set high enough to absorb all of that, so **the listed price is a number almost nobody pays.**

The tempting model is to set the OTA price first and then give direct guests a discount off it. That model is broken, and it fails quietly:

> List a room at 150. A guest with 20% loyalty and 10% mobile pays `150 × 0.8 × 0.9 = 108`.
> Offer "15% off list" for direct booking and you charge `127.50` — **your direct price is 20 dearer than the OTA.**

If most of your guests are discount-eligible, you have made direct booking worse for nearly everyone while believing you did the opposite. Nothing in an extranet will tell you.

So this tool runs the arithmetic the other way. **Your direct price is the master:**

```
guest pays on the OTA  =  direct price ÷ (1 − directDiscount)
listed OTA price       =  guest pays ÷ worst-case discount multiplier
```

Change a direct price, re-run, and the OTA rate follows. The guest genuinely saves by booking with you; you keep the commission.

Commission never appears in that calculation — it decides what you *net*, not what the guest is shown.

---

## Install

Requires Node 20+.

```bash
git clone https://github.com/acekavi/booking-extranet-bot.git
cd booking-extranet-bot
npm install
npx playwright install chromium
```

## Configure

Copy the three examples and fill them in. **Your real config is gitignored** — see [Keeping your data out of git](#keeping-your-data-out-of-git).

```bash
cp config/pricing.example.json config/pricing.json
cp config/rooms.example.json   config/rooms.json
cp config/source.example.json  config/source.json
cp config/prices.example.json  config/prices.json
```

### `config/pricing.json` — your commercial model

```jsonc
{
  "commissionPct": 15,                    // what the OTA takes
  "discounts": {                          // name them whatever you like
    "loyalty3": 20,
    "mobile": 10
  },
  "worstCaseStack": ["loyalty3", "mobile"],  // assume these apply at once
  "directDiscountVsGuestPricePct": 5,        // the guest's saving for booking direct
  "nonRefundableDiscountPct": 5,
  "breakfastPerPersonPerNight": 0             // 0 if you have no breakfast plan
}
```

`worstCaseStack` is the important one. Set it to the discounts your *typical* guest actually gets, not the mildest case. If most bookings come from top-tier members on mobile, that is your worst case, and pricing for anything softer loses money on the majority of stays.

### `config/rooms.json` — your inventory

```jsonc
{
  "seasons": {
    "High":     [12, 1, 2, 3],
    "Shoulder": [4, 11],
    "Low":      [5, 6, 7, 8, 9, 10]
  },
  "ratePlans": [
    { "matches": "standard",  "includesBreakfast": false },
    { "matches": "breakfast", "includesBreakfast": true }
  ],
  "rooms": {
    "Deluxe Double": { "roomId": "1234567890", "units": 4, "capacity": 2 }
  }
}
```

Every month must belong to exactly one season; the loader rejects gaps and overlaps rather than picking for you.

`ratePlans` maps the labels in the extranet's price dropdown to whether that plan includes breakfast. **A label matching no rule aborts the run.** That is deliberate: guess "room only" on a breakfast plan and you give breakfast away on every booking from then on.

Find `roomId` in the calendar page — it is the number in each room row's `data-test-id`.

### `config/source.json` — where prices come from

The simplest source is a file:

```json
{ "type": "json", "pricesPath": "config/prices.json", "bookingsPath": "output/bookings.csv" }
```

`config/prices.json` is `{ "Room name": { "Season name": price } }`, in your own currency, per room per night, **for a direct booking**.

`bookingsPath` is optional. It is a CSV of stays you have already sold elsewhere — your own website, phone, walk-ins — so the OTA is not offered a room you have given away:

```csv
reference,room,checkIn,checkOut,quantity
W-1042,Deluxe Double,2027-02-11,2027-02-14,2
```

Or read both straight out of your website's database:

```json
{
  "type": "postgres",
  "connectionStringEnv": "DATABASE_URL",
  "pricesQuery": "select name as room, label as season, price from ... ",
  "bookingsQuery": "select id as reference, ... where status = 'confirmed'"
}
```

**The queries live in your config, not in this repo** — no two property websites share a schema, and publishing this tool should not publish yours. The queries just have to return the right column names; see `config/source.postgres.example.json`. Put the connection string in `.env` (gitignored).

## Log in

```bash
npm run login
```

A browser opens. Log in yourself, including 2FA. Only the resulting session is saved, to `.auth/` (gitignored).

**The tool never asks for your password and has nowhere to store one.** No credential handling, no TOTP secret in a dotfile, and nothing to leak if the repo is public. Re-run it when the session expires.

## Plan, then push

```bash
npm run plan -- --to 2027-06
```

```
Deluxe Double  (roomId 1234567890)
  availability — 3 range(s)
    2026-09-01 → 2027-02-10   4 to sell
    2027-02-11 → 2027-02-13   2 to sell
    2027-02-14 → 2027-06-30   4 to sell
  rates — 3 range(s)
    2026-09-01 → 2026-10-31   list 58.48   guest pays ~42.11   you keep ~35.79
```

Nothing is written. When it looks right:

```bash
npm run push -- --to 2027-06
```

| Flag | |
|---|---|
| `--from YYYY-MM` | first month to price (default: this month) |
| `--to YYYY-MM` | last month to price (**required**) |
| `--start-date`, `--end-date` | clamp a partial first or last month |
| `--room NAME` | restrict to one room |
| `--rates-only`, `--availability-only` | write one half |
| `--resume FILE` | skip writes recorded in a previous journal |
| `--headless` | no visible browser window |

### If a run is interrupted

Every write is appended to `output/journal-<timestamp>.csv` **as it happens**, not at the end. So if a push dies at range 100 of 128, you still have a record of the 100 that landed:

```bash
npm run push -- --to 2027-06 --resume output/journal-1234567890.csv
```

It skips what is already recorded and carries on.

## When it breaks

Extranets get redesigned without notice. When that happens it is almost always `src/extranet/selectors.ts` that needs editing, and only that file.

```bash
npm run verify-selectors
```

opens the calendar and reports which selectors still match, and whether every rate plan label resolves against your `ratePlans` rules.

---

## How it avoids looking like a problem

Short version: **it does not try to hide.** It logs in as you, in a real browser, and does the same edits you would do by hand — slower, and fewer of them. The goal is to not be a nuisance to the platform, not to be undetectable by it.

That distinction matters, because the two goals pull in opposite directions. Tools that try to look human usually end up hammering the server behind a disguise, which is both worse behaviour and easier to spot.

### What it does

**One request where a naive tool makes ninety.** Rates and availability are collapsed into date ranges and written with the calendar's own Bulk Edit panel. A whole season at one price is a single save. This is by far the biggest factor — it is the difference between a few dozen writes for a year of pricing and several thousand.

**It waits for confirmation instead of retrying blindly.** Every save waits for the extranet's own success banner before moving on. Nothing is fired at a fixed interval and nothing is repeated in a loop hoping it lands.

**One retry, then it stops.** A failed range is attempted once more and then the run fails loudly. There is no backoff loop that quietly turns one broken selector into a thousand requests.

**Randomised pauses between actions.** 400–1000 ms after each save, plus the settle delays the panel needs anyway.

**Prices are typed, not injected.** Each character is entered as a real keystroke at 60 ms intervals. This exists because the panel's React inputs ignore programmatic value-setting — but the side effect is that the tool types at roughly human speed rather than filling a form instantly.

**Everything is sequential.** One browser, one tab, one room at a time. No concurrency, no parallel sessions, no second window.

**It runs visibly by default.** `--headless` is opt-in. Watching the browser do the work is the normal mode.

**You log in; it doesn't.** There is no automated login, no stored password, no TOTP handling and no CAPTCHA solving. The tool inherits a session you created by hand and uses it until it expires.

**`plan` touches nothing.** The default posture is to compute and print. Only `push` writes.

### What it deliberately does not do

No user-agent spoofing, no stealth or anti-detection plugin, no proxy rotation, no `navigator.webdriver` patching, no canvas or fingerprint tampering, no CAPTCHA solving. Stock Playwright Chromium, as installed.

**So yes — the extranet can tell this is automation if it looks.** Playwright sets `navigator.webdriver`, and that is not patched out. Anything in this list would be added only to defeat a control the platform put there on purpose, which is a different activity from managing your own listing, and it is not what this tool is for.

### The thing that actually matters

Volume and rhythm, not fingerprint. A few hundred writes once a month, in the daytime, from a property manager's own session, looks like a property manager. The same tool on an hourly cron looks like a scraper regardless of how convincingly it types.

So, in practice:

- **Run it when you would naturally be working.** Not at 4am, not every hour.
- **Push when prices change, not on a schedule.** This is a tool for a pricing decision, not a heartbeat.
- **Keep runs small.** `--room`, `--from`/`--to` and `--rates-only` all narrow the work. A rerun after a partial failure should use `--resume`, which skips what already landed rather than rewriting it.
- **Use `plan` first, every time.** It costs nothing and catches the mistake that would otherwise become 200 wrong writes.
- **If you ever get challenged or rate-limited, slow down or do less.** Do not reach for a way around it — that is the point at which ordinary automation of your own account turns into something else.

### And check your agreement

Your contract with the platform governs what you may automate against your own listing, and it is the authority here, not this README. Read it. If it prohibits automated access, this tool is not a loophole.

---

## Keeping your data out of git

This repo is public and contains no property's data. That is enforced, not promised:

- `config/*.json` is gitignored; only `config/*.example.json` is committed
- `.env`, `.auth/`, `output/` and `input/` are gitignored
- `src/domain/` — most of the codebase — is pure arithmetic that imports no I/O at all, so it *cannot* hold a credential or a room id
- test fixtures use round, obviously-fake numbers

and a check you can run, which scans the files git actually **tracks** for connection strings, private keys, API tokens, email addresses and bare 8+ digit runs that look like room ids:

```bash
npm run check-clean
```

It exits non-zero on a finding, so it works as a pre-commit hook:

```bash
echo 'npm run check-clean' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

**A warning worth taking seriously.** Your rates, occupancy and margins are commercially sensitive even though they are not secrets. Prices are visible on the OTA anyway, but your commission rate, your direct margin and your booking volumes are not — and together they are a competitor's map of your business. Keep your `config/` private, and think twice before committing analytics or revenue notes to any repo you might later make public.

## What this tool does not do

- **It will not tell you if a rate plan undercuts your direct price.** An extra plan — a weekly rate, a last-minute deal — applies *on top of* the discount stack and can quietly drop below direct. `undercutsDirect()` in `src/domain/pricing.ts` will check a plan for you, but nothing calls it automatically, because only you know which plans exist and which ones you meant to be cheaper.
- **It does not create or edit rate plans**, only prices them.
- **It does not read reservations from the OTA.** Availability is your unit count minus what your `bookings` source reports; if bookings arrive through the OTA itself, the extranet already accounts for those.

## Development

```bash
npm test           # unit tests
npm run build      # typecheck
npm run check-clean
```

```
src/
  domain/     pure logic — no Playwright, no database, no filesystem
  sources/    where prices and bookings come from
  extranet/   the browser automation
  config.ts   every property-specific value enters here
  cli.ts
```

The rule that keeps this honest: **`src/domain/` imports nothing with I/O.** Anything property-specific enters through `config.ts` or `sources/`, so a review only has to look in two places.

`src/extranet/bulk-edit.ts` is full of workarounds with long comments explaining why each exists — typing prices keystroke by keystroke because the React input ignores `fill()`, polling the Save button rather than clicking blind, settling delays after the modal transition. Every one of them looks like superstition until you remove it and the run starts failing again. Read the comments before deleting anything.

## Adapting to another OTA

The domain layer is not Booking.com-specific — it is arithmetic over prices, seasons and dates. Porting means writing a new `src/extranet/` against a different panel and leaving everything else alone.

## Legal

For managing property listings you control, from your own account. See [How it avoids looking like a problem](#how-it-avoids-looking-like-a-problem) for how it behaves and what your agreement with the platform has to say about it.

## License

MIT — see [LICENSE](LICENSE).
