// Uložení přihlášení v prohlížeči.
// JWT držíme v localStorage a posíláme v hlavičce Authorization. Cookie by mezi doménami
// Vercel (frontend) a Render (backend) narážela na blokování cookies třetích stran.

const TOKEN_KEY = "sb_token";
const USER_KEY = "sb_user";

function safeGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function getToken() {
  return safeGet(TOKEN_KEY);
}

export function getUser() {
  try { return JSON.parse(safeGet(USER_KEY) || "null"); } catch { return null; }
}

export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function updateUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent("sb:user", { detail: user }));
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {}
}

export function logout() {
  clearSession();
  location.href = "/login";
}

/** Přesměruje na přihlášení a po něm vrátí uživatele zpět na původní stránku. */
export function redirectToLogin() {
  const next = encodeURIComponent(location.pathname + location.search);
  location.href = `/login?next=${next}`;
}
