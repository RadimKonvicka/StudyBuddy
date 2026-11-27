// Jediné místo, přes které frontend komunikuje s backendem.
// Přidá token, nastaví časový limit a převede všechny chyby na srozumitelnou českou hlášku.
import { clearSession, getToken, redirectToLogin } from "./auth.js";

export const API = (import.meta.env.PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.status = status;
  }
}

// Server zdarma (Render) po 15 minutách nečinnosti usne a probouzí se asi minutu. Proto běžné
// požadavky čekají až 90 s a když odpověď nepřijde do pár sekund, ukážeme, co se děje.
const WAKE_NOTICE_MS = 4000;
let pending = 0;
let noticeTimer = null;

function wakeNotice(show) {
  let el = document.getElementById("wake-notice");
  if (!show) {
    el?.remove();
    return;
  }
  if (el) return;
  el = document.createElement("div");
  el.id = "wake-notice";
  el.className = "fixed top-16 left-1/2 -translate-x-1/2 z-50 card px-4 py-2 text-sm shadow flex items-center gap-2";
  el.setAttribute("role", "status");
  el.innerHTML = `<span class="h-4 w-4 rounded-full border-2 border-line border-t-accent animate-spin"></span>
    Probouzím server, první načtení může trvat až minutu…`;
  document.body.append(el);
}

function startRequest() {
  pending += 1;
  if (pending === 1) noticeTimer = setTimeout(() => wakeNotice(true), WAKE_NOTICE_MS);
}

function endRequest() {
  pending = Math.max(0, pending - 1);
  if (pending === 0) {
    clearTimeout(noticeTimer);
    wakeNotice(false);
  }
}

/**
 * @param {string} path  např. "/api/subjects"
 * @param {{method?: string, body?: any, form?: FormData, timeout?: number, auth?: boolean}} opts
 */
export async function api(path, opts = {}) {
  // dlouhé volání AI má vlastní hlášku o čekání – tam probouzení neukazujeme
  const quiet = (opts.timeout ?? 0) > 90000;
  if (!quiet) startRequest();
  try {
    return await request(path, opts);
  } finally {
    if (!quiet) endRequest();
  }
}

async function request(path, { method = "GET", body, form, timeout = 90000, auth = true } = {}) {
  const headers = {};
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res;
  try {
    res = await fetch(API + path, {
      method,
      headers,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal: AbortSignal.timeout(timeout),
    });
  } catch (err) {
    if (err.name === "TimeoutError") throw new ApiError("Server neodpověděl včas. Zkus to prosím znovu.");
    throw new ApiError("Nepodařilo se spojit se serverem. Běží backend?");
  }

  if (res.status === 401 && auth) {
    clearSession();
    redirectToLogin();
    throw new ApiError("Přihlášení vypršelo.", 401);
  }

  const type = res.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const detail = data && typeof data === "object" ? data.detail : null;
    const message = typeof detail === "string" ? detail : `Požadavek selhal (chyba ${res.status}).`;
    throw new ApiError(message, res.status);
  }
  return data;
}
