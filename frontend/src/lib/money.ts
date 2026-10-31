// Display-only helpers (rule 5). Money stays a string end to end; cents are used only to add up what the user
// is typing so the form can show live totals. The server recomputes every amount.
export function toCents(s: string | null | undefined): number | null {
  const m = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec((s ?? "").trim());
  if (!m) return null;
  const cents = parseInt(m[2], 10) * 100 + parseInt((m[3] ?? "").padEnd(2, "0") || "0", 10);
  return m[1] ? -cents : cents;
}

export function centsToStr(c: number): string {
  const a = Math.abs(c);
  return `${c < 0 ? "-" : ""}${Math.floor(a / 100)}.${String(a % 100).padStart(2, "0")}`;
}
