function padDatePart(value: number): string {
  return String(value).padStart(2, "0");
}

/**
 * Convert the API's timezone-aware timestamp to the user's local time.
 */
export function formatLogTime(timestamp: string): string {
  const milliseconds =
    timestamp.match(/\.(\d{1,3})/)?.[1]?.padEnd(3, "0") ?? "000";
  const normalizedTimestamp = timestamp.replace(/^(\d{4}-\d{2}-\d{2}) /, "$1T");
  const date = new Date(normalizedTimestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  const datePart = [
    date.getFullYear(),
    padDatePart(date.getMonth() + 1),
    padDatePart(date.getDate()),
  ].join("-");
  const timePart = [
    padDatePart(date.getHours()),
    padDatePart(date.getMinutes()),
    padDatePart(date.getSeconds()),
  ].join(":");

  return `${datePart} ${timePart}.${milliseconds}`;
}
