/**
 * Configuration schemas and loaders.
 *
 * Everything specific to a property -- room ids, unit counts, prices,
 * commission, season months -- enters the program HERE and nowhere else.
 * `src/domain/` is pure arithmetic over whatever these produce, which is what
 * makes this repo safe to publish: the committed code contains no property's
 * data, and `config/*.json` is gitignored.
 */
import { readFile } from "node:fs/promises";
import { z } from "zod";

const Pct = z.number().min(0).max(100);

export const PricingConfigSchema = z
  .object({
    currency: z.string().min(1).default("USD"),
    /** Effective commission you pay the OTA, as a percentage. */
    commissionPct: Pct,
    /**
     * Every discount a guest might receive, by your own name for it. The names
     * are arbitrary -- "tier3", "mobile", "member" -- and only need to match
     * what `worstCaseStack` refers to.
     */
    discounts: z.record(z.string(), Pct).default({}),
    /**
     * The discounts you assume apply SIMULTANEOUSLY in the worst case. If most
     * of your bookings come from top-tier loyalty members on mobile, that is
     * your worst case, and pricing for anything softer loses money on the
     * majority of stays.
     */
    worstCaseStack: z.array(z.string()).default([]),
    /**
     * How far below the OTA guest price your direct price sits, as a
     * percentage. This is the guest's actual saving for booking with you.
     *
     * Measured against what the guest PAYS on the OTA, never against the
     * inflated listed price -- see the note in src/domain/pricing.ts.
     */
    directDiscountVsGuestPricePct: Pct,
    /** Discount for a non-refundable variant of each rate. */
    nonRefundableDiscountPct: Pct.default(0),
    /** Per person, per night. Set 0 if you do not sell a breakfast-inclusive plan. */
    breakfastPerPersonPerNight: z.number().min(0).default(0),
  })
  .strict();
export type PricingConfig = z.infer<typeof PricingConfigSchema>;

export const RoomsConfigSchema = z
  .object({
    /**
     * Season name -> month numbers (1-12). Every month you intend to price
     * must appear exactly once; the loader checks this, because a month in two
     * seasons silently resolves to whichever was declared first.
     */
    seasons: z.record(z.string(), z.array(z.number().int().min(1).max(12)).min(1)),
    /**
     * How to recognise each rate plan from its label in the extranet dropdown,
     * and whether that plan includes breakfast.
     *
     * A plan matching no rule is a hard error. Writing a guessed price to a
     * live listing is worse than refusing to run: guess "room only" on a
     * breakfast plan and you give breakfast away on every booking.
     */
    ratePlans: z
      .array(
        z.object({
          matches: z.string().min(1),
          includesBreakfast: z.boolean().default(false),
        })
      )
      .min(1),
    rooms: z
      .record(
        z.string(),
        z.object({
          /** The room's id in the extranet URL / DOM. */
          roomId: z.string().min(1),
          /** How many of this room you have. */
          units: z.number().int().positive(),
          /** Guests it sleeps; used to price breakfast per room. */
          capacity: z.number().int().positive(),
        })
      )
      .refine((rooms) => Object.keys(rooms).length > 0, "at least one room is required"),
  })
  .strict();
export type RoomsConfig = z.infer<typeof RoomsConfigSchema>;

const JsonSourceSchema = z.object({
  type: z.literal("json"),
  /** Path to a file of `{ "Room": { "Season": price } }`. */
  pricesPath: z.string().min(1),
  /** Optional CSV of bookings you hold outside the OTA. */
  bookingsPath: z.string().optional(),
});

const PostgresSourceSchema = z.object({
  type: z.literal("postgres"),
  /** Name of the env var holding the connection string. Never the string itself. */
  connectionStringEnv: z.string().min(1).default("DATABASE_URL"),
  /**
   * Your own SQL, returning columns: room, season, price.
   *
   * The query lives in config rather than in code so that publishing this tool
   * does not publish your schema.
   */
  pricesQuery: z.string().min(1),
  /** Optional. Returns: reference, room, checkIn, checkOut, quantity. */
  bookingsQuery: z.string().optional(),
});

export const SourceConfigSchema = z.discriminatedUnion("type", [
  JsonSourceSchema,
  PostgresSourceSchema,
]);
export type SourceConfig = z.infer<typeof SourceConfigSchema>;

export interface Config {
  pricing: PricingConfig;
  rooms: RoomsConfig;
  source: SourceConfig;
}

/** Parse, with the file path in the message -- zod's default is hard to place. */
function parseFile<S extends z.ZodTypeAny>(schema: S, raw: unknown, path: string): z.infer<S> {
  const result = schema.safeParse(raw);
  if (result.success) return result.data;
  const issues = result.error.issues
    .map((issue) => `  ${issue.path.join(".") || "(root)"}: ${issue.message}`)
    .join("\n");
  throw new Error(`${path} is not valid:\n${issues}`);
}

async function readJson(path: string): Promise<unknown> {
  let text: string;
  try {
    text = await readFile(path, "utf-8");
  } catch {
    throw new Error(
      `${path} not found. Copy the matching config/*.example.json and fill it in ` +
        `(your real config is gitignored).`
    );
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${path} is not valid JSON: ${(error as Error).message}`);
  }
}

/** Reject a month claimed by two seasons, or by none. */
export function assertSeasonsCoverTheYear(rooms: RoomsConfig): void {
  const owner = new Map<number, string>();
  for (const [season, months] of Object.entries(rooms.seasons)) {
    for (const month of months) {
      const existing = owner.get(month);
      if (existing) {
        throw new Error(
          `Month ${month} is in both "${existing}" and "${season}". ` +
            `Each month must belong to exactly one season.`
        );
      }
      owner.set(month, season);
    }
  }
  const missing = Array.from({ length: 12 }, (_, i) => i + 1).filter((m) => !owner.has(m));
  if (missing.length > 0) {
    throw new Error(
      `No season covers month(s) ${missing.join(", ")}. ` +
        `Add them to a season in your rooms config.`
    );
  }
}

/**
 * Reject two rooms sharing a roomId.
 *
 * A roomId addresses one panel in the extranet calendar, so two rooms pointing
 * at the same one cannot both be priced -- the second would overwrite the
 * first. Worse, it does not fail loudly: the plan groups by roomId, so the two
 * rooms' rows interleave and every single date collapses into its own range.
 * You get a plausible-looking plan with hundreds of one-day writes.
 */
export function assertUniqueRoomIds(rooms: RoomsConfig): void {
  const byRoomId = new Map<string, string[]>();
  for (const [name, config] of Object.entries(rooms.rooms)) {
    const names = byRoomId.get(config.roomId);
    if (names) names.push(name);
    else byRoomId.set(config.roomId, [name]);
  }
  for (const [roomId, names] of byRoomId) {
    if (names.length > 1) {
      throw new Error(
        `roomId "${roomId}" is used by ${names.length} rooms (${names.join(", ")}). ` +
          `Each room needs its own roomId from the extranet calendar.`
      );
    }
  }
}

export async function loadConfig(dir = "config"): Promise<Config> {
  const [pricingRaw, roomsRaw, sourceRaw] = await Promise.all([
    readJson(`${dir}/pricing.json`),
    readJson(`${dir}/rooms.json`),
    readJson(`${dir}/source.json`),
  ]);
  const pricing = parseFile(PricingConfigSchema, pricingRaw, `${dir}/pricing.json`);
  const rooms = parseFile(RoomsConfigSchema, roomsRaw, `${dir}/rooms.json`);
  const source = parseFile(SourceConfigSchema, sourceRaw, `${dir}/source.json`);
  assertSeasonsCoverTheYear(rooms);
  assertUniqueRoomIds(rooms);
  return { pricing, rooms, source };
}
