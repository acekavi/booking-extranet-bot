import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { JsonPriceSource } from "./json.js";

let dir: string;
beforeEach(async () => {
  dir = await mkdtemp(path.join(tmpdir(), "source-"));
});
afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

async function write(name: string, content: string): Promise<string> {
  const file = path.join(dir, name);
  await writeFile(file, content);
  return file;
}

describe("JsonPriceSource.prices", () => {
  it("reads a price table", async () => {
    const file = await write("p.json", '{"Example Room":{"High":80,"Low":40}}');
    expect(await new JsonPriceSource(file).prices()).toEqual({
      "Example Room": { High: 80, Low: 40 },
    });
  });

  it("explains itself when the file is missing", async () => {
    const source = new JsonPriceSource(path.join(dir, "nope.json"));
    await expect(source.prices()).rejects.toThrow(/Could not read prices/);
  });

  it("rejects a negative price rather than pushing it", async () => {
    const file = await write("p.json", '{"Example Room":{"High":-5}}');
    await expect(new JsonPriceSource(file).prices()).rejects.toThrow(/positive numbers/);
  });

  it("rejects a price that is a string", async () => {
    const file = await write("p.json", '{"Example Room":{"High":"80"}}');
    await expect(new JsonPriceSource(file).prices()).rejects.toThrow(/positive numbers/);
  });
});

describe("JsonPriceSource.bookings", () => {
  const header = "reference,room,checkIn,checkOut,quantity";

  it("is empty when no bookings path is configured", async () => {
    const file = await write("p.json", "{}");
    expect(await new JsonPriceSource(file).bookings()).toEqual([]);
  });

  it("parses bookings", async () => {
    const prices = await write("p.json", "{}");
    const bookings = await write("b.csv", `${header}\nA1,Example Room,2027-01-01,2027-01-03,2\n`);
    expect(await new JsonPriceSource(prices, bookings).bookings()).toEqual([
      { reference: "A1", room: "Example Room", checkIn: "2027-01-01", checkOut: "2027-01-03", quantity: 2 },
    ]);
  });

  it("names the missing column when the header is wrong", async () => {
    const prices = await write("p.json", "{}");
    const bookings = await write("b.csv", "reference,room,checkIn\nA1,Example Room,2027-01-01\n");
    await expect(new JsonPriceSource(prices, bookings).bookings()).rejects.toThrow(
      /missing column\(s\): checkOut, quantity/
    );
  });

  it("rejects a non-numeric quantity with the row number", async () => {
    const prices = await write("p.json", "{}");
    const bookings = await write("b.csv", `${header}\nA1,Example Room,2027-01-01,2027-01-03,many\n`);
    await expect(new JsonPriceSource(prices, bookings).bookings()).rejects.toThrow(/row 2/);
  });
});
