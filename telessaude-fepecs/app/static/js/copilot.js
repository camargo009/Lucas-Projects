import { S } from "./api.js";
import { pac, idade, usr } from "./ui.js";

const ALERTAS = [
  [/dispneia|falta de ar/i, "Dispneia referida: confirmar saturação e sinais de instabilidade."],
  [/síncope|sincope/i, "Síncope: considerar monitorização e ECG seriado."],
  [/hemoptise/i, "Hemoptise: avaliar volume e estabilidade hemodinâmica."],
  [/creatinina|oligúria|diurese reduzida/i, "Função renal alterada: revisar nefrotóxicos e volemia."],
  [/spo2\s*(\d{2})/i, null],
];

export function analisar(c) {
  const p = pac(c.paciente);
  const txt = [c.queixa, c.anamnese, c.exame_clinico, c.hipotese, c.duvida].join(" ");
  const alertas = ALERTAS.filter(([re, msg]) => msg && re.test(txt)).map((x) => x[1]);
  const sp = /spo2\s*(\d{2})/i.exec(txt);
  if (sp && +sp[1] < 94) alertas.push(`Saturação de ${sp[1]}% em ar ambiente abaixo do esperado.`);
  const fc = /fc\s*(\d{2,3})/i.exec(txt);
  if (fc && (+fc[1] > 100 || +fc[1] < 60)) alertas.push(`Frequência cardíaca de ${fc[1]} bpm fora da faixa de referência.`);
  let sug = "Rotina";
  if (alertas.length >= 2 || /instável|choque|urgên/i.test(txt)) sug = "Urgente";
  else if (alertas.length === 1) sug = "Prioritário";
  const resumo = `${p.nome ? idade(p.nasc) + " anos, " + (p.sexo === "F" ? "sexo feminino" : "sexo masculino") : ""}. Queixa: ${c.queixa || "não informada"}. Hipótese do solicitante: ${c.hipotese || "não informada"}. Dúvida: ${c.duvida || "não informada"}.`;
  return { resumo, alertas, sugestao: sug };
}

export function rascunho(c, transcricao = []) {
  const falas = transcricao.map((l) => l.texto).join(" ").trim();
  const a = analisar(c);
  const p = pac(c.paciente);
  return `PARECER DE ${c.especialidade.toUpperCase()}
Paciente: ${p.nome} (${idade(p.nasc)} anos). Protocolo ${c.protocolo}.

Resumo do caso: ${a.resumo}

${falas ? "Discussão no teleatendimento: " + falas + "\n\n" : ""}Impressão: [descrever]
Conduta sugerida: [descrever]
Reavaliação: [prazo e critérios de nova discussão]

Rascunho gerado pelo Copiloto Telessaúde. Revisão e validação pelo especialista são obrigatórias.`;
}

export function copilotoHtml(c) {
  const a = analisar(c);
  return `<div class="panel"><div class="ph"><h3>Copiloto Telessaúde</h3><span class="tag azul">apoio · revisão humana</span></div><div class="pb">
    <p class="small" style="margin:0 0 8px">${a.resumo}</p>
    <div class="small"><b>Prioridade sugerida:</b> ${a.sugestao}</div>
    ${a.alertas.length ? `<ul class="small" style="margin:8px 0 0;padding-left:18px">${a.alertas.map((x) => `<li>${x}</li>`).join("")}</ul>` : '<p class="small muted" style="margin:8px 0 0">Nenhum alerta identificado nos dados informados.</p>'}
    <p class="small muted" style="margin:10px 0 0">Sugestões automáticas não substituem o julgamento clínico.</p></div></div>`;
}
