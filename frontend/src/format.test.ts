import { describe, expect, it } from "vitest";
import { dayLabel, daysAgo, isoDay, money, nextDays, toF } from "./format";

describe("format", () => {
  it("converts celsius", () => {
    expect(toF(0)).toBe(32);
    expect(toF(21)).toBe(70);
  });

  it("uses local dates", () => {
    expect(isoDay(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
    expect(nextDays(new Date(2026, 11, 30), 3)).toEqual(["2026-12-30", "2026-12-31", "2027-01-01"]);
  });

  it("labels days", () => {
    expect(dayLabel("2026-10-23", "2026-10-23")).toBe("Today");
    expect(dayLabel("2026-10-24", "2026-10-23")).toBe("Tmrw");
    expect(dayLabel("2026-10-27", "2026-10-23")).toBe("Tue");
    expect(daysAgo(null, "2026-10-23")).toBe("never");
    expect(daysAgo("2026-10-20", "2026-10-23")).toBe("3 days ago");
  });

  it("formats money", () => {
    expect(money(null)).toBe("–");
    expect(money(4.5)).toBe("$4.50");
    expect(money(120)).toBe("$120");
  });
});
