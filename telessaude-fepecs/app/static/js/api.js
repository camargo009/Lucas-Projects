export const S = { token: localStorage.getItem("tok"), me: null, d: null, ws: null, onPush: null };

export async function api(path, body, method) {
  const opt = { method: method || (body !== undefined ? "POST" : "GET"), headers: { "Content-Type": "application/json" } };
  if (S.token) opt.headers.Authorization = "Bearer " + S.token;
  if (body !== undefined) opt.body = JSON.stringify(body);
  const r = await fetch("/api" + path, opt);
  let j = {};
  try { j = await r.json(); } catch (e) { /* sem corpo */ }
  if (r.status === 401 && S.token && path !== "/login") { sair(true); throw new Error("Sessão expirada"); }
  if (!r.ok) throw new Error(j.erro || "Falha na requisição");
  return j;
}

export async function carregar() {
  S.d = await api("/state");
  S.me = S.d.me;
  return S.d;
}

export function sair(silencioso) {
  S.token = null; S.me = null; S.d = null;
  localStorage.removeItem("tok");
  if (S.ws) { try { S.ws.close(); } catch (e) { /* ignora */ } S.ws = null; }
  if (!silencioso) location.hash = "#/login"; else location.hash = "#/login";
  location.reload();
}

export function conectarWS() {
  if (S.ws) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws?token=${S.token}`);
  S.ws = ws;
  ws.onmessage = (ev) => { try { S.onPush && S.onPush(JSON.parse(ev.data)); } catch (e) { console.error(e); } };
  ws.onclose = () => { S.ws = null; if (S.token) setTimeout(conectarWS, 2000); };
}
