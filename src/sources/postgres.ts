import type { Booking, PriceSource, PriceTable } from "./types.js";

/**
 * Prices and bookings from your own Postgres database.
 *
 * The queries are supplied by config, not written here, for two reasons: no
 * two property websites share a schema, and publishing this tool should not
 * publish yours. This file only knows the SHAPE of the results.
 *
 *   pricesQuery   -> rows of { room, season, price }
 *   bookingsQuery -> rows of { reference, room, checkIn, checkOut, quantity }
 *
 * `pg` is an optional dependency, so users on the JSON source need not install it.
 */
export class PostgresPriceSource implements PriceSource {
  readonly describe = "postgres";

  constructor(
    private readonly connectionString: string,
    private readonly pricesQuery: string,
    private readonly bookingsQuery?: string
  ) {}

  private async withClient<T>(run: (query: (sql: string) => Promise<any[]>) => Promise<T>): Promise<T> {
    let Client: new (config: { connectionString: string }) => any;
    try {
      ({ Client } = await import("pg"));
    } catch {
      throw new Error(
        `The postgres source needs the "pg" package. Install it with: npm install pg`
      );
    }
    const client = new Client({ connectionString: this.connectionString });
    await client.connect();
    try {
      return await run(async (sql: string) => (await client.query(sql)).rows);
    } finally {
      await client.end();
    }
  }

  async prices(): Promise<PriceTable> {
    return this.withClient(async (query) => {
      const rows = await query(this.pricesQuery);
      if (rows.length === 0) {
        // Pushing an empty price table would blank a live listing's rates.
        throw new Error("pricesQuery returned no rows — refusing to continue with no prices");
      }
      const table: PriceTable = {};
      for (const [index, row] of rows.entries()) {
        const { room, season, price } = row;
        if (room == null || season == null || price == null) {
          throw new Error(
            `pricesQuery row ${index + 1} is missing room, season or price. ` +
              `Alias your columns, e.g. select name as room, label as season, rate as price`
          );
        }
        const value = Number(price);
        if (!Number.isFinite(value) || value <= 0) {
          throw new Error(`pricesQuery returned a non-positive price for ${room}/${season}: ${price}`);
        }
        (table[String(room)] ??= {})[String(season)] = value;
      }
      return table;
    });
  }

  async bookings(): Promise<Booking[]> {
    if (!this.bookingsQuery) return [];
    return this.withClient(async (query) => {
      const rows = await query(this.bookingsQuery!);
      return rows.map((row, index) => {
        const quantity = Number(row.quantity ?? 1);
        if (!Number.isInteger(quantity) || quantity < 1) {
          throw new Error(`bookingsQuery row ${index + 1}: quantity must be a positive integer`);
        }
        return {
          reference: String(row.reference ?? `row-${index + 1}`),
          room: String(row.room),
          checkIn: String(row.checkIn).slice(0, 10),
          checkOut: String(row.checkOut).slice(0, 10),
          quantity,
        };
      });
    });
  }
}
