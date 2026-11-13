// Společné věci pro stránky s učením: úrovně zvládnutí, ukazatel pokroku, ID z adresy.
import { esc } from "./dom.js";

// Generování přes AI trvá déle než běžný požadavek – dáme mu až 2 minuty.
export const AI_TIMEOUT = 120000;

// Třídy musí být napsané celé (ne skládané), aby je Tailwind našel a vygeneroval.
export const LEVELS = {
  weak: { label: "Slabé", bar: "bg-weak", text: "text-weak" },
  mid: { label: "Částečně", bar: "bg-mid", text: "text-mid" },
  strong: { label: "Zvládnuté", bar: "bg-strong", text: "text-strong" },
};

/** Vodorovný ukazatel zvládnutí 0–100 % (barva podle úrovně). */
export function masteryBar(mastery, level) {
  if (mastery === null || mastery === undefined) {
    return `<div class="text-xs text-muted">Zatím netestováno</div>`;
  }
  const l = LEVELS[level] || LEVELS.mid;
  return `
    <div class="flex items-center gap-2">
      <div class="h-2 flex-1 rounded-full bg-surface-2 overflow-hidden" role="progressbar"
           aria-valuenow="${mastery}" aria-valuemin="0" aria-valuemax="100">
        <div class="h-full rounded-full ${l.bar}" style="width:${Math.max(3, mastery)}%"></div>
      </div>
      <span class="text-xs font-medium tabular-nums ${l.text} w-24 text-right">${mastery} % · ${l.label}</span>
    </div>`;
}

/** Malý štítek s úrovní. */
export function levelChip(level) {
  if (!level) return `<span class="chip bg-surface-2 text-muted">Netestováno</span>`;
  const l = LEVELS[level];
  return `<span class="chip bg-surface-2 ${l.text}">${esc(l.label)}</span>`;
}

/** ?id=12 z adresy stránky → 12 (nebo null, když chybí či je neplatné). */
export function idFromUrl() {
  const id = Number(new URLSearchParams(location.search).get("id"));
  return Number.isInteger(id) && id > 0 ? id : null;
}

/** Text čekání na AI s animovaným kolečkem. */
export function aiLoading(message) {
  return `
    <div class="card p-8 flex flex-col items-center gap-3 text-center">
      <div class="h-8 w-8 rounded-full border-4 border-line border-t-accent animate-spin"></div>
      <p class="font-medium">${esc(message)}</p>
      <p class="text-sm text-muted">Umělá inteligence obvykle potřebuje 10–40 sekund. Nezavírej stránku.</p>
    </div>`;
}
