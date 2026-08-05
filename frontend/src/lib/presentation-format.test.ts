import { describe, expect, it } from "vitest";
import { formatCurrency, formatDateTime } from "./presentation-format";

describe("presentation formatting", () => {
  it("uses the organization's locale and time zone for dates", () => {
    expect(
      formatDateTime(
        "2026-07-12T08:00:00Z",
        { locale: "en-US", timeZone: "Asia/Jakarta" },
        {
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
          month: "short",
          year: "numeric",
        },
      ),
    ).toContain("3:00 PM");
  });

  it("uses the organization's locale for currency", () => {
    expect(
      formatCurrency(1250, "USD", {
        locale: "en-US",
        timeZone: "Asia/Jakarta",
      }),
    ).toBe("$1,250.00");
  });
});
