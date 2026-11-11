# Telessaúde FEPECS — Demonstração (BazeTech)

Protótipo funcional para a apresentação de 23/11/2026. Todos os dados são fictícios.
PEC e-SUS e assinatura ICP-Brasil são **simulados** (hash SHA-256 + página de verificação).

## Rodar em outra máquina (Windows)
1. Instale o **Python 3.10+** (python.org, marque "Add to PATH") e o Edge ou Chrome.
2. Clone o repositório: `git clone https://github.com/camargo009/Lucas-Projects.git`
3. Abra o PowerShell na pasta `Lucas-Projects\telessaude-fepecs\app`.
4. Se o PowerShell bloquear scripts: `Set-ExecutionPolicy -Scope Process Bypass`
5. `.\iniciar.ps1 -SemTunel` (instala as dependências e sobe o servidor)
6. Abra http://localhost:8080

Sem o script: `python -m pip install -r requirements.txt` e `python server.py`.
Em Linux/macOS: os mesmos dois comandos, usando `python3`.

## Executar
```powershell
cd app
.\iniciar.ps1            # servidor + túnel HTTPS (cloudflared) para o dev remoto
.\iniciar.ps1 -SemTunel  # somente local
```
Acesse http://localhost:8080. Senha de todas as contas: `telessaude`
(e-mails `@telessaude.fepecs`).

| Perfil | Conta | Papel |
|---|---|---|
| Teleconsultor (solicita) | teleconsultor@ (Dra. Beatriz Nogueira, HRAN) | Abre o teleparecer (Fluxo 1, passos 1 a 9), anexa informações pedidas, participa do teleatendimento |
| Médico especialista (responde) | medico@ (Dr. Henrique Matos, Cardiologia) | Analisa (passo 10), decide nos passos 11 a 13, atende o paciente na sala, emite e assina o parecer |
| Gestor / Administrador | gestor@ (Marina Duarte) | Cadastros, agenda, auditoria, integrações, suporte |

## Módulos (conforme documento FEPECS)
Administrativo, Suporte, Teleinterconsultas, Teleconsulta/Telemonitoramento/Teletriagem,
Teleconsultoria/Teleparecer (Fluxo 1 completo), Telereuniões, Telediagnóstico (espirometria),
Interface PEC e-SUS (FHIR Bundle simulado), Assinatura eletrônica (verificação por QR).

## Roteiro sugerido
1. Teleconsultor → **Nova solicitação** → responde o Fluxo 1 (passo 5 "Sim" = assíncrono, formulário com resposta em até 48 h) → envia.
2. Médico especialista → assume (passo 10) → passo 11: **Sim** emite o parecer; **Não** abre o passo 13 com as 4 opções (mais informações, teleatendimento síncrono, fluxo hospitalar, evoluir no prontuário).
3. Caminho presencial no hospital: no passo 6 "Sim" o teleconsultor agenda a teleconsulta; o médico especialista atende o paciente na sala **sem o teleconsultor**, com enfermagem ajudando (link/QR do caso).
   Para vídeo remoto, o dev abre a URL pública como Dr. Henrique.
4. Dr. Henrique emite parecer (use o rascunho do Copiloto), assina, envia ao PEC e encerra.
5. Mostrar documento impresso e a verificação pelo QR.
6. Telediagnóstico: médico especialista lauda a espirometria. Gestor → Auditoria.

## Vídeo remoto
Câmera exige HTTPS: use o túnel do `iniciar.ps1`. No caso, "Definir URL pública"
para o QR/link do paciente usar o domínio do túnel. Redes restritivas podem exigir TURN:
variáveis `TURN_URL`, `TURN_USER`, `TURN_PASS`. Para voltar aos dados iniciais: Admin → Restaurar demonstração.

## Pendências
Substituir `static/img/fepecs.png` pelo logotipo oficial (o atual é recorte de baixa resolução).
