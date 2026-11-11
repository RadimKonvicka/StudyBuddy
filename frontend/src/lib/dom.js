// Pomocné funkce pro bezpečné vykreslování.
import DOMPurify from "dompurify";
import { marked } from "marked";

/** Escapuje text pro vložení do HTML – vše, co přijde od uživatele nebo AI jako prostý text. */
export const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Markdown z AI → HTML, vždy vyčištěné DOMPurify (odstraní <script>, onclick=… apod.). */
export const md = (text) =>
  DOMPurify.sanitize(marked.parse(String(text ?? ""), { gfm: true, breaks: false }), {
    FORBID_TAGS: ["style", "iframe", "form", "input"],
    FORBID_ATTR: ["style"],
  });

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Krátké oznámení v rohu obrazovky. */
export function toast(message, kind = "info") {
  let host = document.getElementById("toasts");
  if (!host) {
    host = document.createElement("div");
    host.id = "toasts";
    host.className = "fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm";
    host.setAttribute("aria-live", "polite");
    document.body.append(host);
  }
  const colors = { info: "border-line", error: "border-weak", success: "border-strong" };
  const el = document.createElement("div");
  el.className = `card px-4 py-3 text-sm border-l-4 ${colors[kind] || colors.info}`;
  el.textContent = message;
  host.append(el);
  setTimeout(() => el.remove(), 4500);
}

/** Česká pluralizace: plural(3, "kartička", "kartičky", "kartiček") */
export function plural(n, one, few, many) {
  if (n === 1) return one;
  if (n >= 2 && n <= 4) return few;
  return many;
}
