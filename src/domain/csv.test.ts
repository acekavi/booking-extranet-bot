import { describe, expect, it } from "vitest";
import { escapeCsv, parseCsv, parseCsvRecords, toCsv } from "./csv.js";

describe("escapeCsv", () => {
  it("leaves plain values alone", () => {
    expect(escapeCsv("hello")).toBe("hello");
  });

  it("quotes values containing a comma, quote or newline", () => {
    expect(escapeCsv("a,b")).toBe('"a,b"');
    expect(escapeCsv('say "hi"')).toBe('"say ""hi"""');
    expect(escapeCsv("two\nlines")).toBe('"two\nlines"');
  });
});

describe("parseCsv", () => {
  it("round-trips values that need quoting", () => {
    const rows = [["a,b", 'say "hi"', "two\nlines"]];
    expect(parseCsv(toCsv(["x", "y", "z"], rows))[1]).toEqual(rows[0]);
  });

  it("treats a newline inside quotes as data, not a new record", () => {
    expect(parseCsv('a,"line1\nline2",c')).toEqual([["a", "line1\nline2", "c"]]);
  });

  it("treats CRLF as one separator", () => {
    expect(parseCsv("a,b\r\nc,d")).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("handles an escaped quote at the end of a field", () => {
    expect(parseCsv('"he said ""go""",x')).toEqual([['he said "go"', "x"]]);
  });
});

describe("parseCsvRecords", () => {
  it("keys fields by header", () => {
    expect(parseCsvRecords("a,b\n1,2\n")).toEqual([{ a: "1", b: "2" }]);
  });

  it("returns nothing for an empty document", () => {
    expect(parseCsvRecords("")).toEqual([]);
  });

  it("ignores a trailing blank line", () => {
    expect(parseCsvRecords("a,b\n1,2\n\n")).toHaveLength(1);
  });

  it("fills missing trailing columns with empty strings", () => {
    expect(parseCsvRecords("a,b,c\n1,2\n")).toEqual([{ a: "1", b: "2", c: "" }]);
  });
});
