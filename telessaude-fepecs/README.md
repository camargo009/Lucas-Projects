# Telessaúde FEPECS — Demonstração (BazeTech)

Protótipo funcional para a apresentação de 23/11/2026. Todos os dados são fictícios.
PEC e-SUS e assinatura ICP-Brasil são **simulados** (hash SHA-256 + página de verificação).

## Executar
```powershell
cd app
.\iniciar.ps1            # servidor + túnel HTTPS (cloudflared) para o dev remoto
.\iniciar.ps1 -SemTunel  # somente local
```
Acesse http://localhost:8080. Senha de todas as contas: `telessaude`
(e-mails `@telessaude.fepecs`).

| Perfil | Conta |
|---|---|
| Administrador / Gestor | admin@ / gestor@ |
| Solicitante | henrique.matos@ (HRAN), camila.reis@ (HRT) |
| Especialista | beatriz.nogueira@ (Cardiologia), andre.lacerda@ (Nefrologia) |
| Laudista (espirometria) | rafael.teixeira@ |
| Enfermagem / Suporte | patricia.souza@ / suporte@ |

## Módulos (conforme documento FEPECS)
Administrativo, Suporte, Teleinterconsultas, Teleconsulta/Telemonitoramento/Teletriagem,
Teleconsultoria/Teleparecer (Fluxo 1 completo), Telereuniões, Telediagnóstico (espirometria),
Interface PEC e-SUS (FHIR Bundle simulado), Assinatura eletrônica (verificação por QR).

## Roteiro sugerido
1. Henrique (solicitante) → **Novo caso** → percorre o Fluxo 1 → envia.
2. Beatriz (especialista) → assume → solicita informação → Henrique responde.
3. Agendar teleparecer → **Entrar na sala**. O dev remoto abre a URL pública e
   entra como Henrique; o paciente entra pelo link/QR do caso (sem login).
4. Beatriz emite parecer (use o rascunho do Copiloto), assina, envia ao PEC e encerra.
5. Mostrar documento impresso e a verificação pelo QR.
6. Telediagnóstico: Rafael lauda a espirometria. Admin → Auditoria.

## Vídeo remoto
Câmera exige HTTPS: use o túnel do `iniciar.ps1`. No caso, "Definir URL pública"
para o QR/link do paciente usar o domínio do túnel. Redes restritivas podem exigir TURN:
variáveis `TURN_URL`, `TURN_USER`, `TURN_PASS`. Para voltar aos dados iniciais: Admin → Restaurar demonstração.

## Pendências
Substituir `static/img/fepecs.png` pelo logotipo oficial (o atual é recorte de baixa resolução).
