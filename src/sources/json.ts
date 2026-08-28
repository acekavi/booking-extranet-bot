import { readFile } from "node:fs/promises";
import { z } from "zod";
import { parseCsvRecords } from "../domain/csv.js";
import type { Booking, PriceSource, PriceTable } from "./types.js";

const PriceTableSchema = z.record(z.string(), z.record(z.string(), z.number().positive()));

const BOOKING_COLUMNS = ["reference", "room", "checkIn", "checkOut", "quantity"] as const;

/**
 * Prices from a JSON file, bookings from an optional CSV.
 *
 * This is the zero-setup path, and also the escape hatch: anyone who wants to
 * bypass the pricing model entirely can write final prices into this file.
 */
export class JsonPriceSource implements PriceSource {
  readonly describe: string;

  constructor(
    private readonly pricesPath: string,
    private readonly bookingsPath?: string
  ) {
    this.describe = `json:${pricesPath}`;
  }

  async prices(): Promise<PriceTable> {
    let raw: unknown;
    try {
      raw = JSON.parse(await readFile(this.pricesPath, "utf-8"));
    } catch (error) {
      throw new Error(`Could not read prices from ${this.pricesPath}: ${(error as Error).message}`);
    }
    const parsed = PriceTableSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(
        `${this.pricesPath} must be { "Room name": { "Season name": price } } with ` +
          `positive numbers. First problem: ${parsed.error.issues[0]?.message}`
      );
    }
    return parsed.data;
  }

  async bookings(): Promise<Booking[]> {
    if (!this.bookingsPath) return [];
    let text: string;
    try {
      text = await readFile(this.bookingsPath, "utf-8");
    } catch {
      // An absent bookings file means "nothing sold elsewhere", which is a
      // legitimate state -- but a misspelt path looks identical, so say so.
      console.warn(`  no bookings file at ${this.bookingsPath}; assuming none sold elsewhere`);
      return [];
    }
    const records = parseCsvRecords(text);
    if (records.length === 0) return [];

    const missing = BOOKING_COLUMNS.filter((column) => !(column in records[0]!));
    if (missing.length > 0) {
      throw new Error(
        `${this.bookingsPath} is missing column(s): ${missing.join(", ")}. ` +
          `Expected header: ${BOOKING_COLUMNS.join(",")}`
      );
    }
    return records.map((record, index) => {
      const quantity = Number(record.quantity);
      if (!Number.isInteger(quantity) || quantity < 1) {
        throw new Error(
          `${this.bookingsPath} row ${index + 2}: quantity must be a positive integer, ` +
            `got "${record.quantity}"`
        );
      }
      return {
        reference: record.reference!,
        room: record.room!,
        checkIn: record.checkIn!,
        checkOut: record.checkOut!,
        quantity,
      };
    });
  }
}
