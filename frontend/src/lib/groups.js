// Společné věci pro stránky tříd.

/** Štítek s rolí ve třídě. */
export function roleChip(role) {
  return role === "teacher"
    ? `<span class="chip bg-accent-soft text-accent">Učitel</span>`
    : `<span class="chip bg-surface-2 text-muted">Žák</span>`;
}

/** Poslední aktivita srozumitelně: dnes / včera / před 3 dny / 12. 11. 2026 / nikdy. */
export function lastActive(isoDate) {
  if (!isoDate) return "zatím nikdy";
  const [y, m, d] = isoDate.split("-").map(Number);
  const day = new Date(y, m - 1, d);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - day) / 86400000);
  if (diff <= 0) return "dnes";
  if (diff === 1) return "včera";
  if (diff < 7) return `před ${diff} dny`;
  return day.toLocaleDateString("cs-CZ");
}

/** Úroveň zvládnutí z procent (stejné hranice jako backend: <50 slabé, <80 částečně). */
export function levelOf(mastery) {
  if (mastery === null || mastery === undefined) return null;
  return mastery < 50 ? "weak" : mastery < 80 ? "mid" : "strong";
}
