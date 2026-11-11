import { S, api, carregar } from "./api.js";
import { esc, ic, toast, modal, usr, pac, und, caso, dt, dsh, hm, dia, diaKey, idade, rel, sha256, PERFIL, TIPO, STATUS, stHtml, priTag, priCls, slaHtml, pageHead } from "./ui.js";
import { copilotoHtml, rascunho, analisar } from "./copilot.js";

export function tabela(lista) {
  if (!lista.length) return '<div class="pb muted">Nada por aqui.</div>';
  return `<table class="t"><thead><tr><th>Protocolo</th><th>Paciente</th><th>Modalidade</th><th>Especialidade</th><th>Situação</th><th>Prazo</th></tr></thead><tbody>${lista.map((c) => `<tr class="row ${priCls(c.prioridade)}" onclick="location.hash='#/casos/${c.id}'"><td><span class="mono">${c.protocolo}</span><div>${priTag(c.prioridade)}</div></td><td>${esc(pac(c.paciente).nome)}<div class="small muted">${esc(und(c.unidade).nome.replace(/\s*\(.*\)/, ""))}</div></td><td>${TIPO[c.tipo]}</td><td>${esc(c.especialidade)}</td><td>${stHtml(c.status)}</td><td>${slaHtml(c)}</td></tr>`).join("")}</tbody></table>`;
}

let filtro = { q: "", tipo: "", st: "", k: "" };
export function setFiltro(f) { filtro = { q: "", tipo: "", st: "", k: "", ...f }; }
window.addEventListener("hashchange", () => { if (!location.hash.startsWith("#/casos")) filtro.k = ""; });
const KFILTROS = {
  abertas: ["Solicitações abertas", (c) => !["respondido", "encerrado"].includes(c.status)],
  atrasadas: ["Fora do prazo", (c) => !["respondido", "encerrado"].includes(c.status) && c.prazo && c.prazo < S.d.now],
  agendadas: ["Teleatendimentos agendados", (c) => c.agendamento && c.agendamento.fim > S.d.now && c.status !== "encerrado"],
  respondidas: ["Solicitações respondidas", (c) => ["respondido", "encerrado"].includes(c.status)],
};
export function lista(_, box) {
  const m = S.me;
  let cs = S.d.cases;
  if (["solicitante", "enfermagem"].includes(m.perfil)) cs = cs.filter((c) => c.solicitante === m.id || c.unidade === m.unidade);
  if (m.perfil === "especialista") cs = cs.filter((c) => c.especialista === m.id || c.especialidade === m.especialidade);
  const f = filtro;
  const kf = KFILTROS[f.k];
  const vis = cs.filter((c) => (!kf || kf[1](c)) && (!f.tipo || c.tipo === f.tipo) && (!f.st || c.status === f.st) && (!f.q || (c.protocolo + pac(c.paciente).nome + c.queixa).toLowerCase().includes(f.q.toLowerCase())));
  return {
    html: pageHead("Solicitações", "Teleparecer, teleinterconsulta, teleconsulta, teletriagem e demais modalidades.", ["solicitante", "enfermagem"].includes(m.perfil) ? `<a class="btn" href="#/novo">${ic.plus} Nova solicitação</a>` : "") +
      (kf ? `<div class="chipf">Filtro: <b>${kf[0]}</b> <button id="fk" class="btn sm sec">Limpar filtro ✕</button></div>` : "") + `<div class="panel"><div class="ph"><div class="bar"><input id="fq" placeholder="Buscar protocolo, paciente ou queixa" value="${esc(f.q)}" style="padding:5px 8px;border:1px solid #b5b0a4;width:280px">
      <select id="ft" style="padding:5px;border:1px solid #b5b0a4"><option value="">Todas as modalidades</option>${Object.entries(TIPO).map(([k, v]) => `<option value="${k}" ${f.tipo === k ? "selected" : ""}>${v}</option>`).join("")}</select>
      <select id="fs" style="padding:5px;border:1px solid #b5b0a4"><option value="">Todas as situações</option>${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${f.st === k ? "selected" : ""}>${v}</option>`).join("")}</select></div><span class="small muted">${vis.length} registro(s)</span></div>${tabela(vis)}</div>`,
    after: (b) => {
      const up = () => { filtro = { q: b.querySelector("#fq").value, tipo: b.querySelector("#ft").value, st: b.querySelector("#fs").value, k: filtro.k }; };
      const fk = b.querySelector("#fk");
      if (fk) fk.onclick = () => { filtro.k = ""; const r = lista(); b.innerHTML = r.html; r.after(b); };
      b.querySelector("#fq").oninput = (e) => { up(); clearTimeout(lista.t); lista.t = setTimeout(() => { const pos = e.target.selectionStart; const r = lista(); b.innerHTML = r.html; r.after(b); const i = b.querySelector("#fq"); i.focus(); i.setSelectionRange(pos, pos); }, 250); };
      b.querySelector("#ft").onchange = b.querySelector("#fs").onchange = () => { up(); const r = lista(); b.innerHTML = r.html; r.after(b); };
    },
  };
}

/* ---------- grade de horários ---------- */
export function slotGrid(slots, sel) {
  const dias = [...new Set(slots.map((s) => diaKey(s.inicio)))].sort((a, b) => a.split("/").reverse().join("").localeCompare(b.split("/").reverse().join(""))).slice(0, 5);
  if (!dias.length) return '<p class="muted">Nenhum horário livre.</p>';
  const horas = [...new Set(slots.map((s) => hm(s.inicio)))].sort();
  let h = `<div class="ag" style="grid-template-columns:60px repeat(${dias.length},1fr)"><div class="hd"></div>${dias.map((d) => `<div class="hd">${dia(slots.find((s) => diaKey(s.inicio) === d).inicio)}</div>`).join("")}`;
  for (const hr of horas) {
    h += `<div class="hr">${hr}</div>`;
    for (const d of dias) {
      const ss = slots.filter((s) => diaKey(s.inicio) === d && hm(s.inicio) === hr);
      h += `<div>${ss.map((s) => `<div class="slot ${sel === s.id ? "sel" : ""}" data-slot="${s.id}">${esc(usr(s.especialista).nome.split(" ")[0])}</div>`).join("")}</div>`;
    }
  }
  return h + "</div>";
}
/* ---------- detalhe do caso ---------- */
export function baseUrl() { return localStorage.getItem("baseUrl") || location.origin; }

function fhir(c) {
  const p = pac(c.paciente), e = usr(c.especialista || c.solicitante);
  return {
    resourceType: "Bundle", type: "transaction", id: c.pec ? c.pec.id.replace("Bundle/", "") : "pendente",
    entry: [
      { resource: { resourceType: "Patient", identifier: [{ system: "http://rnds.saude.gov.br/fhir/r4/NamingSystem/cns", value: p.cns }], name: [{ text: p.nome }], birthDate: p.nasc, gender: p.sexo === "F" ? "female" : "male" } },
      { resource: { resourceType: "Practitioner", name: [{ text: e.nome }], identifier: [{ system: "CRM", value: e.crm || "" }] } },
      { resource: { resourceType: "Composition", status: "final", type: { text: "Teleparecer" }, title: "Teleparecer " + c.protocolo, section: [{ title: "Parecer", text: { status: "generated", div: (c.resposta && c.resposta.texto) || "" } }] } },
      ...(c.resposta && c.resposta.assinatura ? [{ resource: { resourceType: "Provenance", signature: [{ type: [{ code: "1.2.840.10065.1.12.1.1" }], when: new Date(c.resposta.assinatura.ts).toISOString(), data: c.resposta.assinatura.hash }] } }] : []),
    ],
  };
}

function fluxoHtml(c, m) {
  const esp = m.perfil === "especialista", sol = m.perfil === "solicitante";
  const card = (n, t, p, bt = "") => `<div class="decisao" style="margin-bottom:16px"><div class="n">${n}</div><div class="q">${t}</div><p style="margin:0 0 10px;color:var(--ink-2)">${p}</p>${bt}</div>`;
  const sala = c.modo === "sala_teleparecer";
  if (c.status === "aguardando") return esp
    ? card("PASSO 10 DO FLUXOGRAMA", "Analise a solicitação enviada", "Você tem carga horária reservada para teleparecer. O prazo de resposta é de 48 horas.", `<button class="btn" data-a="assumir">Analisar solicitação</button>`)
    : card("PASSO 10 DO FLUXOGRAMA", "Aguardando o teleconsultor", "O profissional requisitado analisa a solicitação enviada em até 48 horas.");
  if (c.status === "em_analise") return esp
    ? card("PASSO 11 DO FLUXOGRAMA", "A dúvida pode ser respondida neste primeiro acesso?", "Sim: passo 12, emita o parecer e encerre o pedido. Não: passo 13, responda no Sistema de Telessaúde marcando uma das opções.", `<button class="btn ok" data-a="p11sim">Sim, emitir parecer (passo 12)</button><div class="small muted" style="margin:14px 0 6px"><b>Não: passo 13, marque uma das opções</b></div>${[["info", "1", "Solicito mais informações (descreva as informações necessárias)"], ["sync", "2", "Favor marcar teleatendimento síncrono com a presença do paciente (horário disponível)"], ["hospitalar", "3", "Favor seguir fluxo hospitalar (já estabelecido)"], ["evoluir", "4", "Evoluir teleparecer no prontuário"]].map((o) => `<div class="opt" data-a="p13_${o[0]}"><b>${o[1]}</b><div>${o[2]}</div></div>`).join("")}`)
    : card("PASSO 11 DO FLUXOGRAMA", "Em análise pelo teleconsultor", "O teleconsultor decide se a dúvida é respondida agora ou se pede mais informações, teleatendimento ou outro encaminhamento.");
  if (c.status === "info_solicitada") return sol
    ? card("PASSO 13 · OPÇÃO 1", "Anexe as informações solicitadas", `Teleconsultor pediu: ${esc(c.info_pedida || "")}`, `<button class="btn" data-a="enviar">Anexar e informar</button>`)
    : card("PASSO 13 · OPÇÃO 1", "Aguardando o médico solicitante", "O médico deve anexar no sistema as informações solicitadas.");
  if (c.status === "teleatendimento_agendado") {
    const t = sala
      ? "Passo 8: no dia e hora marcados, o teleconsultor acessa o sistema e abre o link do teleatendimento. A equipe de enfermagem desloca o paciente até a sala de teleparecer e acessa o sistema. O teleatendimento é feito sem a presença do médico solicitante."
      : "Passo 13, opção 2: teleatendimento síncrono com a presença do paciente, no horário marcado. Médico solicitante, paciente e teleconsultor entram na mesma sala.";
    return card(sala ? "PASSOS 7 E 8 DO FLUXOGRAMA" : "PASSO 13 · OPÇÃO 2", "Teleatendimento marcado", t);
  }
  if (c.status === "em_atendimento") return esp
    ? card("PASSO 13 DO FLUXOGRAMA", "Teleatendimento em andamento", "Ao terminar, registre o desfecho no sistema marcando uma das opções.", `<button class="btn" data-a="p13">Registrar desfecho (passo 13)</button>`)
    : card("TELEATENDIMENTO", "Em andamento", sala ? "Atendimento na sala de teleparecer, com o paciente e a equipe de enfermagem, sem o médico solicitante. Use a Troca de informações abaixo para enviar dados ao teleconsultor durante o atendimento." : "Entre na sala para participar e use a Troca de informações abaixo para enviar dados ao teleconsultor.");
  if (c.status === "respondido") return card("PASSO 12 DO FLUXOGRAMA", "Resposta registrada: encerre o pedido", "O teleconsultor assina o documento, a evolução segue para o prontuário (PEC e-SUS) e o pedido é encerrado no sistema de Telessaúde.");
  return "";
}

function msgsHtml(c, m) {
  const ms = c.mensagens || [];
  const podeEnviar = ["solicitante", "especialista"].includes(m.perfil) && c.status !== "encerrado";
  const lista = ms.length ? ms.map((x) => { const eu = x.autor === m.id; const u = usr(x.autor); return `<div class="trm ${eu ? "eu" : ""}"><div class="small muted"><b>${esc(u.nome)}</b> · ${u.perfil === "especialista" ? "Teleconsultor" : "Médico"} · ${dt(x.ts)}</div><div class="txtblk">${esc(x.texto)}</div>${(x.anexos || []).length ? `<div class="small">Anexos: ${x.anexos.map((a) => esc(a.nome)).join(", ")}</div>` : ""}</div>`; }).join("") : `<p class="muted small" style="margin:0">Nenhuma mensagem ainda. Médico e teleconsultor trocam informações e anexos por aqui.</p>`;
  const nota = c.status === "info_solicitada" && m.perfil === "solicitante" ? `<div class="err" style="margin:0 0 10px">O teleconsultor aguarda sua resposta abaixo.</div>` : "";
  const form = podeEnviar ? `${nota}<div class="fld" style="margin-top:12px"><label>${m.perfil === "solicitante" ? "Responder ou enviar informação ao teleconsultor" : "Enviar mensagem ao médico solicitante"}</label><textarea id="mt" placeholder="Escreva aqui…"></textarea></div><div class="bar" style="margin-top:8px"><input id="mf" type="file" multiple><button class="btn" id="ms">Enviar</button></div>` : "";
  return `<div class="panel"><div class="ph"><h3>Troca de informações</h3><span class="tag azul">médico ⇄ teleconsultor</span></div><div class="pb"><div class="trlist">${lista}</div>${form}</div></div>`;
}

export function detalhe(id, box) {
  const c = caso(id);
  if (!c) return pageHead("Solicitação não encontrada");
  const m = S.me, p = pac(c.paciente);
  const esp = m.perfil === "especialista" || m.perfil === "admin";
  const sol = c.solicitante === m.id || ["solicitante", "enfermagem"].includes(m.perfil);
  const aberto = !["respondido", "encerrado"].includes(c.status);
  const ag = c.agendamento;
  const url = baseUrl() + "/#/convidado/" + c.sala;
  const acoes = [];
  const medicoNaSala = c.modo !== "sala_teleparecer";
  if (["teleatendimento_agendado", "em_atendimento"].includes(c.status) && (m.perfil === "especialista" || (sol && medicoNaSala))) acoes.push(`<button class="btn ok" data-a="entrar">${ic.video} ${m.perfil === "especialista" && c.status !== "em_atendimento" ? "Iniciar teleatendimento" : "Entrar na sala"}</button>`);
  if (c.resposta && !c.resposta.assinatura && m.perfil === "especialista") acoes.push(`<button class="btn" data-a="assinar">${ic.shield} Assinar eletronicamente</button>`);
  if (c.resposta) acoes.push(`<a class="btn sec" href="#/documento/${c.id}">${ic.print} Documento</a>`, `<button class="btn sec" data-a="pec">Enviar ao PEC e-SUS</button>`);
  if (c.status === "respondido" && (m.perfil === "especialista" || sol)) acoes.push(`<button class="btn sec" data-a="encerrar">Encerrar pedido</button>`);
  const r = c.resposta;
  const OP = { resolvido: "Teleparecer resolvido e evoluído no prontuário eletrônico", hospitalar: "Seguir o fluxo hospitalar já estabelecido", evoluir: "Evoluir teleparecer no prontuário" };
  const html = pageHead(`<span class="mono" style="font-size:19px">${c.protocolo}</span> Teleparecer`, `${stHtml(c.status)} &nbsp; ${priTag(c.prioridade)} &nbsp; <a href="#/casos" class="small">Voltar à lista</a>`, acoes.join("")) +
    `<div class="grid g-main"><div class="stack">
    ${fluxoHtml(c, m)}
    <div class="panel"><div class="ph"><h3>Paciente e solicitação</h3></div><div class="pb"><dl class="dl">
      <dt>Paciente</dt><dd><b>${esc(p.nome)}</b> · ${idade(p.nasc)} anos · ${p.sexo === "F" ? "F" : "M"} · ${esc(c.situacao || "Internado")}</dd><dt>CNS</dt><dd class="mono">${esc(p.cns)}</dd><dt>Local</dt><dd>${esc(p.local)} · ${esc(und(c.unidade).nome)}</dd>
      ${c.modo ? `<dt>Teleatendimento</dt><dd>${c.modo === "sala_teleparecer" ? "Sala de teleparecer, sem o médico solicitante; enfermagem acompanha o paciente" : "Síncrono, com o paciente e o médico solicitante"}</dd>` : ""}
      <dt>Médico solicitante</dt><dd>${esc(usr(c.solicitante).nome)} <span class="muted">· ${esc(usr(c.solicitante).cargo || "")}</span></dd><dt>Teleconsultor</dt><dd>${c.especialista ? `${esc(usr(c.especialista).nome)} <span class="muted">· ${esc(c.especialidade)}</span>` : `<span class="muted">Aguardando um teleconsultor de ${esc(c.especialidade)}</span>`}</dd>
      <dt>Seu papel</dt><dd><span class="tag azul">${m.perfil === "solicitante" ? "Você é o médico solicitante" : m.perfil === "especialista" ? "Você é o teleconsultor" : "Gestão"}</span></dd>
      <dt>Prazo</dt><dd>${slaHtml(c)}</dd>${ag ? `<dt>Teleatendimento</dt><dd><b>${dt(ag.inicio)}</b></dd>` : ""}</dl></div></div>
    <div class="panel"><div class="ph"><h3>Dados clínicos</h3></div><div class="pb"><dl class="dl"><dt>Queixa</dt><dd>${esc(c.queixa)}</dd><dt>Anamnese</dt><dd class="txtblk">${esc(c.anamnese)}</dd><dt>Exame clínico</dt><dd class="txtblk">${esc(c.exame_clinico)}</dd><dt>Hipótese</dt><dd>${esc(c.hipotese)}</dd><dt>Dúvida</dt><dd class="txtblk">${esc(c.duvida)}</dd>${c.anexos.length ? `<dt>Anexos</dt><dd>${c.anexos.map((a) => esc(a.nome)).join(", ")}</dd>` : ""}</dl>
      ${c.info_pedida && c.status === "info_solicitada" ? `<div class="err" style="margin:12px 0 0"><b>Informação solicitada pelo especialista:</b> ${esc(c.info_pedida)}</div>` : ""}</div></div>
    ${msgsHtml(c, m)}
    ${r ? `<div class="panel" style="border-left:4px solid var(--verde)"><div class="ph"><h3>Parecer do teleconsultor</h3><span class="tag verde">${esc(OP[r.opcao] || r.opcao)}</span></div><div class="pb"><div class="txtblk">${esc(r.texto)}</div><p class="small muted" style="margin-bottom:0">${esc(usr(r.por).nome)} · ${dt(r.ts)}${r.assinatura ? ` · <span class="tag verde">assinado</span> <span class="mono">${r.assinatura.hash.slice(0, 16)}…</span>` : ' · <span class="tag ambar">aguardando assinatura</span>'}</p></div></div>` : ""}
    ${c.transcricao.length ? `<div class="panel"><div class="ph"><h3>Transcrição do teleatendimento</h3></div><div class="pb small">${c.transcricao.map((l) => `<div><b>${esc(l.autor)}:</b> ${esc(l.texto)}</div>`).join("")}</div></div>` : ""}
    </div><div class="stack">
    ${esp ? copilotoHtml(c) : ""}
    <div class="panel"><div class="ph"><h3>Sala de teleatendimento</h3></div><div class="pb small">
      <p style="margin-top:0">Link para o paciente entrar sem cadastro:</p><input readonly id="lk" value="${esc(url)}" style="width:100%;padding:6px;border:1px solid #b5b0a4;font-family:var(--mono);font-size:11.5px">
      <div class="bar" style="margin-top:8px;align-items:flex-start"><img src="/api/qr?text=${encodeURIComponent(url)}" width="110" height="110" alt="QR"><div class="muted">Aponte a câmera do celular para o QR. Para acesso fora desta máquina, defina a URL pública.<br><a href="#" id="setbase">Definir URL pública</a></div></div></div></div>
    <div class="panel"><div class="ph"><h3>Histórico</h3></div><div class="pb"><ul class="tl">${[...c.timeline].reverse().map((t) => `<li><div class="w">${dt(t.ts)} · ${esc(usr(t.autor).nome)}</div><div class="small">${esc(t.texto)}</div></li>`).join("")}</ul></div></div>
    ${c.pec ? `<div class="panel"><div class="ph"><h3>Interface PEC e-SUS</h3></div><div class="pb small">Enviado em ${dt(c.pec.ts)}<br><span class="mono">${c.pec.id}</span><br><a href="#" id="vf">Ver FHIR Bundle</a></div></div>` : ""}
    ${["admin", "gestor"].includes(m.perfil) ? `<div class="panel"><div class="ph"><h3>Gestão</h3></div><div class="pb"><select id="pr" style="padding:5px">${["Rotina", "Prioritário", "Urgente"].map((x) => `<option ${c.prioridade === x ? "selected" : ""}>${x}</option>`).join("")}</select></div></div>` : ""}
    </div></div>`;
  return { html, after: (b) => ligaDetalhe(b, c) };
}

async function acao(c, a, body) {
  const r = await api(`/cases/${c.id}/${a}`, body || {});
  await carregar();
  return r;
}

function ligaDetalhe(b, c) {
  const on = (sel, fn) => { const e = b.querySelector(sel); if (e) e.onclick = fn; };
  b.querySelector("#lk")?.addEventListener("focus", (e) => e.target.select());
  on("#setbase", (e) => { e.preventDefault(); const v = prompt("URL pública (ex.: https://xxxx.trycloudflare.com)", baseUrl()); if (v !== null) { v ? localStorage.setItem("baseUrl", v.replace(/\/$/, "")) : localStorage.removeItem("baseUrl"); location.reload(); } });
  on("#vf", (e) => { e.preventDefault(); modal({ titulo: "FHIR Bundle · PEC e-SUS APS (simulado)", lg: true, semRodape: true, corpo: `<pre class="json">${esc(JSON.stringify(fhir(c), null, 2))}</pre>` }); });
  const pr = b.querySelector("#pr");
  on("#ms", async () => {
    const t = b.querySelector("#mt").value.trim();
    if (!t) { toast("Escreva a mensagem.", true); return; }
    try { await acao(c, "mensagem", { texto: t, anexos: [...b.querySelector("#mf").files].map((f) => ({ nome: f.name, tamanho: f.size })) }); toast("Mensagem enviada."); const r = detalhe(c.id); b.innerHTML = r.html; r.after(b); }
    catch (e) { toast(e.message, true); }
  });
  if (pr) pr.onchange = async () => { await acao(c, "prioridade", { prioridade: pr.value }); toast("Prioridade atualizada."); location.reload(); };
  const ligaRascunho = () => setTimeout(() => { const rs = document.querySelector("#rs"); if (rs) rs.onclick = () => { document.querySelector("#t").value = rascunho(c, c.transcricao); }; }, 0);
  const campoTexto = (rot, dica, ini = "") => `<div class="fld"><label>${rot}</label><textarea id="t" style="min-height:190px">${esc(ini)}</textarea><div class="hint">${dica}</div></div><div><button class="btn sec sm" id="rs" type="button">${ic.sparkle} Gerar rascunho do Copiloto</button></div>`;
  const h = {
    assumir: async () => { await acao(c, "assumir"); toast("Solicitação em análise."); },
    entrar: async () => { if (S.me.perfil === "especialista" && c.status === "teleatendimento_agendado") await acao(c, "iniciar_atendimento"); location.hash = "#/sala/" + c.sala; },
    encerrar: async () => { await acao(c, "encerrar"); toast("Pedido encerrado."); },
    pec: async () => { await acao(c, "sync_pec"); toast("Evolução enviada ao PEC e-SUS."); },
    assinar: () => modal({ titulo: "Assinatura eletrônica", ok: "Assinar documento", corpo: `<p>O parecer será assinado com certificado digital ICP-Brasil (simulado) e receberá um código verificável.</p><div class="fld"><label>Certificado</label><select id="cert"><option>ICP-Brasil A3 (simulada)</option><option>Gov.br avançada (simulada)</option></select></div>`, onOk: async (m) => { await acao(c, "assinar", { tipo: m.querySelector("#cert").value }); toast("Documento assinado."); } }),
    enviar: () => modal({ titulo: "Anexar as informações solicitadas", ok: "Enviar ao teleconsultor", corpo: `<div class="fld"><label>Informações</label><textarea id="t"></textarea></div><div class="fld"><label>Anexos</label><input id="f" type="file" multiple></div>`, onOk: async (m) => { const t = m.querySelector("#t").value.trim(); if (!t) { toast("Descreva as informações.", true); return false; } await acao(c, "enviar_info", { texto: t, anexos: [...m.querySelector("#f").files].map((f) => ({ nome: f.name, tamanho: f.size })) }); toast("Informações enviadas."); } }),
    p11sim: () => {
      modal({ titulo: "Passo 12 · Emitir parecer e encerrar o pedido", lg: true, ok: "Emitir parecer", corpo: `<div class="f"><div class="pill-info">Opção: <b>Teleparecer resolvido e evoluído no prontuário eletrônico</b></div>${campoTexto("Parecer", "Use o rascunho do Copiloto como ponto de partida. A revisão é obrigatória.", c.resposta ? c.resposta.texto : "")}</div>`,
        onOk: async (m) => { const t = m.querySelector("#t").value.trim(); if (t.length < 20) { toast("Escreva o parecer completo.", true); return false; } await acao(c, "responder", { opcao: "resolvido", texto: t }); toast("Parecer emitido. Falta a assinatura eletrônica."); } });
      ligaRascunho();
    },
    p13: (ini = "info") => {
      let sel = "";
      const sl = S.d.slots.filter((s) => s.status === "livre" && usr(s.especialista).especialidade === c.especialidade);
      const OPS = [["info", "1", "Solicito mais informações (descreva as informações necessárias)"], ["sync", "2", "Favor marcar teleatendimento síncrono com a presença do paciente (horário disponível)"], ["hospitalar", "3", "Favor seguir fluxo hospitalar (já estabelecido)"], ["evoluir", "4", "Evoluir teleparecer no prontuário"]];
      const area = (op) => op === "info" ? `<div class="fld"><label>Informações necessárias</label><textarea id="t" placeholder="Ex.: enviar ECG de 12 derivações e a curva de troponina"></textarea></div>`
        : op === "sync" ? `<div id="g">${slotGrid(sl, sel)}</div>`
        : op === "hospitalar" ? campoTexto("Orientação ao médico solicitante", "Descreva o encaminhamento pelo fluxo hospitalar já estabelecido.")
        : campoTexto("Evolução no prontuário", "O teleparecer será evoluído no prontuário eletrônico.", c.resposta ? c.resposta.texto : "");
      const mm = modal({ titulo: "Passo 13 · Responder no Sistema de Telessaúde", lg: true, ok: "Registrar", corpo: `<div class="opcoes13">${OPS.map((o, i) => `<label class="o13"><input type="radio" name="op13" value="${o[0]}" ${i === 0 ? "" : ""}${o[0] === ini ? "checked" : ""}><b>${o[1]}</b><span>${o[2]}</span></label>`).join("")}</div><div id="area13" style="margin-top:14px">${area(ini)}</div>`,
        onOk: async (m) => {
          const op = m.querySelector("input[name=op13]:checked").value;
          const t = (m.querySelector("#t") || {}).value?.trim();
          if (op === "info") { if (!t) { toast("Descreva a informação necessária.", true); return false; } await acao(c, "solicitar_info", { texto: t }); toast("Pedido enviado ao médico solicitante."); }
          else if (op === "sync") { if (!sel) { toast("Selecione um horário.", true); return false; } await acao(c, "agendar", { slot: sel }); toast("Teleatendimento marcado."); }
          else { if (!t || t.length < 20) { toast("Escreva o texto completo.", true); return false; } await acao(c, "responder", { opcao: op, texto: t }); toast("Resposta registrada. Falta a assinatura eletrônica."); }
        } });
      const redesenha = () => { const op = mm.el.querySelector("input[name=op13]:checked").value; mm.el.querySelector("#area13").innerHTML = area(op); ligaRascunho(); };
      mm.el.addEventListener("change", (e) => { if (e.target.name === "op13") redesenha(); });
      mm.el.addEventListener("click", (e) => { const s = e.target.closest(".slot"); if (s) { sel = s.dataset.slot; mm.el.querySelector("#g").innerHTML = slotGrid(sl, sel); } });
      ligaRascunho();
    },
    p13_info: () => h.p13("info"), p13_sync: () => h.p13("sync"), p13_hospitalar: () => h.p13("hospitalar"), p13_evoluir: () => h.p13("evoluir"),
  };
  b.querySelectorAll("[data-a]").forEach((x) => (x.onclick = async () => {
    const a = x.dataset.a;
    try {
      const out = h[a]();
      if (out && out.then) await out;
      if (!document.getElementById("modal-root").innerHTML) { const r = detalhe(c.id); b.innerHTML = r.html; r.after(b); }
    } catch (e) { toast(e.message, true); }
  }));
}

/* ---------- documento imprimível ---------- */
export function documento(id, root) {
  const ex = S.d.exams.find((e) => e.id === id);
  const c = caso(id);
  const doc = ex ? { titulo: "Laudo de Espirometria", prot: ex.id, pac: pac(ex.paciente), texto: ex.laudo, ass: ex.assinatura, por: ex.laudista } : c && c.resposta ? { titulo: "Parecer de Teleconsultoria", prot: c.protocolo, pac: pac(c.paciente), texto: c.resposta.texto, ass: c.resposta.assinatura, por: c.resposta.por } : null;
  if (!doc) { root.innerHTML = `<div class="lobby">Documento indisponível.<p><a href="#/painel">Voltar</a></p></div>`; return; }
  const u = usr(doc.por);
  const vurl = baseUrl() + "/#/verificar/" + (doc.ass ? doc.ass.hash : "");
  root.innerHTML = `<div style="padding:20px;max-width:800px;margin:0 auto" class="bar"><a class="btn sec" href="${ex ? "#/telediagnostico" : "#/casos/" + id}">Voltar</a><button class="btn" id="pr">${ic.print} Imprimir</button></div>
    <div id="print-area"><div class="doc"><div class="cab"><img src="/img/fepecs.png" alt=""><div style="text-align:right;font-family:var(--font);font-size:12px">Secretaria de Estado de Saúde do DF<br>Telessaúde FEPECS</div></div>
    <h2>${doc.titulo}</h2><p style="text-align:center;margin:0 0 18px" class="mono">${esc(doc.prot)}</p>
    <p><b>Paciente:</b> ${esc(doc.pac.nome)} · CNS ${esc(doc.pac.cns)}</p><div class="txtblk" style="margin:14px 0">${esc(doc.texto)}</div>
    <div class="ass">${doc.ass ? `<div style="display:flex;justify-content:space-between;gap:16px;align-items:center"><div><b>${esc(u.nome)}</b> · ${esc(u.crm || "")}<br>${esc(u.cargo || "")}<br>Assinado eletronicamente em ${dt(doc.ass.ts)} (${esc(doc.ass.tipo)})<br><span class="mono" style="font-size:11px;word-break:break-all">SHA-256 ${doc.ass.hash}</span></div><img src="/api/qr?text=${encodeURIComponent(vurl)}" width="96" height="96" alt="QR"></div>` : "<i>Documento sem assinatura eletrônica.</i>"}</div></div></div>`;
  root.querySelector("#pr").onclick = () => window.print();
}
