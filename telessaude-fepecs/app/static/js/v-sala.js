import { S, api, carregar } from "./api.js";
import { esc, ic, toast, usr, pac, und, caso, idade, ini, dt } from "./ui.js";
import { copilotoHtml, rascunho } from "./copilot.js";

let cur = null; // sessão ativa da sala

async function getInfo(room) {
  const r = await fetch("/api/room/" + encodeURIComponent(room));
  return r.ok ? r.json() : null;
}

export async function convidado(room, root) {
  const info = await getInfo(room);
  if (!info) { root.innerHTML = `<div class="guest-wrap"><div class="lobby"><h2>Sala não encontrada</h2><p class="muted">Confira o link recebido.</p></div></div>`; return; }
  root.innerHTML = `<div class="guest-wrap"><div class="lobby"><div class="bar" style="margin-bottom:12px"><img src="/img/fepecs.png" width="52" height="52" alt=""><div><h2>Telessaúde FEPECS</h2><div class="muted small">${esc(info.titulo)}</div></div></div>
    <p>Você foi convidado para um teleatendimento. Informe seu nome para entrar. Sua câmera e seu microfone serão solicitados pelo navegador.</p>
    <div class="fld"><label>Seu nome</label><input id="gn" placeholder="Nome e sobrenome" value="${info.paciente ? "Paciente " + esc(info.paciente) : ""}"></div>
    <div id="pv"></div><button class="btn" id="gb" style="margin-top:14px;width:100%;justify-content:center;padding:10px">Entrar na sala</button></div></div>`;
  root.querySelector("#gb").onclick = () => {
    const nome = root.querySelector("#gn").value.trim();
    if (!nome) return toast("Informe seu nome.", true);
    iniciar(room, root, { guest: true, nome, info });
  };
}

export async function sala(room, root) {
  const info = await getInfo(room);
  if (!info) { root.innerHTML = `<div class="lobby"><h2>Sala não encontrada</h2><p><a href="#/painel">Voltar ao painel</a></p></div>`; return; }
  const c = info.caso ? caso(info.caso) : null;
  root.innerHTML = `<div class="guest-wrap"><div class="lobby"><div class="bar" style="margin-bottom:12px"><img src="/img/fepecs.png" width="52" height="52" alt=""><div><h2>${esc(info.titulo)}</h2><div class="muted small">${c ? esc(pac(c.paciente).nome) : "Telerreunião"}</div></div></div>
    <p>Antes de entrar, o navegador pedirá acesso à câmera e ao microfone. Entrando como <b>${esc(S.me.nome)}</b>.</p><div class="bar"><button class="btn" id="gb">Entrar na sala</button><a class="btn sec" href="${c ? "#/casos/" + c.id : "#/reunioes"}">Cancelar</a></div></div></div>`;
  root.querySelector("#gb").onclick = () => iniciar(room, root, { guest: false, nome: S.me.nome, info, c });
}

async function iniciar(room, root, opt) {
  const { guest, info } = opt;
  const c = opt.c || null;
  const eu = { stream: null, mic: true, cam: true, share: false };
  try { eu.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: { echoCancellation: true, noiseSuppression: true } }); }
  catch (e) {
    try { eu.stream = await navigator.mediaDevices.getUserMedia({ audio: true }); eu.cam = false; toast("Câmera indisponível. Entrando só com áudio.", true); }
    catch (e2) { eu.stream = new MediaStream(); eu.cam = false; eu.mic = false; toast("Sem acesso a câmera/microfone (é necessário HTTPS ou localhost). Você só verá e ouvirá.", true); }
  }
  let ice = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
  try { ice = await (await fetch("/api/ice")).json(); } catch (e) { /* usa padrão */ }

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws?` + (guest ? "nome=" + encodeURIComponent(opt.nome) : "token=" + S.token));
  const peers = {}; // id -> {pc, name, perfil}
  const linhas = c ? [...c.transcricao] : [];
  let meuId = null, rec = null, transc = false, t0 = Date.now();

  const sp = !guest && S.me.perfil === "especialista";
  const tabs = guest ? ["chat"] : c ? ["caso", "chat", "transcricao"] : ["chat"];
  root.innerHTML = `<div class="room full"><div class="stage"><div class="bar-top"><span class="pill-live">AO VIVO</span><b>${esc(info.titulo)}</b><span class="muted" id="tm">00:00</span><span style="flex:1"></span><span class="small" id="np"></span></div>
    <div class="videos n1" id="vs"></div>
    <div class="ctrl"><button class="cb" id="bm">${ic.mic} Microfone</button><button class="cb" id="bc">${ic.cam} Câmera</button><button class="cb" id="bs">${ic.screen} Compartilhar tela</button>${guest ? "" : `<button class="cb" id="bt">${ic.sparkle} Transcrição</button>`}<button class="cb end" id="bx">${ic.phone} Sair</button></div></div>
    <aside class="rside"><div class="tabs">${tabs.map((t, i) => `<button data-t="${t}" class="${i === 0 ? "on" : ""}">${{ caso: "Caso", chat: "Chat", transcricao: "Parecer" }[t]}</button>`).join("")}</div>
    <div class="tabpane" id="p-caso" ${tabs[0] === "caso" ? "" : "hidden"}></div><div class="tabpane" id="p-chat" ${tabs[0] === "chat" ? "" : "hidden"}></div><div class="chatin" id="ci" ${tabs[0] === "chat" ? "" : "hidden"}><input id="cm" placeholder="Mensagem" autocomplete="off"><button id="cs">Enviar</button></div>
    <div class="tabpane" id="p-transcricao" hidden></div></aside></div>`;
  const $ = (s) => root.querySelector(s);
  const vs = $("#vs");

  /* ---- painel do caso ---- */
  if (c && !guest) {
    const p = pac(c.paciente);
    $("#p-caso").innerHTML = `<dl class="dl" style="grid-template-columns:90px 1fr"><dt>Paciente</dt><dd><b>${esc(p.nome)}</b><br>${idade(p.nasc)} anos · ${p.sexo}</dd><dt>CNS</dt><dd class="mono">${esc(p.cns)}</dd><dt>Local</dt><dd>${esc(p.local)}</dd><dt>Protocolo</dt><dd class="mono">${c.protocolo}</dd></dl>
      <h4>Queixa</h4>${esc(c.queixa)}<h4>Anamnese</h4><div class="txtblk">${esc(c.anamnese)}</div><h4>Exame clínico</h4><div class="txtblk">${esc(c.exame_clinico)}</div><h4>Dúvida ao especialista</h4><div class="txtblk">${esc(c.duvida)}</div>`;
    $("#p-transcricao").innerHTML = `<div id="tr"></div><div id="inter" class="small muted"></div>${sp ? `<h4>Rascunho do parecer</h4><textarea id="rp" placeholder="O rascunho usa a transcrição e os dados do caso."></textarea><div class="bar" style="margin-top:8px"><button class="btn sm" id="gr">${ic.sparkle} Gerar rascunho</button><button class="btn sec sm" id="st">Salvar transcrição</button></div><p class="small muted">A emissão e a assinatura do parecer são feitas na tela da solicitação.</p>` : '<p class="small muted">A transcrição é salva na solicitação pelo especialista.</p>'}`;
  }
  const pintaTr = () => { const t = $("#tr"); if (t) { t.innerHTML = linhas.length ? linhas.map((l) => `<div class="msg tr"><b>${esc(l.autor)}</b> ${esc(l.texto)}</div>`).join("") : '<p class="small muted">Ative a transcrição para registrar a fala (Chrome ou Edge).</p>'; } };
  pintaTr();

  $(".tabs").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    root.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
    root.querySelectorAll(".tabpane").forEach((x) => (x.hidden = x.id !== "p-" + b.dataset.t));
    $("#ci").hidden = b.dataset.t !== "chat";
  };

  /* ---- vídeo ---- */
  const tile = (id, nome, perfil, stream, local) => {
    let el = vs.querySelector(`[data-id="${id}"]`);
    if (!el) {
      el = document.createElement("div"); el.className = "vt"; el.dataset.id = id;
      el.innerHTML = `<video autoplay playsinline ${local ? "muted" : ""}></video><div class="off">${esc(ini(nome) || "?")}</div><div class="lb">${esc(nome)}${perfil ? " · " + esc(perfil) : ""}${local ? " (você)" : ""}</div>`;
      vs.appendChild(el);
      layout();
    }
    if (stream) el.querySelector("video").srcObject = stream;
    return el;
  };
  const layout = () => { const n = vs.children.length; vs.className = "videos n" + Math.min(n, 4); $("#np").textContent = n + " participante(s)"; };
  const PERF = { admin: "Gestor / Administrador", gestor: "Gestor", solicitante: "Teleconsultor", especialista: "Médico especialista", enfermagem: "Enfermagem", suporte: "Suporte", paciente: "Paciente" };
  tile("local", opt.nome, guest ? "Paciente" : PERF[S.me.perfil], eu.stream, true);
  const marcaCam = (el, on) => el.classList.toggle("camoff", !on);
  marcaCam(vs.querySelector('[data-id="local"]'), eu.cam && eu.stream.getVideoTracks().length > 0);

  const send = (o) => ws.readyState === 1 && ws.send(JSON.stringify(o));

  const criaPeer = (id, nome, perfil, iniciador) => {
    if (peers[id]) return peers[id];
    const pc = new RTCPeerConnection(ice);
    const p = { pc, nome, perfil };
    peers[id] = p;
    if (iniciador) {
      const a = pc.addTransceiver("audio", { direction: "sendrecv" }), v = pc.addTransceiver("video", { direction: "sendrecv" });
      const at = eu.stream.getAudioTracks()[0], vt = eu.stream.getVideoTracks()[0];
      if (at) a.sender.replaceTrack(at);
      if (vt) v.sender.replaceTrack(vt);
    }
    pc.onicecandidate = (e) => e.candidate && send({ t: "signal", to: id, data: { candidate: e.candidate } });
    const remoto = new MediaStream();
    pc.ontrack = (e) => { remoto.addTrack(e.track); const el = tile(id, nome, PERF[perfil] || perfil, remoto, false); marcaCam(el, true); };
    pc.onconnectionstatechange = () => { if (["failed"].includes(pc.connectionState)) toast("Falha na conexão com " + nome + ". Pode ser necessário um servidor TURN.", true); };
    tile(id, nome, PERF[perfil] || perfil, remoto, false);
    if (iniciador) pc.createOffer().then((o) => pc.setLocalDescription(o)).then(() => send({ t: "signal", to: id, data: { sdp: pc.localDescription } }));
    return p;
  };

  ws.onopen = () => {};
  ws.onmessage = async (ev) => {
    const m = JSON.parse(ev.data);
    if (m.t === "hello") { meuId = m.id; send({ t: "join", room }); }
    else if (m.t === "error") { toast(m.msg, true); }
    else if (m.t === "peers") m.peers.forEach((p) => criaPeer(p.id, p.name, p.perfil, true));
    else if (m.t === "peer-joined") { toast(m.peer.name + " entrou na sala."); criaPeer(m.peer.id, m.peer.name, m.peer.perfil, false); }
    else if (m.t === "peer-left") { const p = peers[m.id]; if (p) { toast(p.nome + " saiu da sala."); p.pc.close(); delete peers[m.id]; } const el = vs.querySelector(`[data-id="${m.id}"]`); if (el) el.remove(); layout(); }
    else if (m.t === "signal") {
      const p = peers[m.from] || criaPeer(m.from, m.name, "", false);
      const d = m.data;
      try {
        if (d.sdp) {
          await p.pc.setRemoteDescription(d.sdp);
          if (d.sdp.type === "offer") {
            p.pc.getTransceivers().forEach((t) => {
              const k = t.receiver.track.kind, tr = k === "audio" ? eu.stream.getAudioTracks()[0] : (eu.share || eu.stream.getVideoTracks()[0]);
              t.direction = "sendrecv";
              if (tr) t.sender.replaceTrack(tr);
            });
            const an = await p.pc.createAnswer(); await p.pc.setLocalDescription(an); send({ t: "signal", to: m.from, data: { sdp: p.pc.localDescription } });
          }
        } else if (d.candidate) await p.pc.addIceCandidate(d.candidate);
      } catch (e) { console.warn(e); }
    }
    else if (m.t === "chat") addChat(m.name, m.texto);
    else if (m.t === "transcript") { linhas.push({ autor: m.name, texto: m.texto }); pintaTr(); }
    else if (m.t === "media-state") { const el = vs.querySelector(`[data-id="${m.from}"]`); if (el) marcaCam(el, m.cam); }
  };
  ws.onclose = () => { if (cur && cur.ws === ws && !cur.saindo) toast("Conexão com o servidor encerrada.", true); };

  const addChat = (nome, texto) => { const p = $("#p-chat"); p.insertAdjacentHTML("beforeend", `<div class="msg"><b>${esc(nome)}</b><div>${esc(texto)}</div></div>`); p.scrollTop = p.scrollHeight; };
  const enviaChat = () => { const i = $("#cm"); const t = i.value.trim(); if (!t) return; send({ t: "chat", texto: t }); addChat("Você", t); i.value = ""; };
  $("#cs").onclick = enviaChat; $("#cm").onkeydown = (e) => e.key === "Enter" && enviaChat();

  /* ---- controles ---- */
  const estado = () => send({ t: "media-state", cam: eu.cam });
  $("#bm").onclick = () => { eu.mic = !eu.mic; eu.stream.getAudioTracks().forEach((t) => (t.enabled = eu.mic)); $("#bm").classList.toggle("off", !eu.mic); $("#bm").innerHTML = (eu.mic ? ic.mic : ic.micoff) + " Microfone"; };
  $("#bc").onclick = () => { eu.cam = !eu.cam; eu.stream.getVideoTracks().forEach((t) => (t.enabled = eu.cam)); $("#bc").classList.toggle("off", !eu.cam); $("#bc").innerHTML = (eu.cam ? ic.cam : ic.camoff) + " Câmera"; marcaCam(vs.querySelector('[data-id="local"]'), eu.cam && eu.stream.getVideoTracks().length > 0); estado(); };
  $("#bs").onclick = async () => {
    const trocar = (track) => Object.values(peers).forEach((p) => p.pc.getTransceivers().filter((t) => t.receiver.track.kind === "video").forEach((t) => t.sender.replaceTrack(track)));
    if (!eu.share) {
      try {
        const d = await navigator.mediaDevices.getDisplayMedia({ video: true });
        const tr = d.getVideoTracks()[0]; trocar(tr); eu.share = tr; $("#bs").classList.add("off");
        const el = vs.querySelector('[data-id="local"] video'); el.srcObject = d;
        tr.onended = () => { fim(); };
        const fim = () => { const vt = eu.stream.getVideoTracks()[0] || null; trocar(vt); el.srcObject = eu.stream; eu.share = false; $("#bs").classList.remove("off"); };
        $("#bs").onclick = () => { tr.stop(); fim(); };
      } catch (e) { toast("Compartilhamento cancelado.", true); }
    }
  };
  const bt = $("#bt");
  if (bt) bt.onclick = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return toast("Transcrição requer Chrome ou Edge.", true);
    transc = !transc; bt.classList.toggle("off", transc);
    if (transc) {
      rec = new SR(); rec.lang = "pt-BR"; rec.continuous = true; rec.interimResults = false;
      rec.onresult = (e) => { for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) { const t = e.results[i][0].transcript.trim(); if (t) { linhas.push({ autor: S.me.nome, texto: t }); send({ t: "transcript", texto: t }); pintaTr(); } } };
      rec.onend = () => { if (transc) { try { rec.start(); } catch (e) { /* já ativo */ } } };
      try { rec.start(); toast("Transcrição ativada."); } catch (e) { /* ignora */ }
    } else { try { rec.stop(); } catch (e) { /* ignora */ } toast("Transcrição pausada."); }
  };
  const gr = $("#gr");
  if (gr) gr.onclick = () => { $("#rp").value = rascunho(c, linhas); };
  const st = $("#st");
  if (st) st.onclick = async () => { try { await api(`/cases/${c.id}/salvar_transcricao`, { linhas }); toast("Transcrição salva na solicitação."); } catch (e) { toast(e.message, true); } };

  const tmr = setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000); const el = $("#tm"); if (el) el.textContent = String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); }, 1000);

  const sair = async () => {
    if (cur) cur.saindo = true;
    clearInterval(tmr); transc = false; try { rec && rec.stop(); } catch (e) { /* ignora */ }
    Object.values(peers).forEach((p) => p.pc.close());
    eu.stream.getTracks().forEach((t) => t.stop()); if (eu.share) eu.share.stop();
    try { ws.close(); } catch (e) { /* ignora */ }
    cur = null;
    if (!guest && c && sp && linhas.length) { try { await api(`/cases/${c.id}/salvar_transcricao`, { linhas }); } catch (e) { /* ignora */ } }
    if (guest) root.innerHTML = `<div class="guest-wrap"><div class="lobby"><h2>Atendimento encerrado</h2><p class="muted">Obrigado por participar. Você já pode fechar esta janela.</p></div></div>`;
    else { try { await carregar(); } catch (e) { /* ignora */ } location.hash = c ? "#/casos/" + c.id : "#/reunioes"; }
  };
  $("#bx").onclick = sair;
  cur = { ws, saindo: false };
  window.addEventListener("hashchange", function h() { if (!location.hash.includes("/sala/") && !location.hash.includes("/convidado/")) { window.removeEventListener("hashchange", h); if (cur) { cur.saindo = true; clearInterval(tmr); eu.stream.getTracks().forEach((t) => t.stop()); Object.values(peers).forEach((p) => p.pc.close()); try { ws.close(); } catch (e) { /* ignora */ } cur = null; } } });
}
