# Telessaúde FEPECS: estado atual e próximos passos

## Estado em 10/11/2026
- Demo funcional para apresentação de 23/11/2026, no GitHub (`camargo009/Lucas-Projects`, branch `camargo009-redcap-task-list`, pasta `telessaude-fepecs`).
- 3 perfis (senha `telessaude`): médico (`medico@`), teleconsultor (`teleconsultor@`), gestor/administrador (`gestor@`).
- Fluxo 1 (Teleparecer, passos 1 a 13) implementado conforme o fluxograma oficial:
  - assíncrono por formulário (48 h), sala de teleparecer sem o médico, passo 11 (Sim: passo 12; Não: passo 13 com 4 opções).
  - troca de informações em formulário entre médico e teleconsultor, com anexos.
- Vídeo WebRTC 3 pontas funciona; acesso remoto via túnel cloudflared (`iniciar.ps1`).
- Simulados: assinatura ICP-Brasil, PEC e-SUS (FHIR), Copiloto de rascunho. A logo da FEPECS é um recorte de baixa resolução; trocar pela oficial.

## Tecnologia
Python 3 + aiohttp (REST, WebSocket, sinalização WebRTC); SPA em JavaScript puro (módulos ES) sem build; dados em `data.json`.

## Hipóteses a confirmar
- Passo 11 "Sim" vai ao 12 e "Não" ao 13; depois do teleatendimento (passo 8) o especialista registra o passo 13.
- Enfermagem representada só por link/QR e observação (sem login).

## Não testado
Telerreuniões, telediagnóstico, suporte, administração, documento impresso/verificação, câmera real e vídeo 3 pontas após as últimas mudanças.

## Colocar online (próxima etapa)
- **TURN:** retransmite o vídeo quando a conexão direta é bloqueada (hospital, VPN, 4G). STUN só descobre o IP público. O código lê `TURN_URL`, `TURN_USER`, `TURN_PASS`.
- **Estrutura:** navegadores -> HTTPS/WSS -> app Python em container -> Postgres; vídeo via WebRTC com TURN.
- **Serviços sugeridos (valores a confirmar):** app em Railway/Render/Fly.io; Postgres em Neon/Supabase; domínio e HTTPS na Cloudflare; TURN da Metered, Twilio ou Cloudflare.
- **Projeto real:** LiveKit (SFU) para mais participantes e gravação; hospedagem no Brasil; LGPD, criptografia e auditoria.
- **Tarefas:** Dockerfile, migrar `data.json` para Postgres, chat síncrono em tempo real pelo WebSocket, senhas por usuário, configuração do TURN.
