import { describe, expect, it } from "vitest";
import { datesInMonth, monthsBetween, nightsOfStay } from "./dates.js";

describe("nightsOfStay", () => {
  it("includes check-in and excludes check-out", () => {
    expect(nightsOfStay("2027-03-01", "2027-03-04")).toEqual([
      "2027-03-01",
      "2027-03-02",
      "2027-03-03",
    ]);
  });

  it("returns nothing for a same-day stay", () => {
    expect(nightsOfStay("2027-03-01", "2027-03-01")).toEqual([]);
  });

  it("crosses a month boundary", () => {
    expect(nightsOfStay("2027-01-31", "2027-02-02")).toEqual(["2027-01-31", "2027-02-01"]);
  });

  it("rejects unparseable dates rather than looping forever", () => {
    expect(() => nightsOfStay("not-a-date", "2027-01-01")).toThrow(/Invalid stay dates/);
  });
});

describe("datesInMonth", () => {
  it("handles a 31-day month", () => {
    expect(datesInMonth("2027-01")).toHaveLength(31);
  });

  it("handles a leap February", () => {
    expect(datesInMonth("2028-02")).toHaveLength(29);
    expect(datesInMonth("2027-02")).toHaveLength(28);
  });

  it("zero-pads days", () => {
    expect(datesInMonth("2027-03")[0]).toBe("2027-03-01");
  });

  it("rejects a malformed month", () => {
    expect(() => datesInMonth("2027-13")).toThrow(/Invalid month/);
  });
});

describe("monthsBetween", () => {
  it("is inclusive at both ends", () => {
    expect(monthsBetween("2027-01", "2027-03")).toEqual(["2027-01", "2027-02", "2027-03"]);
  });

  it("rolls over the year", () => {
    expect(monthsBetween("2027-11", "2028-02")).toEqual([
      "2027-11",
      "2027-12",
      "2028-01",
      "2028-02",
    ]);
  });

  it("returns a single month when both ends match", () => {
    expect(monthsBetween("2027-05", "2027-05")).toEqual(["2027-05"]);
  });

  it("rejects a backwards range instead of returning nothing", () => {
    expect(() => monthsBetween("2027-06", "2027-01")).toThrow(/runs backwards/);
  });
});
