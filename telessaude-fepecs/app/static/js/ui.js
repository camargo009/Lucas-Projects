import { S } from "./api.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const P = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const ic = {
  home: P('<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>'),
  inbox: P('<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/>'),
  plus: P('<path d="M12 5v14M5 12h14"/>'),
  cal: P('<rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/>'),
  video: P('<rect x="2" y="6" width="14" height="12"/><path d="M16 10l6-3v10l-6-3"/>'),
  users: P('<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-4 3-6 7-6s7 2 7 6"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14c2.5.6 4 2.4 4 6"/>'),
  lung: P('<path d="M12 4v9"/><path d="M12 8c-3 0-6 4-6 9 0 2 1 3 3 3 2 0 3-1 3-3"/><path d="M12 8c3 0 6 4 6 9 0 2-1 3-3 3-2 0-3-1-3-3"/>'),
  help: P('<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 015 .5c0 1.7-2.5 2-2.5 4M12 17v.5"/>'),
  gear: P('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>'),
  link: P('<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>'),
  flow: P('<rect x="3" y="3" width="7" height="5"/><rect x="14" y="16" width="7" height="5"/><path d="M6.5 8v5h11v3"/>'),
  bell: P('<path d="M6 17V11a6 6 0 0112 0v6l2 2H4z"/><path d="M10 21h4"/>'),
  mic: P('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>'),
  micoff: P('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3M3 3l18 18"/>'),
  cam: P('<rect x="2" y="6" width="14" height="12"/><path d="M16 10l6-3v10l-6-3"/>'),
  camoff: P('<rect x="2" y="6" width="14" height="12"/><path d="M16 10l6-3v10l-6-3M3 3l18 18"/>'),
  screen: P('<rect x="3" y="4" width="18" height="12"/><path d="M8 21h8M12 16v5"/>'),
  phone: P('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>'),
  check: P('<path d="M4 12l5 5L20 6"/>'),
  print: P('<path d="M6 9V3h12v6M6 18H3v-8h18v8h-3"/><rect x="6" y="14" width="12" height="7"/>'),
  shield: P('<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>'),
  scroll: P('<path d="M6 3h11a2 2 0 012 2v14a2 2 0 01-2 2H6z"/><path d="M9 8h7M9 12h7M9 16h4"/>'),
  sparkle: P('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>'),
};

const TZ = "America/Sao_Paulo";
const f2 = (o) => new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, ...o });
export const dt = (t) => (t ? f2({ day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(t) : "—");
export const dsh = (t) => (t ? f2({ day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(t) : "—");
export const hm = (t) => f2({ hour: "2-digit", minute: "2-digit" }).format(t);
export const dia = (t) => f2({ weekday: "short", day: "2-digit", month: "2-digit" }).format(t);
export const diaKey = (t) => f2({ year: "numeric", month: "2-digit", day: "2-digit" }).format(t);
export const idade = (n) => { const a = new Date(n), h = new Date(); let i = h.getFullYear() - a.getFullYear(); if (h < new Date(h.getFullYear(), a.getMonth(), a.getDate())) i--; return i; };

export const nowMs = () => Date.now();
export function rel(t) {
  const m = Math.round((t - Date.now()) / 60000), a = Math.abs(m);
  const s = a < 60 ? `${a} min` : a < 2880 ? `${Math.round(a / 60)} h` : `${Math.round(a / 1440)} d`;
  return m >= 0 ? "em " + s : "há " + s;
}

export const usr = (id) => S.d.users.find((u) => u.id === id) || { nome: "—" };
export const pac = (id) => S.d.patients.find((p) => p.id === id) || { nome: "—" };
export const und = (id) => S.d.units.find((u) => u.id === id) || { nome: "—" };
export const caso = (id) => S.d.cases.find((c) => c.id === id);
export const ini = (nome) => nome.split(" ").filter((x) => x.length > 2).slice(0, 2).map((x) => x[0]).join("").toUpperCase();

export const PERFIL = { admin: "Administrador", gestor: "Gestor", solicitante: "Profissional assistencial", especialista: "Teleconsultor", enfermagem: "Profissional assistencial (enfermagem)", suporte: "Suporte técnico", paciente: "Paciente" };
export const TIPO = { teleparecer: "Teleparecer", teleinterconsulta: "Teleinterconsulta", teleconsultoria: "Teleconsultoria", teleconsulta: "Teleconsulta", teletriagem: "Teletriagem", telemonitoramento: "Telemonitoramento" };
export const STATUS = { aguardando: "Aguardando especialista", em_analise: "Em análise", info_solicitada: "Informação solicitada", teleatendimento_agendado: "Teleatendimento agendado", em_atendimento: "Em atendimento", respondido: "Respondido", encerrado: "Encerrado" };
export const stHtml = (s) => `<span class="st ${s}">${STATUS[s] || s}</span>`;
export const priTag = (p) => (p === "Urgente" ? '<span class="tag verm">Urgente</span>' : p === "Prioritário" ? '<span class="tag ambar">Prioritário</span>' : '<span class="tag">Rotina</span>');
export const priCls = (p) => (p === "Urgente" ? "u" : p === "Prioritário" ? "p" : "");

export function slaHtml(c) {
  if (!c.prazo || ["respondido", "encerrado"].includes(c.status)) return '<span class="muted small">—</span>';
  const tot = c.prazo - c.criado, gasto = Date.now() - c.criado, pct = Math.min(100, Math.max(4, (gasto / tot) * 100));
  const late = Date.now() > c.prazo;
  return `<div class="small ${late ? "" : "muted"}" style="${late ? "color:var(--verm)" : ""}">${late ? "Prazo vencido " : "Prazo "}${rel(c.prazo)}</div><div class="sla ${late ? "late" : ""}" style="width:110px"><i style="width:${pct}%"></i></div>`;
}

export function toast(msg, err, link) {
  const el = document.createElement("div");
  el.className = "toast" + (err ? " err" : "");
  el.textContent = msg;
  el.onclick = () => { if (link) location.hash = "#" + link; el.remove(); };
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => el.remove(), 6500);
}

export function modal({ titulo, corpo, ok = "Confirmar", cancel = "Cancelar", lg = false, onOk, semRodape = false }) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `<div class="mod-bg"><div class="modal ${lg ? "lg" : ""}"><div class="mh"><h3>${esc(titulo)}</h3><button class="btn sec sm" data-x>Fechar</button></div><div class="mb">${corpo}</div>${semRodape ? "" : `<div class="mf"><button class="btn sec" data-x>${cancel}</button><button class="btn" data-ok>${ok}</button></div>`}</div></div>`;
  const close = () => { root.innerHTML = ""; };
  root.querySelectorAll("[data-x]").forEach((b) => (b.onclick = close));
  const okb = root.querySelector("[data-ok]");
  if (okb) okb.onclick = async () => {
    okb.disabled = true;
    try { const r = await onOk(root.querySelector(".modal")); if (r !== false) close(); } catch (e) { toast(e.message, true); }
    okb.disabled = false;
  };
  return { close, el: root.querySelector(".modal") };
}

export const pageHead = (t, sub, acoes = "") => `<div class="pg-h"><div><h1>${t}</h1>${sub ? `<p>${sub}</p>` : ""}</div><div class="bar">${acoes}</div></div>`;

export async function sha256(txt) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(txt));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
