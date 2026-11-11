# CONTEXTO — Telessaúde FEPECS (leia primeiro ao retomar em outra máquina)

## Quem / por quê
- Lucas, dono da BazeTech (ME, Simples Nacional). Fala português.
- Demo funcional para apresentação em **23/11/2026**, apoiando proposta para o sistema de telessaúde da FEPECS/SES-DF ("SIS-TELE SUS-DF").
- Fluxo de referência: fluxograma oficial **"Fluxo 1: Teleparecer" (passos 1–13)**, imagem `WhatsApp Image 2026-11-10 at 15.57.16.jpeg` (Downloads do Lucas; não está no repo). **O sistema deve funcionar exatamente como o fluxograma.**

## Perfis (somente 3, a pedido do Lucas)
| Perfil | Login (senha `telessaude`) | Papel |
|---|---|---|
| Médico (solicitante) | medico@telessaude.fepecs — Dr. Henrique Matos | abre o caso, responde pedidos de informação, participa do atendimento |
| Teleconsultor (especialista) | teleconsultor@telessaude.fepecs — Dra. Beatriz Nogueira | assume o caso, pede informações, agenda, atende, emite parecer |
| Gestor/Administrador | gestor@telessaude.fepecs — Marina Duarte | agenda, usuários, integrações, visão geral |
- Enfermagem não tem login (apenas link/QR e nota).
- Não incluir consulta assíncrona via chat como fluxo próprio: o Lucas pediu só os 3 perfis e o fluxo do fluxograma.

## Stack
- Python 3 + aiohttp (REST, WebSocket, sinalização WebRTC). Persistência em `data.json` (apagar para voltar ao seed).
- Frontend: SPA vanilla JS com ES modules, sem build.
- Vídeo WebRTC (3 participantes); TURN opcional via env `TURN_URL`, `TURN_USER`, `TURN_PASS`.
- **Simulados:** assinatura ICP-Brasil, integração PEC e-SUS (FHIR), Copiloto (IA).
- Rodar: ver `README.md` / `iniciar.ps1` (porta 8080). Acesso remoto de teste via cloudflared tunnel.
- API: `POST /api/login` devolve token; enviar `Authorization: Bearer <token>`.

## Mapa do código (`app\`)
- `server.py` — backend: `seed()`, `create_case`, `case_action` (ações: mensagem, assumir, solicitar_info, enviar_info, agendar, iniciar_atendimento, responder, assinar, sync_pec, encerrar). `mensagem` só para solicitante e especialista (403 para outros).
- `static\js\v-novo.js` — assistente de novo caso (passos 1–9).
- `static\js\v-casos.js` — lista/detalhe do caso, `fluxoHtml` (passos 10–13 como cards), `msgsHtml` (painel "Troca de informações": texto + anexo), `ligaDetalhe` (handlers `p11sim`, `p13`, `p13_info|sync|hospitalar|evoluir`).
- `static\js\app.js` — roteador, dashboard, login (3 cards de perfil).
- `static\js\v-outros.js` — agenda, telediagnóstico, suporte, admin, integrações, view `fluxo`.
- `static\js\v-sala.js` — sala WebRTC.
- `static\css\app.css` — tema (classes `.trlist`, `.trm`, `.trm.eu` para mensagens).

## Decisões e feedback do Lucas (histórico resumido)
1. Visual precisava ficar mais bonito/intuitivo → tema moderno aplicado.
2. Usuários devem refletir as informações dos documentos → perfis ajustados.
3. Fluxo confuso → reescrito seguindo o fluxograma (commit d3877ac).
4. O médico não conseguia interagir → criada **troca de informações** (mensagens + anexos) entre médico e teleconsultor, funcionando via formulário. Vídeo pode ser simulado.
5. Sentiu falta do **passo 13** → passo 11 mostra "Sim, emitir parecer (passo 12)" e 4 cards para o 13: pedir/enviar mais informações, teleatendimento síncrono, encaminhamento hospitalar, evolução do caso (commit 96658a8).

## Suposições NÃO confirmadas (validar com o Lucas)
- Passo 11 "Sim" → 12 (parecer) e "Não" → 13.
- Após o teleatendimento do passo 8, o especialista registra o passo 13.
- Enfermagem sem login.
- Logo da FEPECS é um recorte de baixa resolução → trocar pelo oficial.

## Testado / não testado
- Testado: API (5 casos assíncronos, mais informações, agendar síncrono, hospitalar, sala_teleparecer, 403 por perfil, mensagem dos dois perfis); UI: login dos 3 perfis, wizard até o passo 5, cards do passo 11, médico enviando mensagem; sem erros de JS.
- **Não testado:** formulários/modais do passo 13 no navegador, vídeo 3 vias após as mudanças, telerreuniões, telediagnóstico, suporte, admin, impressão/verificação de documentos, câmera real.

## Evolução planejada (online)
- Discutido: hospedar online com banco de dados permite vídeo real e chat assíncrono/síncrono.
- Requisitos: HTTPS; **servidor TURN** (relay WebRTC quando P2P falha por NAT/firewall; STUN só descobre IP público); chat síncrono via WebSocket já existente; banco Postgres (ou SQLite).
- Serviços cogitados (preços são estimativas, não confirmados): Railway/Render/Fly.io (app), Neon/Supabase (Postgres), Cloudflare (DNS/HTTPS), Metered/Twilio/Cloudflare TURN, LiveKit para o projeto real.
- To-do: Dockerfile, migrar `data.json` → Postgres, configurar TURN, chat síncrono em tempo real, senhas individuais. Ver também `PROXIMOS-PASSOS.md`.

## Ambiente/convenções (da máquina original)
- Windows + PowerShell (sem `&&`). Python 3.15; `requests` não instalado (usar urllib). `node` ausente.
- Testes de UI com Playwright + Edge: `p.chromium.launch(channel="msedge")`.
- Reiniciar servidor: achar PID em `Get-NetTCPConnection -LocalPort 8080` (estado Listen), `Stop-Process -Id`, apagar `data.json`, `Start-Process python server.py -WindowStyle Hidden` em `app\`.
- Commits: autor `camargo009`, trailer `Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>`.

## Git
- Repo: https://github.com/camargo009/Lucas-Projects — o sistema está na branch **`camargo009-redcap-task-list`** (não na `main`), pasta `telessaude-fepecs\`.
- Outra máquina: `git clone` → `git checkout camargo009-redcap-task-list` → abrir o Copilot na pasta → "leia CONTEXTO.md, PROXIMOS-PASSOS.md e README.md e vamos continuar".
