export function toF(c: number): number {
  return Math.round((c * 9) / 5 + 32);
}

export function money(n: number | null | undefined): string {
  if (n === null || n === undefined) return "–";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: n < 10 ? 2 : 0 });
}

/** Local YYYY-MM-DD (not UTC, which flips to tomorrow in the evening in the US). */
export function isoDay(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function nextDays(start: Date, n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return isoDay(d);
  });
}

export function dayLabel(iso: string, today: string): string {
  if (iso === today) return "Today";
  const d = new Date(`${iso}T12:00:00`);
  const t = new Date(`${today}T12:00:00`);
  if ((d.getTime() - t.getTime()) / 86400000 === 1) return "Tmrw";
  return d.toLocaleDateString("en-US", { weekday: "short" });
}

export function timeLabel(iso: string | null): string {
  if (!iso) return "All day";
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function daysAgo(iso: string | null, today: string): string {
  if (!iso) return "never";
  const n = Math.round((new Date(`${today}T12:00:00`).getTime() - new Date(`${iso}T12:00:00`).getTime()) / 86400000);
  if (n <= 0) return "today";
  if (n === 1) return "yesterday";
  return `${n} days ago`;
}
