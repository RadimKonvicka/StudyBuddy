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

/**
 * @param {string} path  např. "/api/subjects"
 * @param {{method?: string, body?: any, form?: FormData, timeout?: number, auth?: boolean}} opts
 */
export async function api(path, { method = "GET", body, form, timeout = 30000, auth = true } = {}) {
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
