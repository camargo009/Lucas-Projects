import { S, api, carregar } from "./api.js";
import { esc, ic, toast, modal, usr, pac, und, dt, dsh, hm, dia, diaKey, idade, PERFIL, pageHead } from "./ui.js";
import { tabela } from "./v-casos.js";

/* ---------- agenda ---------- */
let agEsp = "";
export function agenda() {
  const esps = S.d.users.filter((u) => u.perfil === "especialista");
  if (!agEsp) agEsp = S.me.perfil === "especialista" ? S.me.id : esps[0].id;
  const sl = S.d.slots.filter((s) => s.especialista === agEsp);
  const agendados = S.d.cases.filter((c) => c.agendamento && c.agendamento.especialista !== null).filter((c) => c.especialista === agEsp && c.agendamento);
  const dias = [...new Set([...sl.map((s) => s.inicio), ...agendados.map((c) => c.agendamento.inicio)].map(diaKey))].sort((a, b) => a.split("/").reverse().join("").localeCompare(b.split("/").reverse().join(""))).slice(0, 5);
  const itens = [...sl.map((s) => ({ ini: s.inicio, s })), ...agendados.filter((c) => !sl.some((s) => s.caso === c.id)).map((c) => ({ ini: c.agendamento.inicio, c }))];
  const horas = [...new Set(itens.map((i) => hm(i.ini)))].sort();
  let g = `<div class="ag" style="grid-template-columns:60px repeat(${dias.length || 1},1fr)"><div class="hd"></div>${dias.map((d) => `<div class="hd">${dia(itens.find((i) => diaKey(i.ini) === d).ini)}</div>`).join("")}`;
  for (const h of horas) {
    g += `<div class="hr">${h}</div>`;
    for (const d of dias) {
      const it = itens.filter((i) => diaKey(i.ini) === d && hm(i.ini) === h);
      g += `<div>${it.map((i) => {
        const c = i.c || (i.s.caso && S.d.cases.find((x) => x.id === i.s.caso));
        return c ? `<a class="slot res" style="display:block;color:inherit" href="#/casos/${c.id}"><b class="mono">${c.protocolo}</b><br>${esc(pac(c.paciente).nome.split(" ")[0])}</a>` : '<div class="slot" style="cursor:default">Livre</div>';
      }).join("")}</div>`;
    }
  }
  g += "</div>";
  return {
    html: pageHead("Agenda de teleatendimentos", "Horários de 30 minutos por especialista. Reservas feitas pelo fluxo do Teleparecer aparecem aqui.", `<select id="ae" style="padding:6px">${esps.map((e) => `<option value="${e.id}" ${e.id === agEsp ? "selected" : ""}>${esc(e.nome)} · ${esc(e.especialidade)}</option>`).join("")}</select>`) + g,
    after: (b) => { b.querySelector("#ae").onchange = (e) => { agEsp = e.target.value; const r = agenda(); b.innerHTML = r.html; r.after(b); }; },
  };
}

/* ---------- telerreuniões ---------- */
export function reunioes() {
  const ms = [...S.d.meetings].sort((a, b) => a.inicio - b.inicio);
  const pode = ["admin", "gestor", "especialista"].includes(S.me.perfil);
  const T = { telegrupo: "Telegrupo", reuniao: "Reunião", teleducacao: "Teleducação" };
  return {
    html: pageHead("Telerreuniões e telegrupos", "Discussão de casos, reuniões de equipe e atividades de teleducação.", pode ? '<button class="btn" id="nm">' + ic.plus + " Nova telerreunião</button>" : "") +
      `<div class="panel"><table class="t"><thead><tr><th>Data e hora</th><th>Título</th><th>Tipo</th><th>Anfitrião</th><th>Participantes</th><th></th></tr></thead><tbody>${ms.map((m) => `<tr><td class="nowrap mono">${dt(m.inicio)}</td><td><b>${esc(m.titulo)}</b><div class="small muted">${esc(m.pauta)}</div></td><td><span class="tag azul">${T[m.tipo] || m.tipo}</span></td><td>${esc(usr(m.anfitriao).nome)}</td><td class="small">${m.participantes.map((p) => esc(usr(p).nome.split(" ")[0])).join(", ")}</td><td class="right"><a class="btn sm" href="#/sala/${m.sala}">${ic.video} Entrar</a></td></tr>`).join("")}</tbody></table></div>`,
    after: (b) => {
      const nm = b.querySelector("#nm");
      if (nm) nm.onclick = () => modal({ titulo: "Nova telerreunião", ok: "Agendar", corpo: `<div class="f"><div class="fld"><label>Título</label><input id="t"></div><div class="f c2"><div class="fld"><label>Tipo</label><select id="tp"><option value="telegrupo">Telegrupo</option><option value="reuniao">Reunião</option><option value="teleducacao">Teleducação</option></select></div><div class="fld"><label>Data e hora</label><input id="dt" type="datetime-local"></div></div><div class="fld"><label>Pauta</label><textarea id="pa" style="min-height:60px"></textarea></div><div class="fld"><label>Convidados</label>${S.d.users.filter((u) => u.id !== S.me.id).map((u) => `<label style="text-transform:none;letter-spacing:0;font-size:13px;font-weight:400"><input type="checkbox" value="${u.id}" style="width:auto"> ${esc(u.nome)} · ${esc(u.cargo)}</label>`).join("")}</div></div>`,
        onOk: async (m) => {
          const t = m.querySelector("#t").value.trim(), d = m.querySelector("#dt").value;
          if (!t || !d) { toast("Informe título e data.", true); return false; }
          await api("/meetings", { titulo: t, tipo: m.querySelector("#tp").value, inicio: new Date(d).getTime(), pauta: m.querySelector("#pa").value, participantes: [...m.querySelectorAll("input[type=checkbox]:checked")].map((x) => x.value) });
          await carregar(); toast("Telerreunião agendada."); location.reload();
        } });
    },
  };
}

/* ---------- telediagnóstico ---------- */
function interpretar(p) {
  const r = p.vef1 / p.cvf, cv = p.cvf / p.cvf_prev, v1 = p.vef1 / p.vef1_prev;
  if (r < 0.7) return `Distúrbio ventilatório obstrutivo de grau ${v1 < 0.35 ? "grave" : v1 < 0.5 ? "moderadamente grave" : v1 < 0.6 ? "moderado" : "leve"} (VEF1/CVF ${(r * 100).toFixed(0)}%, VEF1 ${(v1 * 100).toFixed(0)}% do previsto). Correlacionar com quadro clínico e prova broncodilatadora.`;
  if (cv < 0.8) return `CVF reduzida (${(cv * 100).toFixed(0)}% do previsto) com relação VEF1/CVF preservada: sugere distúrbio restritivo; confirmar com volumes pulmonares.`;
  return "Espirometria dentro dos limites da normalidade.";
}

function curva(canvas, p) {
  const ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height, pad = 38;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "#e4e1d9"; ctx.lineWidth = 1; ctx.font = "11px Segoe UI"; ctx.fillStyle = "#78808a";
  const xmax = Math.max(p.cvf_prev, p.cvf) * 1.1, ymax = 12;
  const X = (v) => pad + (v / xmax) * (W - pad - 12), Y = (f) => H - pad - (f / ymax) * (H - pad - 12);
  for (let f = 0; f <= 12; f += 3) { ctx.beginPath(); ctx.moveTo(pad, Y(f)); ctx.lineTo(W - 12, Y(f)); ctx.stroke(); ctx.fillText(f, 12, Y(f) + 4); }
  for (let v = 0; v <= xmax; v += 1) { ctx.fillText(v, X(v) - 3, H - 20); }
  ctx.fillText("Volume (L)", W / 2 - 22, H - 5); ctx.save(); ctx.translate(10, H / 2 + 30); ctx.rotate(-Math.PI / 2); ctx.fillText("Fluxo (L/s)", 0, 0); ctx.restore();
  const desenhar = (cvf, pef, cor, tracejado) => {
    ctx.strokeStyle = cor; ctx.lineWidth = 2; ctx.setLineDash(tracejado ? [5, 4] : []); ctx.beginPath(); ctx.moveTo(X(0), Y(0));
    const n = 60;
    for (let i = 1; i <= n; i++) { const v = (i / n) * cvf; const x = v / cvf; const f = x < 0.12 ? pef * (x / 0.12) : pef * Math.pow(1 - (x - 0.12) / 0.88, 1.35 + (p.vef1 / p.cvf < 0.7 ? 0.9 : 0)); ctx.lineTo(X(v), Y(f)); }
    ctx.stroke(); ctx.setLineDash([]);
  };
  desenhar(p.cvf_prev, p.pef * 1.15, "#78808a", true);
  desenhar(p.cvf, p.pef, "#0a4a82", false);
  ctx.fillStyle = "#0a4a82"; ctx.fillText("medido", W - 90, 24); ctx.fillStyle = "#78808a"; ctx.fillText("previsto", W - 90, 38);
}

let exFiltro = "";
export function setExFiltro(v) { exFiltro = v; }
window.addEventListener("hashchange", () => { if (!location.hash.startsWith("#/telediagnostico")) exFiltro = ""; });
export function telediagnostico() {
  const pn = S.me.especialidade === "Pneumologia";
  const pode = ["solicitante", "enfermagem", "admin"].includes(S.me.perfil);
  const ex = S.d.exams.filter((e) => !exFiltro || e.status === exFiltro);
  return {
    html: pageHead("Telediagnóstico · Espirometria", "Exames realizados na rede, laudados remotamente por pneumologistas.", pode ? `<button class="btn" id="ne">${ic.plus} Enviar espirometria</button>` : "") +
      `${exFiltro ? '<div class="chipf">Filtro: <b>Aguardando laudo</b> <button id="fx" class="btn sm sec">Limpar filtro ✕</button></div>' : ""}<div class="panel"><table class="t"><thead><tr><th>Exame</th><th>Paciente</th><th>Unidade de coleta</th><th>CVF</th><th>VEF1</th><th>VEF1/CVF</th><th>Situação</th></tr></thead><tbody>${ex.map((e) => `<tr class="row" data-e="${e.id}"><td class="mono">${e.id}<div class="small muted">${dsh(e.solicitado)}</div></td><td>${esc(pac(e.paciente).nome)}</td><td>${esc(und(e.coleta).nome.replace(/\s*\(.*\)/, ""))}</td><td class="mono">${e.params.cvf.toFixed(2)} L</td><td class="mono">${e.params.vef1.toFixed(2)} L</td><td class="mono">${((e.params.vef1 / e.params.cvf) * 100).toFixed(0)}%</td><td><span class="st ${e.status === "laudado" ? "laudado" : "aguardando"}">${e.status === "laudado" ? "Laudado" : "Aguardando laudo"}</span></td></tr>`).join("")}</tbody></table></div>`,
    after: (b) => {
      const fx = b.querySelector("#fx");
      if (fx) fx.onclick = () => { exFiltro = ""; location.reload(); };
      b.querySelectorAll("tr[data-e]").forEach((tr) => (tr.onclick = () => abrirExame(ex.find((x) => x.id === tr.dataset.e), pn)));
      const ne = b.querySelector("#ne");
      if (ne) ne.onclick = () => modal({ titulo: "Enviar espirometria para laudo", ok: "Enviar", corpo: `<div class="f c2"><div class="fld span2"><label>Paciente</label><select id="p">${S.d.patients.map((p) => `<option value="${p.id}">${esc(p.nome)}</option>`).join("")}</select></div>
        <div class="fld"><label>CVF medida (L)</label><input id="cvf" type="number" step="0.01" value="3.40"></div><div class="fld"><label>VEF1 medido (L)</label><input id="vef1" type="number" step="0.01" value="2.30"></div><div class="fld"><label>PEF (L/s)</label><input id="pef" type="number" step="0.1" value="6.2"></div><div class="fld"><label>Arquivo do exame (PDF)</label><input type="file"></div></div>`,
        onOk: async (m) => { const v = (i) => parseFloat(m.querySelector(i).value); const cvf = v("#cvf"), vef1 = v("#vef1"); await api("/exams", { paciente: m.querySelector("#p").value, params: { cvf, vef1, pef: v("#pef"), cvf_prev: +(cvf * 1.12).toFixed(2), vef1_prev: +(vef1 * 1.25).toFixed(2) } }); await carregar(); toast("Exame enviado para laudo."); location.reload(); } });
    },
  };
}

function abrirExame(e, pn) {
  const p = e.params, pc = pac(e.paciente);
  const pode = pn && e.status !== "laudado";
  const mm = modal({ titulo: `Espirometria ${e.id} · ${pc.nome}`, lg: true, semRodape: !pode, ok: "Laudar e assinar", cancel: "Fechar",
    corpo: `<div class="grid g2"><div><canvas id="cv" width="360" height="280" style="border:1px solid var(--line);width:100%"></canvas></div><div><table class="t"><thead><tr><th>Parâmetro</th><th>Medido</th><th>Previsto</th><th>%</th></tr></thead><tbody>
      <tr><td>CVF (L)</td><td class="mono">${p.cvf}</td><td class="mono">${p.cvf_prev}</td><td class="mono">${((p.cvf / p.cvf_prev) * 100).toFixed(0)}%</td></tr><tr><td>VEF1 (L)</td><td class="mono">${p.vef1}</td><td class="mono">${p.vef1_prev}</td><td class="mono">${((p.vef1 / p.vef1_prev) * 100).toFixed(0)}%</td></tr>
      <tr><td>VEF1/CVF</td><td class="mono">${((p.vef1 / p.cvf) * 100).toFixed(0)}%</td><td class="mono">≥ 70%</td><td></td></tr><tr><td>PEF (L/s)</td><td class="mono">${p.pef}</td><td></td><td></td></tr></tbody></table>
      <div class="fld" style="margin-top:12px"><label>Laudo</label>${e.status === "laudado" ? `<div class="txtblk">${esc(e.laudo)}</div><p class="small muted">${esc(usr(e.laudista).nome)}${e.assinatura ? ` · <span class="tag verde">assinado</span> · <a href="#/documento/${e.id}">abrir documento</a>` : ""}</p>` : pode ? `<textarea id="lt" style="min-height:130px">${esc(interpretar(p))}</textarea><div class="hint">Sugestão automática a partir dos parâmetros. Revise antes de assinar.</div>` : '<p class="muted">Aguardando laudo do pneumologista.</p>'}</div></div></div>`,
    onOk: async (m) => { await api(`/exams/${e.id}/laudo`, { texto: m.querySelector("#lt").value }); await carregar(); toast("Laudo emitido e assinado."); location.reload(); } });
  curva(mm.el.querySelector("#cv"), p);
}

/* ---------- suporte ---------- */
const STT = { aberto: "Aberto", em_atendimento: "Em atendimento", resolvido: "Resolvido" };
export function suporte() {
  const ts = S.d.tickets;
  return {
    html: pageHead("Suporte", "Chamados técnicos e dúvidas de uso.", `<button class="btn" id="nt">${ic.plus} Abrir chamado</button>`) +
      `<div class="panel"><table class="t"><thead><tr><th>Chamado</th><th>Categoria</th><th>Autor</th><th>Prioridade</th><th>Situação</th><th>Aberto</th></tr></thead><tbody>${ts.map((t) => `<tr class="row" data-t="${t.id}"><td><b>${esc(t.titulo)}</b><div class="small muted">${t.respostas.length} mensagem(ns)</div></td><td>${esc(t.categoria)}</td><td>${esc(usr(t.autor).nome)}</td><td>${t.prioridade}</td><td><span class="st ${t.status === "resolvido" ? "respondido" : t.status === "em_atendimento" ? "em_analise" : "aguardando"}">${STT[t.status]}</span></td><td class="small nowrap">${dsh(t.criado)}</td></tr>`).join("")}</tbody></table></div>`,
    after: (b) => {
      b.querySelector("#nt").onclick = () => modal({ titulo: "Abrir chamado", ok: "Enviar", corpo: `<div class="f"><div class="fld"><label>Assunto</label><input id="t"></div><div class="f c2"><div class="fld"><label>Categoria</label><select id="c"><option>Acesso</option><option>Anexos</option><option>Vídeo e áudio</option><option>Assinatura</option><option>Outros</option></select></div><div class="fld"><label>Prioridade</label><select id="p"><option>Baixa</option><option selected>Média</option><option>Alta</option></select></div></div><div class="fld"><label>Descrição</label><textarea id="d"></textarea></div></div>`, onOk: async (m) => { const t = m.querySelector("#t").value.trim(); if (!t) { toast("Informe o assunto.", true); return false; } await api("/tickets", { titulo: t, categoria: m.querySelector("#c").value, prioridade: m.querySelector("#p").value, descricao: m.querySelector("#d").value }); await carregar(); toast("Chamado aberto."); location.reload(); } });
      b.querySelectorAll("tr[data-t]").forEach((tr) => (tr.onclick = () => {
        const t = ts.find((x) => x.id === tr.dataset.t), sup = S.me.perfil === "suporte" || S.me.perfil === "admin";
        modal({ titulo: t.titulo, lg: true, ok: "Enviar resposta", cancel: "Fechar", corpo: `${t.respostas.map((r) => `<div style="border-left:3px solid var(--azul);padding:2px 10px;margin-bottom:10px"><b>${esc(usr(r.autor).nome)}</b> <span class="small muted">${dt(r.ts)}</span><div class="txtblk">${esc(r.texto)}</div></div>`).join("") || '<p class="muted">Sem mensagens.</p>'}<div class="f c2" style="margin-top:12px"><div class="fld span2"><label>Resposta</label><textarea id="r" style="min-height:70px"></textarea></div>${sup ? `<div class="fld"><label>Situação</label><select id="s">${Object.entries(STT).map(([k, v]) => `<option value="${k}" ${t.status === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>` : ""}</div>`,
          onOk: async (m) => { await api(`/tickets/${t.id}/reply`, { texto: m.querySelector("#r").value.trim(), status: m.querySelector("#s") ? m.querySelector("#s").value : undefined }); await carregar(); location.reload(); } });
      }));
    },
  };
}

/* ---------- administração ---------- */
export function admin() {
  const u = S.me, adm = u.perfil === "admin";
  const aud = S.d.audit;
  return {
    html: pageHead("Administração", "Unidades, usuários e trilha de auditoria (LGPD).", adm ? '<button class="btn sec" id="rs">Restaurar dados de demonstração</button>' : "") +
      `<div class="stack"><div class="panel"><div class="ph"><h3>Unidades</h3></div><table class="t"><thead><tr><th>Unidade</th><th>Tipo</th><th>Região</th><th>CNES</th></tr></thead><tbody>${S.d.units.map((x) => `<tr><td>${esc(x.nome)}</td><td>${x.tipo}</td><td>${x.regiao}</td><td class="mono">${x.cnes}</td></tr>`).join("")}</tbody></table></div>
      <div class="panel"><div class="ph"><h3>Usuários e perfis</h3>${adm ? '<button class="btn sm" id="nu">Novo usuário</button>' : ""}</div><table class="t"><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Unidade</th></tr></thead><tbody>${S.d.users.map((x) => `<tr><td>${esc(x.nome)}<div class="small muted">${esc(x.cargo)}</div></td><td class="mono">${esc(x.email)}</td><td>${PERFIL[x.perfil]}</td><td>${esc(und(x.unidade).nome)}</td></tr>`).join("")}</tbody></table></div>
      ${aud.length ? `<div class="panel"><div class="ph"><h3>Trilha de auditoria</h3></div><table class="t"><thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Alvo</th><th>IP</th></tr></thead><tbody>${aud.slice(0, 40).map((a) => `<tr><td class="mono nowrap">${dt(a.ts)}</td><td>${a.user === "-" ? "—" : esc(usr(a.user).nome)}</td><td>${esc(a.acao)}</td><td class="mono">${esc(a.alvo)}</td><td class="mono">${esc(a.ip)}</td></tr>`).join("")}</tbody></table></div>` : ""}</div>`,
    after: (b) => {
      const rs = b.querySelector("#rs");
      if (rs) rs.onclick = () => modal({ titulo: "Restaurar demonstração", ok: "Restaurar", corpo: "<p>Todos os dados voltam ao estado inicial. Use antes da apresentação.</p>", onOk: async () => { await api("/reset", {}); await carregar(); toast("Dados restaurados."); location.reload(); } });
      const nu = b.querySelector("#nu");
      if (nu) nu.onclick = () => modal({ titulo: "Novo usuário", ok: "Criar", corpo: `<div class="f c2"><div class="fld"><label>Nome</label><input id="n"></div><div class="fld"><label>E-mail</label><input id="e"></div><div class="fld"><label>Perfil</label><select id="p">${Object.entries(PERFIL).filter(([k]) => k !== "paciente").map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div><div class="fld"><label>Unidade</label><select id="u">${S.d.units.map((x) => `<option value="${x.id}">${esc(x.nome)}</option>`).join("")}</select></div></div>`, onOk: async (m) => { await api("/users", { nome: m.querySelector("#n").value, email: m.querySelector("#e").value, perfil: m.querySelector("#p").value, unidade: m.querySelector("#u").value }); await carregar(); toast("Usuário criado."); location.reload(); } });
    },
  };
}

/* ---------- integrações ---------- */
export function integracoes() {
  const cs = S.d.cases.filter((c) => c.resposta);
  const docs = [...cs.filter((c) => c.resposta.assinatura).map((c) => ({ n: "Parecer " + c.protocolo, a: c.resposta.assinatura, id: c.id })), ...S.d.exams.filter((e) => e.assinatura).map((e) => ({ n: "Laudo " + e.id, a: e.assinatura, id: e.id }))];
  return {
    html: pageHead("Integrações", "Interface com o PEC e-SUS APS e assinatura eletrônica de documentos.") +
      `<div class="grid g2"><div class="panel"><div class="ph"><h3>PEC e-SUS APS</h3><span class="tag verde">homologação · simulada</span></div><table class="t"><thead><tr><th>Protocolo</th><th>Evolução</th></tr></thead><tbody>${cs.map((c) => `<tr><td class="mono"><a href="#/casos/${c.id}">${c.protocolo}</a></td><td>${c.pec ? `<span class="st respondido">Enviado ${dsh(c.pec.ts)}</span> <span class="mono small muted">${c.pec.id}</span>` : '<span class="st aguardando">Pendente</span>'}</td></tr>`).join("") || '<tr><td colspan="2" class="muted">Sem pareceres emitidos.</td></tr>'}</tbody></table></div>
      <div class="panel"><div class="ph"><h3>Assinatura eletrônica</h3><span class="tag verde">ICP-Brasil · simulada</span></div><table class="t"><thead><tr><th>Documento</th><th>Hash</th><th></th></tr></thead><tbody>${docs.map((d) => `<tr><td>${d.n}<div class="small muted">${esc(usr(d.a.por).nome)} · ${dsh(d.a.ts)}</div></td><td class="mono small">${d.a.hash.slice(0, 14)}…</td><td><a class="small" href="#/verificar/${d.a.hash}">verificar</a></td></tr>`).join("") || '<tr><td colspan="3" class="muted">Nenhum documento assinado.</td></tr>'}</tbody></table></div></div>
      <div class="panel" style="margin-top:16px"><div class="ph"><h3>Bases tecnológicas</h3></div><div class="pb small">Teleconsultoria e teleparecer sobre a base <b>Lyah</b>; telemonitoramento sobre a base <b>MyHeart</b>. Os conectores são representados nesta demonstração e serão implementados na fase 1 do projeto.</div></div>`,
    after: () => {},
  };
}

/* ---------- fluxo ---------- */
export function fluxo() {
  const P = [["1", "Passo 1: paciente em ambiente hospitalar precisa de parecer."], ["2", "Passos 2 e 3: se precisa ser presencial, o parecer é convencional pelo prontuário. Caso contrário, passo 4: solicitar teleparecer pelo sistema."], ["3", "Passo 5: se pode ser assíncrono, passos 9 e 10: o teleconsultor preenche anamnese e exame clínico e o médico especialista analisa em até 48 h."], ["4", "Passo 6: se o paciente pode ir à sala de teleparecer, passos 7 e 8: o teleconsultor agenda e o médico especialista atende o paciente no dia e hora marcados, com apoio da enfermagem. Se não, segue para o passo 11."], ["5", "Passo 11: a dúvida foi respondida no primeiro acesso? Sim: passo 12, teleparecer resolvido e evoluído no prontuário."], ["6", "Passo 13 (não resolvida): 1) solicitar mais informações; 2) marcar teleatendimento síncrono com o paciente; 3) seguir fluxo hospitalar; 4) evoluir teleparecer no prontuário."], ["7", "Encerrar o pedido no sistema."]];
  return pageHead("Fluxo 1: Teleparecer", "Referência do processo implementado no sistema.") +
    `<div class="grid g-main"><div class="panel"><div class="pb"><img src="/img/fluxo1-teleparecer.jpg" alt="Fluxograma do Teleparecer" style="width:100%"></div></div><div class="panel"><div class="ph"><h3>Como o sistema aplica o fluxo</h3></div><div class="pb"><ol style="padding-left:18px;margin:0">${P.map((x) => `<li style="margin-bottom:9px">${x[1]}</li>`).join("")}</ol></div></div></div>`;
}

/* ---------- verificação pública de assinatura ---------- */
export async function verificar(hash, root) {
  root.innerHTML = `<div class="lobby"><div class="bar"><img src="/img/fepecs.png" width="46" height="46" alt=""><h2>Verificação de documento</h2></div><div id="r" class="muted" style="margin-top:14px">Consultando…</div></div>`;
  const j = await fetch("/api/verify/" + encodeURIComponent(hash || "")).then((r) => r.json());
  root.querySelector("#r").innerHTML = j.valido
    ? `<div style="border-left:4px solid var(--verde);padding:6px 12px;color:var(--ink)"><b style="color:var(--verde)">Assinatura válida</b><dl class="dl" style="margin-top:10px"><dt>Documento</dt><dd>${esc(j.documento)}</dd><dt>Assinado por</dt><dd>${esc(j.por)} ${esc(j.crm)}</dd><dt>Data</dt><dd>${dt(j.ts)}</dd><dt>Tipo</dt><dd>${esc(j.tipo)}</dd></dl></div>`
    : '<div class="err">Código não encontrado. O documento pode ter sido alterado ou o código está incorreto.</div>';
}
