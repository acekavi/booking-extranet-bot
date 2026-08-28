import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { Journal } from "./journal.js";

let dir: string;
beforeEach(async () => {
  dir = await mkdtemp(path.join(tmpdir(), "journal-"));
});
afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

const entry = {
  roomId: "ROOM_A",
  room: "Example Room",
  kind: "rate" as const,
  from: "2027-01-01",
  to: "2027-01-31",
  value: 100,
};

describe("Journal", () => {
  it("writes a header and a row on the first record", async () => {
    const journal = new Journal(path.join(dir, "j.csv"));
    await journal.record(entry);
    const text = await readFile(journal.path, "utf-8");
    expect(text.split("\n")[0]).toBe("roomId,room,kind,from,to,value,appliedAt");
    expect(text).toContain("ROOM_A,Example Room,rate,2027-01-01,2027-01-31,100");
  });

  it("appends after every write, so a crash cannot lose the record", async () => {
    const journal = new Journal(path.join(dir, "j.csv"));
    await journal.record(entry);
    // Simulating a crash: nothing is flushed at the end, yet the row is there.
    expect(await readFile(journal.path, "utf-8")).toContain("2027-01-01");
    await journal.record({ ...entry, from: "2027-02-01", to: "2027-02-28" });
    expect((await readFile(journal.path, "utf-8")).trim().split("\n")).toHaveLength(3);
  });

  it("reports a recorded write as done", async () => {
    const journal = new Journal(path.join(dir, "j.csv"));
    expect(journal.isDone(entry)).toBe(false);
    await journal.record(entry);
    expect(journal.isDone(entry)).toBe(true);
  });

  it("does not treat a different value as already done", async () => {
    const journal = new Journal(path.join(dir, "j.csv"));
    await journal.record(entry);
    expect(journal.isDone({ ...entry, value: 200 })).toBe(false);
  });

  it("resumes from a previous run's journal", async () => {
    const first = new Journal(path.join(dir, "first.csv"));
    await first.record(entry);
    await first.record({ ...entry, kind: "availability", value: 3 });

    const second = new Journal(path.join(dir, "second.csv"));
    expect(await second.resumeFrom(first.path)).toBe(2);
    expect(second.isDone(entry)).toBe(true);
  });

  it("says so when there is no journal to resume from", async () => {
    const journal = new Journal(path.join(dir, "j.csv"));
    await expect(journal.resumeFrom(path.join(dir, "missing.csv"))).rejects.toThrow(/not found/);
  });
});
