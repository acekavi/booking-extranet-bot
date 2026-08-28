import { describe, expect, it } from "vitest";
import { groupConsecutiveByValue } from "./ranges.js";

describe("groupConsecutiveByValue", () => {
  it("returns nothing for no entries", () => {
    expect(groupConsecutiveByValue([])).toEqual([]);
  });

  it("collapses a constant run into one range", () => {
    expect(
      groupConsecutiveByValue([
        { date: "2027-01-01", value: 50 },
        { date: "2027-01-02", value: 50 },
        { date: "2027-01-03", value: 50 },
      ])
    ).toEqual([{ from: "2027-01-01", to: "2027-01-03", value: 50 }]);
  });

  it("splits where the value changes", () => {
    expect(
      groupConsecutiveByValue([
        { date: "2027-01-01", value: 50 },
        { date: "2027-01-02", value: 60 },
        { date: "2027-01-03", value: 60 },
      ])
    ).toEqual([
      { from: "2027-01-01", to: "2027-01-01", value: 50 },
      { from: "2027-01-02", to: "2027-01-03", value: 60 },
    ]);
  });

  it("does not merge equal values that are not adjacent", () => {
    const ranges = groupConsecutiveByValue([
      { date: "2027-01-01", value: 50 },
      { date: "2027-01-02", value: 60 },
      { date: "2027-01-03", value: 50 },
    ]);
    expect(ranges).toHaveLength(3);
  });

  it("handles a single entry", () => {
    expect(groupConsecutiveByValue([{ date: "2027-01-01", value: 7 }])).toEqual([
      { from: "2027-01-01", to: "2027-01-01", value: 7 },
    ]);
  });
});
