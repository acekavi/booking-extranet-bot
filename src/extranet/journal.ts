/**
 * A record of what was actually written, appended AS IT HAPPENS.
 *
 * Buffering the log until the run finishes is a trap: a push is dozens of slow
 * browser interactions against a panel that intermittently misbehaves, and the
 * run that crashes at range 100 of 128 is exactly the run whose record you
 * need. Appending after each write means the journal survives a crash, a
 * timeout, or a Ctrl-C -- and a later run can skip what already landed.
 */
import { appendFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { escapeCsv, parseCsvRecords } from "../domain/csv.js";

export type WriteKind = "availability" | "rate" | "rate-breakfast";

export interface JournalEntry {
  roomId: string;
  room: string;
  kind: WriteKind;
  from: string;
  to: string;
  value: number;
  appliedAt: string;
}

const HEADERS = ["roomId", "room", "kind", "from", "to", "value", "appliedAt"] as const;

/** Identity of one write, for resume checks. Excludes the timestamp. */
function keyOf(entry: Omit<JournalEntry, "appliedAt">): string {
  return [entry.roomId, entry.kind, entry.from, entry.to, entry.value].join("|");
}

export class Journal {
  private readonly applied = new Set<string>();
  private started = false;

  constructor(private readonly filePath: string) {}

  /** Load a previous run's journal so completed writes can be skipped. */
  async resumeFrom(filePath: string): Promise<number> {
    let text: string;
    try {
      text = await readFile(filePath, "utf-8");
    } catch {
      throw new Error(`Cannot resume: ${filePath} not found`);
    }
    for (const record of parseCsvRecords(text)) {
      this.applied.add(
        keyOf({
          roomId: record.roomId!,
          room: record.room!,
          kind: record.kind as WriteKind,
          from: record.from!,
          to: record.to!,
          value: Number(record.value),
        })
      );
    }
    return this.applied.size;
  }

  /** True if an identical write is already recorded as done. */
  isDone(entry: Omit<JournalEntry, "appliedAt">): boolean {
    return this.applied.has(keyOf(entry));
  }

  async record(entry: Omit<JournalEntry, "appliedAt">): Promise<void> {
    const full: JournalEntry = { ...entry, appliedAt: new Date().toISOString() };
    if (!this.started) {
      await mkdir(path.dirname(this.filePath), { recursive: true });
      await appendFile(this.filePath, HEADERS.join(",") + "\n");
      this.started = true;
    }
    const row = HEADERS.map((h) => escapeCsv(String(full[h]))).join(",");
    await appendFile(this.filePath, row + "\n");
    this.applied.add(keyOf(entry));
  }

  get path(): string {
    return this.filePath;
  }
}
