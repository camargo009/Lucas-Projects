import { S, api, carregar } from "./api.js";
import { esc, ic, toast, usr, pac, und, idade, pageHead, priTag } from "./ui.js";
import { analisar } from "./copilot.js";
import { slotGrid } from "./v-casos.js";

/* Assistente "Nova solicitação": segue o Fluxo 1 (Teleparecer), passos 1 a 9 do fluxograma oficial. */
let W = null;
const NOVO0 = () => ({ step: "ctx", prioridade: "Rotina", paciente: "", situacao: "Internado", especialidade: "", modalidade: "assincrona", semDeslocamento: false, slot: "", dados: { queixa: "", anamnese: "", exame_clinico: "", hipotese: "", duvida: "" }, anexos: [], novoPac: null, hist: [] });
const ESPECS = ["Cardiologia"];
const SITUACOES = ["Internado", "Em processo de internação", "Em processo de alta"];

export function novo() {
  if (!W) W = NOVO0();
  return { html: "", after: (b) => desenha(b) };
}

const passo = (n, q, sub, ops, extra = "") => `<div class="decisao"><div class="n">PASSO ${n} DO FLUXOGRAMA</div><div class="q">${q}</div><p style="margin-top:0;color:var(--ink-2)">${sub}</p>${ops.map((o) => `<div class="opt" data-op="${o[0]}"><b>${o[0] === "sim" ? "S" : "N"}</b><div>${o[1]}</div></div>`).join("")}${extra}<div class="bar" style="margin-top:12px"><button class="btn sec" id="w-back">Voltar</button><a href="#/fluxo" class="small">Ver diagrama completo</a></div></div>`;

function desenha(b) {
  const w = W;
  const fases = [["ctx", "1 · Paciente"], ["triagem", "2 a 6 · Triagem do fluxo"], ["dados", "7 ou 9 · Solicitação"], ["rev", "Envio"]];
  const fase = { ctx: 0, p2: 1, p3: 1, p4: 1, p5: 1, p6: 1, agenda: 2, dados: 2, rev: 3 }[w.step];
  const stepper = `<div class="steps">${fases.map((f, i) => `<div class="${i < fase ? "ok" : i === fase ? "on" : ""}"><b>${i < fase ? "✓" : i + 1}</b>${f[1]}</div>`).join("")}</div>`;
  const pn = w.paciente && w.paciente !== "novo" ? pac(w.paciente) : null;
  const nomePac = pn ? pn.nome : w.novoPac?.nome || "";
  let corpo = "";
  if (w.step === "ctx") {
    corpo = `<div class="panel"><div class="ph"><h3>Passo 1 · Paciente em ambiente hospitalar com necessidade de parecer</h3></div><div class="pb"><div class="f c2">
      <div class="fld span2"><label>Paciente</label><select id="w-pac"><option value="">Selecione um paciente</option>${S.d.patients.map((p) => `<option value="${p.id}" ${w.paciente === p.id ? "selected" : ""}>${esc(p.nome)} · ${idade(p.nasc)} anos · ${esc(p.local)}</option>`).join("")}<option value="novo" ${w.paciente === "novo" ? "selected" : ""}>+ Cadastrar novo paciente</option></select></div>
      ${w.paciente === "novo" ? `<div class="fld"><label>Nome completo</label><input id="np-nome" value="${esc(w.novoPac?.nome || "")}"></div><div class="fld"><label>Nascimento</label><input id="np-nasc" type="date" value="${esc(w.novoPac?.nasc || "")}"></div><div class="fld"><label>Sexo</label><select id="np-sexo"><option value="M">Masculino</option><option value="F" ${w.novoPac?.sexo === "F" ? "selected" : ""}>Feminino</option></select></div><div class="fld"><label>Local (enfermaria, leito)</label><input id="np-local" value="${esc(w.novoPac?.local || "")}"></div>` : ""}
      <div class="fld"><label>Situação do paciente</label><select id="w-sit">${SITUACOES.map((x) => `<option ${w.situacao === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
      <div class="fld"><label>Especialidade do parecer</label><select id="w-esp"><option value="">Selecione</option>${ESPECS.map((e) => `<option ${w.especialidade === e ? "selected" : ""}>${e}</option>`).join("")}</select></div>
      <div class="fld"><label>Prioridade</label><select id="w-pri">${["Rotina", "Prioritário", "Urgente"].map((x) => `<option ${w.prioridade === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
      </div><div class="bar end" style="margin-top:16px"><button class="btn" id="w-next">Continuar</button></div></div></div>`;
  } else if (w.step === "p2") {
    corpo = passo(2, "O parecer tem que ser presencial?", "O paciente precisa ser avaliado pessoalmente pelo especialista?", [["sim", "Sim, o parecer tem que ser presencial"], ["nao", "Não, pode ser feito à distância"]]);
  } else if (w.step === "p3") {
    corpo = `<div class="decisao"><div class="n">PASSO 3 DO FLUXOGRAMA</div><div class="q">Solicitar parecer convencional presencial via prontuário eletrônico</div><p>Este paciente precisa de parecer presencial. Registre a solicitação pelo prontuário eletrônico do hospital. Nenhum pedido é criado no Sistema de Telessaúde.</p><div class="bar"><button class="btn sec" id="w-back">Voltar</button><a class="btn" href="#/painel">Concluir</a></div></div>`;
  } else if (w.step === "p4") {
    corpo = `<div class="decisao"><div class="n">PASSO 4 DO FLUXOGRAMA</div><div class="q">Solicitar teleparecer via Sistema de Telessaúde</div><p>Você está no Sistema de Telessaúde. Responda mais algumas perguntas para encaminhar o pedido pelo caminho correto.</p><div class="bar"><button class="btn sec" id="w-back">Voltar</button><button class="btn" id="w-p4">Continuar</button></div></div>`;
  } else if (w.step === "p5") {
    corpo = passo(5, "O teleparecer pode ser assíncrono?", "A resposta do especialista pode ser dada sem teleatendimento em tempo real, com prazo de até 48 horas?", [["sim", "Sim, solicitar teleconsultoria assíncrona"], ["nao", "Não, é preciso um teleatendimento"]]);
  } else if (w.step === "p6") {
    corpo = passo(6, "O paciente tem condições de ser deslocado até a sala de teleparecer?", "Para realizar teleatendimento diretamente com o especialista requisitado, sem a presença do teleconsultor solicitante ou plantonista.", [["sim", "Sim, solicitar agenda de teleconsulta hospitalar"], ["nao", "Não, o pedido segue para análise do especialista"]]);
  } else if (w.step === "agenda") {
    const sl = S.d.slots.filter((s) => s.status === "livre" && usr(s.especialista).especialidade === w.especialidade);
    corpo = `<div class="panel"><div class="ph"><h3>Passo 7 · Agenda de teleconsulta hospitalar · ${esc(w.especialidade)}</h3></div><div class="pb"><p class="small muted" style="margin-top:0">Escolha o horário disponibilizado pelo especialista. No dia e hora marcados, a equipe de enfermagem desloca o paciente à sala de teleparecer e acessa o sistema.</p>${slotGrid(sl, w.slot)}<div class="bar end" style="margin-top:14px"><button class="btn sec" id="w-back">Voltar</button><button class="btn" id="w-next" ${w.slot ? "" : "disabled"}>Reservar e preencher a solicitação</button></div></div></div>`;
  } else if (w.step === "dados") {
    const d = w.dados;
    corpo = `<div class="panel"><div class="ph"><h3>${w.modalidade === "assincrona" && !w.semDeslocamento ? "Passo 9 · Teleconsultoria assíncrona: anamnese e exame clínico" : "Dados clínicos: anamnese e exame clínico"}</h3><span class="small muted">${esc(nomePac)}</span></div><div class="pb"><div class="f">
      <div class="fld"><label>Queixa principal</label><input id="d-queixa" value="${esc(d.queixa)}"></div>
      <div class="fld"><label>Anamnese</label><textarea id="d-anamnese">${esc(d.anamnese)}</textarea></div>
      <div class="fld"><label>Exame clínico</label><textarea id="d-exame_clinico">${esc(d.exame_clinico)}</textarea></div>
      <div class="f c2"><div class="fld"><label>Hipótese diagnóstica</label><input id="d-hipotese" value="${esc(d.hipotese)}"></div><div class="fld"><label>Anexos (exames, imagens)</label><input id="d-files" type="file" multiple></div></div>
      <div class="fld"><label>Dúvida / pergunta ao especialista</label><textarea id="d-duvida">${esc(d.duvida)}</textarea></div>
      ${w.anexos.length ? `<div class="small">Anexos: ${w.anexos.map((a) => esc(a.nome)).join(", ")}</div>` : ""}
      </div><div class="bar end" style="margin-top:16px"><button class="btn sec" id="w-back">Voltar</button><button class="btn" id="w-next">Revisar</button></div></div></div>`;
  } else if (w.step === "rev") {
    const d = w.dados, a = analisar({ ...d, paciente: w.paciente, especialidade: w.especialidade });
    const caminho = w.modalidade === "sincrona" ? "Teleconsulta hospitalar na sala de teleparecer, sem a presença do teleconsultor solicitante (passos 6 a 8)" : w.semDeslocamento ? "Paciente não pode ser deslocado: o especialista analisa o pedido em até 48 h (passo 6 → 10)" : "Teleconsultoria assíncrona, resposta do especialista em até 48 h (passos 5, 9 e 10)";
    corpo = `<div class="grid g-main"><div class="panel"><div class="ph"><h3>Revisão da solicitação</h3></div><div class="pb"><dl class="dl">
      <dt>Caminho no fluxo</dt><dd>${caminho}</dd><dt>Especialidade</dt><dd>${esc(w.especialidade)}</dd><dt>Paciente</dt><dd>${esc(nomePac)} · ${esc(w.situacao)}</dd><dt>Prioridade</dt><dd>${priTag(w.prioridade)}</dd>
      <dt>Queixa</dt><dd>${esc(d.queixa)}</dd><dt>Anamnese</dt><dd class="txtblk">${esc(d.anamnese)}</dd><dt>Exame clínico</dt><dd class="txtblk">${esc(d.exame_clinico)}</dd><dt>Hipótese</dt><dd>${esc(d.hipotese)}</dd><dt>Dúvida</dt><dd class="txtblk">${esc(d.duvida)}</dd></dl>
      <div class="bar end" style="margin-top:16px"><button class="btn sec" id="w-back">Voltar</button><button class="btn ok" id="w-send">${ic.check} Enviar solicitação</button></div></div></div>
      <div class="panel"><div class="ph"><h3>Verificação do Copiloto</h3></div><div class="pb small"><p style="margin-top:0">Prioridade sugerida: <b>${a.sugestao}</b></p>${a.alertas.length ? `<ul style="padding-left:18px">${a.alertas.map((x) => `<li>${x}</li>`).join("")}</ul>` : "<p class='muted'>Sem alertas.</p>"}${a.sugestao !== w.prioridade ? `<button class="btn sec sm" id="w-pri-sug">Adotar prioridade ${a.sugestao}</button>` : ""}</div></div></div>`;
  }
  b.innerHTML = pageHead("Nova solicitação de teleparecer", "Siga o Fluxo 1: as respostas definem o caminho correto do pedido.") + stepper + corpo;
  liga(b);
}

function guarda(b) {
  const g = (id) => b.querySelector(id);
  if (g("#w-pac")) { W.paciente = g("#w-pac").value; W.situacao = g("#w-sit").value; W.especialidade = g("#w-esp").value; W.prioridade = g("#w-pri").value; if (g("#np-nome")) W.novoPac = { nome: g("#np-nome").value, nasc: g("#np-nasc").value, sexo: g("#np-sexo").value, local: g("#np-local").value }; }
  if (g("#d-queixa")) for (const k of Object.keys(W.dados)) W.dados[k] = g("#d-" + k).value;
}

function liga(b) {
  const w = W;
  const ir = (s) => { w.hist.push(w.step); w.step = s; desenha(b); };
  const pac_ = b.querySelector("#w-pac");
  if (pac_) pac_.onchange = () => { guarda(b); desenha(b); };
  const back = b.querySelector("#w-back");
  if (back) back.onclick = () => { guarda(b); w.step = w.hist.pop() || "ctx"; w.modalidade = "assincrona"; w.semDeslocamento = false; w.slot = ""; desenha(b); };
  const p4 = b.querySelector("#w-p4");
  if (p4) p4.onclick = () => ir("p5");
  b.querySelectorAll(".opt").forEach((o) => (o.onclick = () => {
    const v = o.dataset.op;
    if (w.step === "p2") v === "sim" ? ir("p3") : ir("p4");
    else if (w.step === "p5") { if (v === "sim") { w.modalidade = "assincrona"; ir("dados"); } else ir("p6"); }
    else if (w.step === "p6") { if (v === "sim") { w.modalidade = "sincrona"; ir("agenda"); } else { w.modalidade = "assincrona"; w.semDeslocamento = true; ir("dados"); } }
  }));
  b.querySelectorAll(".slot").forEach((s) => (s.onclick = () => { w.slot = s.dataset.slot; desenha(b); }));
  const nx = b.querySelector("#w-next");
  if (nx) nx.onclick = () => {
    guarda(b);
    if (w.step === "ctx") {
      if (!w.paciente || !w.especialidade) return toast("Selecione o paciente e a especialidade.", true);
      if (w.paciente === "novo" && !(w.novoPac && w.novoPac.nome)) return toast("Informe o nome do paciente.", true);
      ir("p2");
    } else if (w.step === "agenda") ir("dados");
    else if (w.step === "dados") {
      if (!w.dados.queixa || !w.dados.duvida) return toast("Informe a queixa principal e a dúvida ao especialista.", true);
      ir("rev");
    }
  };
  const fi = b.querySelector("#d-files");
  if (fi) fi.onchange = () => { w.anexos = [...fi.files].map((f) => ({ nome: f.name, tamanho: f.size })); guarda(b); desenha(b); };
  const ps = b.querySelector("#w-pri-sug");
  if (ps) ps.onclick = () => { w.prioridade = analisar({ ...w.dados, paciente: w.paciente, especialidade: w.especialidade }).sugestao; desenha(b); };
  const send = b.querySelector("#w-send");
  if (send) send.onclick = async () => {
    send.disabled = true;
    try {
      const body = { especialidade: w.especialidade, prioridade: w.prioridade, situacao: w.situacao, sem_deslocamento: w.semDeslocamento, anexos: w.anexos, ...w.dados };
      if (w.paciente === "novo") body.novo_paciente = w.novoPac; else body.paciente = w.paciente;
      if (w.modalidade === "sincrona" && w.slot) body.slot = w.slot;
      const c = await api("/cases", body);
      W = null;
      await carregar();
      toast("Solicitação " + c.protocolo + " enviada ao médico especialista.");
      location.hash = "#/casos/" + c.id;
    } catch (e) { toast(e.message, true); send.disabled = false; }
  };
}

window.addEventListener("hashchange", () => { if (!location.hash.startsWith("#/novo")) W = null; });
