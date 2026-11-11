import { S, api, carregar, conectarWS, sair } from "./api.js";
import { esc, ic, toast, ini, usr, pac, und, caso, dsh, dt, hm, PERFIL, TIPO, stHtml, priTag, priCls, slaHtml, pageHead, rel, STATUS } from "./ui.js";
import * as V from "./v-casos.js";
import { novo } from "./v-novo.js";
const tabela = V.tabela;
import * as O from "./v-outros.js";
import * as R from "./v-sala.js";

const MENU = {
  admin: ["painel", "casos", "agenda", "reunioes", "telediagnostico", "suporte", "admin", "integracoes", "fluxo"],
  solicitante: ["painel", "novo", "casos", "agenda", "reunioes", "telediagnostico", "suporte", "fluxo"],
  especialista: ["painel", "casos", "agenda", "reunioes", "telediagnostico", "suporte", "fluxo"],
};
const ITEM = {
  painel: ["Painel", "home"], novo: ["Nova solicitação", "plus"], casos: ["Solicitações", "inbox"], agenda: ["Agenda", "cal"],
  reunioes: ["Telerreuniões", "users"], telediagnostico: ["Telediagnóstico", "lung"], suporte: ["Suporte", "help"],
  admin: ["Administração", "gear"], integracoes: ["Integrações", "link"], fluxo: ["Fluxo do teleparecer", "flow"],
};
const GRUPO = { painel: "Atendimento", novo: "Atendimento", casos: "Atendimento", agenda: "Atendimento", reunioes: "Teleeducação e reuniões", telediagnostico: "Diagnóstico", suporte: "Gestão do serviço", admin: "Gestão do serviço", integracoes: "Gestão do serviço", fluxo: "Referência" };

const $app = () => document.getElementById("app");
document.addEventListener("click", (e) => {
  const k = e.target.closest && e.target.closest(".kpi[data-go]");
  if (!k) return;
  if (k.dataset.go === "laudo") { O.setExFiltro("aguardando"); location.hash = "#/telediagnostico"; }
  else { V.setFiltro({ k: k.dataset.go }); location.hash = "#/casos"; }
});
let atual = null;

function rota() {
  const h = location.hash.replace(/^#/, "") || "/";
  const p = h.split("/").filter(Boolean);
  return { p, h };
}

async function render() {
  const { p } = rota();
  if (p[0] === "convidado") return R.convidado(p[1], $app());
  if (p[0] === "verificar") return O.verificar(p[1], $app());
  if (!S.token) return login();
  if (!S.d) {
    try { await carregar(); } catch (e) { return login(); }
    conectarWS();
  }
  if (p[0] === "sala") return R.sala(p[1], $app());
  if (p[0] === "documento") return V.documento(p[1], $app());
  if (!p[0] || p[0] === "login") { location.hash = "#/painel"; return; }
  shell(p);
}

function shell(p) {
  const menu = MENU[S.me.perfil] || MENU.solicitante;
  const naoLidas = S.d.notifs.length;
  let grp = "", nav = "";
  for (const k of menu) {
    if (GRUPO[k] !== grp) { grp = GRUPO[k]; nav += `<div class="grp">${grp}</div>`; }
    const on = p[0] === k || (k === "casos" && p[0] === "casos") ? "on" : "";
    const ct = k === "casos" ? pendentes() : 0;
    nav += `<a href="#/${k}" class="${on}">${ic[ITEM[k][1]]}<span>${ITEM[k][0]}</span>${ct ? `<em class="ct" style="font-style:normal">${ct}</em>` : ""}</a>`;
  }
  const r = $app();
  if (!r.querySelector(".shell")) {
    r.innerHTML = `<div class="shell"><div class="gdf"><span><b>Governo do Distrito Federal</b> · Secretaria de Estado de Saúde · FEPECS</span><span>Ambiente de demonstração · dados fictícios</span></div>
      <aside class="side"><div class="brand"><img src="/img/fepecs.png" alt="FEPECS"><div><div class="nm">Telessaúde FEPECS</div><div class="sb">SES-DF</div></div></div><nav class="nav"></nav>
      <div class="foot"><img src="/img/bazetech.png" alt="BazeTech"><span>Desenvolvido por BazeTech</span></div></aside>
      <section class="main"><header class="top"><div class="crumb"></div><div class="sp"></div><button class="bell" title="Notificações" id="bell">${ic.bell}<i id="bellc"></i></button>
      <div class="me"><div class="av"></div><div class="who"><b></b><span></span></div></div><button class="btn sec sm" id="sair">Sair</button></header><div class="content"></div></section></div>`;
    r.querySelector("#sair").onclick = async () => { try { await api("/logout", {}); } catch (e) { /* ignora */ } sair(); };
    r.querySelector("#bell").onclick = notifs;
  }
  r.querySelector(".nav").innerHTML = nav;
  r.querySelector(".crumb").textContent = "Telessaúde FEPECS / " + (ITEM[p[0]] ? ITEM[p[0]][0] : "Solicitação");
  r.querySelector(".av").textContent = ini(S.me.nome);
  r.querySelector(".who b").textContent = S.me.nome;
  r.querySelector(".who span").textContent = PERFIL[S.me.perfil] + " · " + und(S.me.unidade).nome.replace(/\s*\(.*\)/, "");
  const bc = r.querySelector("#bellc");
  bc.textContent = naoLidas || ""; bc.style.display = naoLidas ? "" : "none";
  const box = r.querySelector(".content");
  const mod = { painel: painel, novo: novo, casos: V.lista, agenda: O.agenda, reunioes: O.reunioes, telediagnostico: O.telediagnostico, suporte: O.suporte, admin: O.admin, integracoes: O.integracoes, fluxo: O.fluxo };
  const fn = p[0] === "casos" && p[1] ? V.detalhe : mod[p[0]];
  if (!fn) { box.innerHTML = pageHead("Página não encontrada"); return; }
  const scroll = box.scrollTop;
  const key = location.hash;
  const out = fn(p[1], box);
  if (typeof out === "string") box.innerHTML = out; else if (out && out.html !== undefined) { box.innerHTML = out.html; out.after && out.after(box); }
  atual = key;
  box.scrollTop = scroll;
}

function pendentes() {
  const m = S.me;
  const ab = (c) => !["respondido", "encerrado"].includes(c.status);
  if (m.perfil === "especialista") return S.d.cases.filter((c) => ab(c) && (c.especialista === m.id || (!c.especialista && c.especialidade === m.especialidade)) && c.status !== "info_solicitada").length;
  if (["solicitante", "enfermagem"].includes(m.perfil)) return S.d.cases.filter((c) => c.solicitante === m.id && c.status === "info_solicitada").length;
  return 0;
}

function notifs() {
  const l = S.d.notifs;
  import("./ui.js").then(({ modal }) => modal({ titulo: "Notificações", semRodape: true, corpo: l.length ? `<table class="t"><tbody>${l.map((n) => `<tr class="row" data-l="${esc(n.link || "")}"><td>${esc(n.texto)}<div class="small muted">${dsh(n.ts)}</div></td></tr>`).join("")}</tbody></table>` : '<p class="muted">Sem notificações.</p>' }).el.querySelectorAll("tr[data-l]").forEach((tr) => (tr.onclick = () => { if (tr.dataset.l) location.hash = "#" + tr.dataset.l; document.getElementById("modal-root").innerHTML = ""; })));
}

function painel() {
  const d = S.d, m = S.me, cs = d.cases;
  const aberto = cs.filter((c) => !["respondido", "encerrado"].includes(c.status));
  const hoje = d.now;
  const agend = cs.filter((c) => c.agendamento && c.agendamento.fim > hoje && !["encerrado"].includes(c.status)).sort((a, b) => a.agendamento.inicio - b.agendamento.inicio);
  const atrasados = aberto.filter((c) => c.prazo && c.prazo < hoje).length;
  const fila = (m.perfil === "especialista" ? aberto.filter((c) => c.especialista === m.id || (!c.especialista && c.especialidade === m.especialidade)) : ["solicitante", "enfermagem"].includes(m.perfil) ? cs.filter((c) => c.solicitante === m.id && c.status !== "encerrado") : aberto).slice(0, 8);
  const respondidos = cs.filter((c) => c.status === "respondido" || c.status === "encerrado").length;
  const porTipo = {};
  cs.forEach((c) => (porTipo[c.tipo] = (porTipo[c.tipo] || 0) + 1));
  const max = Math.max(1, ...Object.values(porTipo));
  const barras = Object.entries(porTipo).map(([k, v]) => `<div style="display:grid;grid-template-columns:130px 1fr 24px;gap:10px;align-items:center;margin-bottom:7px"><span class="small">${TIPO[k]}</span><div style="background:var(--line-soft);height:10px"><div style="width:${(v / max) * 100}%;background:var(--azul);height:100%"></div></div><span class="mono">${v}</span></div>`).join("");
  const exAg = d.exams.filter((e) => e.status === "aguardando").length;
  const frase = m.perfil === "especialista" ? "Fila de solicitações da sua especialidade e próximos teleatendimentos." : ["solicitante", "enfermagem"].includes(m.perfil) ? "Acompanhe suas solicitações e responda pedidos de informação." : "Visão consolidada da operação da rede de telessaúde.";
  return pageHead(`Bom dia, ${esc(m.nome.split(" ")[0])}`, frase, ["solicitante", "enfermagem"].includes(m.perfil) ? `<a class="btn" href="#/novo">${ic.plus} Nova solicitação</a>` : "") +
    `<div class="kpis"><a class="kpi" data-go="abertas"><div class="n">${aberto.length}</div><div class="l">Solicitações abertas</div><div class="d">${cs.length} no total</div></a>
    <a class="kpi" data-go="atrasadas"><div class="n">${atrasados}</div><div class="l">Fora do prazo</div><div class="d">prazo de 48 h</div></a>
    <a class="kpi" data-go="agendadas"><div class="n">${agend.length}</div><div class="l">Teleatendimentos agendados</div><div class="d">${agend[0] ? "próximo " + dsh(agend[0].agendamento.inicio) : "nenhum"}</div></a>
    <a class="kpi" data-go="laudo"><div class="n">${exAg}</div><div class="l">Exames aguardando laudo</div><div class="d">${respondidos} solicitações respondidas</div></a></div>
    <div class="grid g-main"><div class="stack"><div class="panel"><div class="ph"><h3>${m.perfil === "especialista" ? "Fila de trabalho" : "Solicitações em andamento"}</h3><a href="#/casos" class="small">Ver todas</a></div>
      ${tabela(fila)}</div>
      <div class="panel"><div class="ph"><h3>Solicitações por modalidade</h3></div><div class="pb">${barras}</div></div></div>
    <div class="stack"><div class="panel"><div class="ph"><h3>Próximos teleatendimentos</h3></div><div class="pb">${agend.length ? agend.slice(0, 5).map((c) => `<div style="padding:8px 0;border-bottom:1px solid var(--line-soft)"><div class="bar" style="justify-content:space-between"><b class="mono">${dsh(c.agendamento.inicio)}</b><a class="mono small" href="#/casos/${c.id}">${c.protocolo}</a></div><div class="small">${esc(pac(c.paciente).nome)}</div><div class="small muted">${esc(usr(c.solicitante).nome)} ↔ ${esc(usr(c.especialista).nome)}</div><a class="btn sm" style="margin-top:6px" href="#/sala/${c.sala}">${ic.video} Entrar na sala</a></div>`).join("") : '<p class="muted">Nenhum teleatendimento agendado.</p>'}</div></div>
      <div class="panel"><div class="ph"><h3>Atividade recente</h3></div><div class="pb"><ul class="tl">${cs.flatMap((c) => c.timeline.map((t) => ({ ...t, p: c.protocolo, id: c.id }))).sort((a, b) => b.ts - a.ts).slice(0, 6).map((t) => `<li><div class="w">${rel(t.ts)} · <a class="mono" href="#/casos/${t.id}">${t.p}</a></div><div class="small">${esc(t.texto)}</div></li>`).join("")}</ul></div></div></div></div>`;
}

function login() {
  const r = $app();
  const demo = [["medico@telessaude.fepecs", "Médico", "Dr. Henrique Matos · HRAN", "Quem atende o paciente e pede o parecer. Abre solicitações, conversa por texto ou vídeo com o teleconsultor."], ["teleconsultor@telessaude.fepecs", "Teleconsultor", "Dra. Beatriz Nogueira · Cardiologia", "Especialista que responde: chat assíncrono, teleatendimento com o paciente, parecer assinado."], ["gestor@telessaude.fepecs", "Gestor / Administrador", "Marina Duarte · Núcleo de Telessaúde", "Cadastros, agenda, indicadores, auditoria, integrações e suporte."]];
  r.innerHTML = `<div class="login"><div class="left"><div class="logos"><img class="f" src="/img/fepecs.png" alt="FEPECS"><img class="b" src="/img/bazetech.png" alt="BazeTech"></div>
    <div><div class="small" style="letter-spacing:.14em;text-transform:uppercase;color:#9fb7d1">Secretaria de Estado de Saúde do Distrito Federal</div><h1>Telessaúde<br><b>FEPECS</b></h1><p>Teleparecer, teleinterconsulta, teleconsulta e telediagnóstico em uma única plataforma, integrada ao prontuário e com segurança conforme a LGPD.</p></div>
    <div class="modulos">ADMINISTRATIVO · SUPORTE · TELEINTERCONSULTAS · TELECONSULTA · TELECONSULTORIA · TELEREUNIÕES · TELEDIAGNÓSTICO · INTERFACE PEC · ASSINATURA ELETRÔNICA</div></div>
    <div class="right"><div class="box"><h2>Acesso ao sistema</h2><p class="muted" style="margin:0 0 18px">Entre com seu e-mail institucional.</p><div id="lerr"></div>
    <form id="lf" class="f"><div class="fld"><label>E-mail</label><input id="le" type="email" required autocomplete="username"></div><div class="fld"><label>Senha</label><input id="ls" type="password" required autocomplete="current-password"></div><button class="btn" style="justify-content:center;padding:10px">Entrar</button></form>
    <div class="demo"><h4>Entrar como (demonstração · senha: telessaude)</h4>${demo.map((x) => `<button data-e="${x[0]}"><div><b>${x[1]}</b><div class="small muted">${x[2]}</div><div class="small desc">${x[3]}</div></div></button>`).join("")}</div></div></div></div>`;
  const go = async (email, senha) => {
    try {
      const j = await api("/login", { email, senha });
      S.token = j.token; localStorage.setItem("tok", j.token); S.d = null;
      location.hash = "#/painel"; render();
    } catch (e) { r.querySelector("#lerr").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  };
  r.querySelector("#lf").onsubmit = (e) => { e.preventDefault(); go(r.querySelector("#le").value, r.querySelector("#ls").value); };
  r.querySelectorAll(".demo button").forEach((b) => (b.onclick = () => go(b.dataset.e, "telessaude")));
}

S.onPush = async (m) => {
  if (m.t === "state" || m.t === "notify") {
    if (m.t === "notify" && m.para.includes(S.me.id)) toast(m.texto, false, m.link ? m.link.replace(/^\/casos/, "/casos") : null);
    if (location.hash.startsWith("#/sala")) { try { await carregar(); } catch (e) { /* ignora */ } return; }
    const el = document.activeElement;
    const digitando = el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
    try { await carregar(); } catch (e) { return; }
    if (!digitando && !location.hash.startsWith("#/novo") && !document.getElementById("modal-root").innerHTML) render();
  }
};
window.addEventListener("hashchange", render);
setInterval(() => { if (S.d && !document.getElementById("modal-root").innerHTML && !location.hash.match(/#\/(sala|convidado|novo)/)) render(); }, 60000);
render();
