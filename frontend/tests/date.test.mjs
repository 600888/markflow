import assert from "node:assert/strict";
import test from "node:test";

import { formatLogTime } from "../src/lib/date.ts";

test("formats a UTC log timestamp with local date, time, and milliseconds", () => {
  const timestamp = "2026-07-31 01:02:03.123456+00:00";
  const date = new Date("2026-07-31T01:02:03.123456+00:00");
  const pad = (part) => String(part).padStart(2, "0");
  const expected =
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    ".123";

  assert.equal(formatLogTime(timestamp), expected);
});

test("pads timestamps without fractional seconds to millisecond precision", () => {
  assert.match(
    formatLogTime("2026-07-31 01:02:03+00:00"),
    /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.000$/,
  );
});

test("keeps an invalid timestamp visible", () => {
  assert.equal(formatLogTime("unknown"), "unknown");
});
