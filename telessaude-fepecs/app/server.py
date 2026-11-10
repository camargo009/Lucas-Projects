"""Telessaúde FEPECS - servidor de demonstração (HTTP + WebSocket + sinalização WebRTC)."""
import asyncio
import hashlib
import io
import json
import os
import secrets
import time
import uuid
from pathlib import Path

from aiohttp import web, WSMsgType
import qrcode
import qrcode.image.svg

BASE = Path(__file__).parent
STATIC = BASE / "static"
DATA_FILE = BASE / "data.json"
H = 3600 * 1000
D = 24 * H

TIPOS = {
    "teleparecer": "TP", "teleinterconsulta": "TI", "teleconsultoria": "TS",
    "teleconsulta": "TC", "teletriagem": "TT", "telemonitoramento": "TM",
}

DB = {}
SESSIONS = {}
CLIENTS = {}   # ws -> peer info
ROOMS = {}     # room -> {peer_id: ws}


def now():
    return int(time.time() * 1000)


def uid(p=""):
    return p + uuid.uuid4().hex[:8]


def at(days=0, hour=9, minute=0):
    t = time.localtime(time.time() + days * 86400)
    return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, 0, 0, -1)) * 1000)


def seed():
    users = [
        dict(id="u-admin", nome="Marina Duarte", email="admin@telessaude.fepecs", perfil="admin", cargo="Coordenação do Núcleo de Telessaúde", unidade="u-nuc"),
        dict(id="u-gestor", nome="Roberto Alencar", email="gestor@telessaude.fepecs", perfil="gestor", cargo="Gerência de Serviços de Telessaúde", unidade="u-nuc"),
        dict(id="u-sol1", nome="Henrique Matos", email="henrique.matos@telessaude.fepecs", perfil="solicitante", cargo="Médico residente, Clínica Médica", unidade="u-hran", crm="CRM-DF 00000"),
        dict(id="u-sol2", nome="Camila Reis", email="camila.reis@telessaude.fepecs", perfil="solicitante", cargo="Médica, Clínica Médica", unidade="u-hrt", crm="CRM-DF 00001"),
        dict(id="u-esp1", nome="Beatriz Nogueira", email="beatriz.nogueira@telessaude.fepecs", perfil="especialista", cargo="Cardiologista", especialidade="Cardiologia", unidade="u-hran", crm="CRM-DF 00002"),
        dict(id="u-esp2", nome="Rafael Teixeira", email="rafael.teixeira@telessaude.fepecs", perfil="especialista", cargo="Pneumologista", especialidade="Pneumologia", unidade="u-hmib", crm="CRM-DF 00003"),
        dict(id="u-esp3", nome="André Lacerda", email="andre.lacerda@telessaude.fepecs", perfil="especialista", cargo="Nefrologista", especialidade="Nefrologia", unidade="u-hrg", crm="CRM-DF 00004"),
        dict(id="u-enf", nome="Patrícia Souza", email="patricia.souza@telessaude.fepecs", perfil="enfermagem", cargo="Enfermeira, Clínica Médica", unidade="u-hran", coren="COREN-DF 00000"),
        dict(id="u-sup", nome="Thiago Ramos", email="suporte@telessaude.fepecs", perfil="suporte", cargo="Suporte técnico (BazeTech)", unidade="u-nuc"),
    ]
    units = [
        dict(id="u-nuc", nome="Núcleo de Telessaúde FEPECS/SES-DF", tipo="Gestão", regiao="Asa Norte", cnes="—"),
        dict(id="u-hran", nome="Hospital Regional da Asa Norte (HRAN)", tipo="Hospital", regiao="Central", cnes="0000001"),
        dict(id="u-hmib", nome="Hospital Materno Infantil de Brasília (HMIB)", tipo="Hospital", regiao="Central", cnes="0000002"),
        dict(id="u-hrt", nome="Hospital Regional de Taguatinga (HRT)", tipo="Hospital", regiao="Oeste", cnes="0000003"),
        dict(id="u-hrg", nome="Hospital Regional do Gama (HRG)", tipo="Hospital", regiao="Sul", cnes="0000004"),
        dict(id="u-ubs1", nome="UBS 1 de Planaltina", tipo="UBS", regiao="Norte", cnes="0000005"),
        dict(id="u-ubs2", nome="UBS 3 de Ceilândia", tipo="UBS", regiao="Oeste", cnes="0000006"),
        dict(id="u-pol", nome="Policlínica de Sobradinho", tipo="Policlínica", regiao="Norte", cnes="0000007"),
    ]
    patients = [
        dict(id="p1", nome="José Antônio Ferreira", nasc="1951-03-14", sexo="M", cns="700 0000 0000 0001", unidade="u-hran", local="Enfermaria 4B, leito 12"),
        dict(id="p2", nome="Maria das Graças Lima", nasc="1964-09-02", sexo="F", cns="700 0000 0000 0002", unidade="u-hrt", local="Clínica Médica, leito 7"),
        dict(id="p3", nome="Ricardo Pires Cunha", nasc="1978-12-21", sexo="M", cns="700 0000 0000 0003", unidade="u-ubs2", local="Ambulatório"),
        dict(id="p4", nome="Ana Beatriz Moura", nasc="1992-06-30", sexo="F", cns="700 0000 0000 0004", unidade="u-ubs1", local="Ambulatório"),
        dict(id="p5", nome="Sebastião Rocha Neto", nasc="1947-01-09", sexo="M", cns="700 0000 0000 0005", unidade="u-hrg", local="UTI, leito 3"),
        dict(id="p6", nome="Luciana Barros Gomes", nasc="1985-04-17", sexo="F", cns="700 0000 0000 0006", unidade="u-hran", local="Enfermaria 2A, leito 5"),
    ]

    def ev(autor, tipo, texto, ts):
        return dict(ts=ts, autor=autor, tipo=tipo, texto=texto)

    c = []

    def case(tipo, n, **kw):
        base = dict(
            id=uid("c-"), tipo=tipo, protocolo=f"{TIPOS[tipo]}-2026-{n:04d}", status="aguardando", prioridade="Rotina",
            modalidade="assincrona", hospitalar=True, anexos=[], timeline=[], resposta=None, agendamento=None,
            sala="r-" + secrets.token_hex(5), pec=None, transcricao=[], especialista=None, anamnese="", exame_clinico="",
            hipotese="", duvida="", queixa="", criado=now(), prazo=None, info_pedida=None,
        )
        base.update(kw)
        c.append(base)
        return base

    a = case("teleparecer", 1, paciente="p1", solicitante="u-sol1", especialidade="Cardiologia", unidade="u-hran",
             prioridade="Urgente", queixa="Dispneia progressiva e edema de MMII há 5 dias",
             anamnese="Paciente masculino, 74 anos, hipertenso e diabético, internado por descompensação de insuficiência cardíaca. Refere dispneia aos mínimos esforços, ortopneia e edema bilateral de membros inferiores. Em uso de furosemida 40 mg EV 12/12h com resposta parcial.",
             exame_clinico="PA 150/90 mmHg, FC 104 bpm, SpO2 92% em ar ambiente, FR 24 irpm. Turgência jugular a 45 graus, estertores crepitantes em bases, edema 3+/4+ bilateral.",
             hipotese="Insuficiência cardíaca descompensada", duvida="Ajuste do tratamento diurético e necessidade de ecocardiograma?",
             criado=now() - 20 * H, prazo=now() + 28 * H)
    a["timeline"] = [ev("u-sol1", "criacao", "Teleparecer solicitado ao serviço de Cardiologia (fluxo assíncrono, prazo de 48 h).", a["criado"])]

    b = case("teleparecer", 2, paciente="p2", solicitante="u-sol2", especialista="u-esp2", especialidade="Pneumologia", unidade="u-hrt",
             status="info_solicitada", queixa="Tosse crônica com hemoptise esporádica",
             anamnese="Feminina, 61 anos, ex-tabagista (30 maços/ano), internada para investigação de tosse com hemoptise esporádica há 3 semanas.",
             exame_clinico="SpO2 95% em ar ambiente, murmúrio vesicular diminuído em ápice direito. Sem febre.",
             hipotese="Suspeita de neoplasia pulmonar versus tuberculose", duvida="Quais exames complementares priorizar?",
             criado=now() - 30 * H, prazo=now() + 18 * H,
             info_pedida="Enviar laudo da radiografia de tórax e resultado da baciloscopia, se disponíveis.")
    b["timeline"] = [ev("u-sol2", "criacao", "Teleparecer solicitado.", b["criado"] ),
                     ev("u-esp2", "info", "Solicitado mais informações: enviar laudo da radiografia de tórax e resultado da baciloscopia.", now() - 6 * H)]

    d = case("teleparecer", 3, paciente="p5", solicitante="u-sol1", especialista="u-esp3", especialidade="Nefrologia", unidade="u-hrg",
             status="respondido", prioridade="Prioritário", queixa="Elevação de creatinina em paciente de UTI",
             anamnese="Masculino, 78 anos, UTI por pneumonia grave. Creatinina de 1,1 para 2,4 mg/dL em 48 h, diurese reduzida.",
             exame_clinico="Hipotenso em uso de noradrenalina, mucosas úmidas, edema discreto.",
             hipotese="Lesão renal aguda", duvida="Indicação de terapia renal substitutiva?",
             criado=now() - 3 * D, prazo=now() - 1 * D)
    d["resposta"] = dict(opcao="resolvido", texto="Quadro compatível com lesão renal aguda pré-renal/NTA em contexto séptico. Sem indicação de terapia renal substitutiva no momento: sem acidose grave, hipercalemia ou sobrecarga refratária. Otimizar volemia e pressão de perfusão, suspender nefrotóxicos e reavaliar creatinina e diurese em 24 h. Nova discussão se piora.",
                         por="u-esp3", ts=now() - 2 * D,
                         assinatura=dict(hash=hashlib.sha256(b"seed-1").hexdigest(), por="u-esp3", ts=now() - 2 * D, tipo="ICP-Brasil (simulada)"))
    d["timeline"] = [ev("u-sol1", "criacao", "Teleparecer solicitado.", d["criado"]),
                     ev("u-esp3", "resposta", "Parecer emitido e assinado: resolvido e evoluído no prontuário eletrônico.", now() - 2 * D)]
    d["pec"] = dict(status="enviado", id="Bundle/" + uid(), ts=now() - 2 * D)

    e = case("teleparecer", 4, paciente="p6", solicitante="u-sol1", especialista="u-esp1", especialidade="Cardiologia", unidade="u-hran",
             status="teleatendimento_agendado", modalidade="sincrona", prioridade="Urgente", queixa="Síncope de repetição",
             anamnese="Feminina, 39 anos, dois episódios de síncope em 48 h sem pródromos. Sem cardiopatia conhecida.",
             exame_clinico="PA 110/70, FC 58 bpm, ECG com bloqueio atrioventricular de 1º grau.",
             hipotese="Síncope com suspeita de causa arritmogênica", duvida="Necessidade de monitorização contínua e investigação?",
             criado=now() - 8 * H, prazo=now() + 40 * H)
    e["agendamento"] = dict(inicio=at(0, 15, 0), fim=at(0, 15, 30), slot="s-seed")
    e["timeline"] = [ev("u-sol1", "criacao", "Teleparecer solicitado.", e["criado"]),
                     ev("u-esp1", "agenda", "Marcado teleatendimento síncrono com a presença do paciente.", now() - 2 * H)]

    f = case("teleinterconsulta", 5, paciente="p3", solicitante="u-sol2", especialista="u-esp3", especialidade="Nefrologia", unidade="u-ubs2",
             hospitalar=False, status="em_analise", queixa="Diabetes tipo 2 com proteinúria persistente",
             anamnese="Masculino, 45 anos, DM2 há 12 anos, HAS. Relação albumina/creatinina de 420 mg/g em duas amostras.",
             exame_clinico="PA 138/86, IMC 31, sem edema.", hipotese="Doença renal do diabetes",
             duvida="Iniciar iSGLT2? Quando encaminhar presencialmente?", criado=now() - 26 * H, prazo=now() + 22 * H)
    f["timeline"] = [ev("u-sol2", "criacao", "Teleinterconsulta solicitada pela APS.", f["criado"]),
                     ev("u-esp3", "analise", "Solicitação assumida para análise.", now() - 5 * H)]

    g = case("teletriagem", 6, paciente="p4", solicitante="u-sol2", especialidade="Pneumologia", unidade="u-ubs1", hospitalar=False,
             queixa="Tosse seca há 6 semanas", anamnese="Feminina, 33 anos, não fumante, tosse seca persistente, sem febre.",
             exame_clinico="Ausculta pulmonar normal.", hipotese="Asma de início tardio?", duvida="Encaminhar para espirometria?",
             criado=now() - 4 * H, prazo=now() + 44 * H)
    g["timeline"] = [ev("u-sol2", "criacao", "Teletriagem solicitada.", g["criado"])]

    h = case("teleconsulta", 7, paciente="p3", solicitante="u-sol2", especialista="u-esp3", especialidade="Nefrologia", unidade="u-ubs2",
             hospitalar=False, modalidade="sincrona", status="teleatendimento_agendado", queixa="Retorno de seguimento, doença renal crônica",
             anamnese="Retorno após ajuste terapêutico.", criado=now() - 2 * D, prazo=now() + 1 * D)
    h["agendamento"] = dict(inicio=at(1, 10, 0), fim=at(1, 10, 30), slot="s-seed2")
    h["timeline"] = [ev("u-sol2", "criacao", "Teleconsulta de retorno agendada.", h["criado"])]

    slots = []
    for esp in ("u-esp1", "u-esp2", "u-esp3"):
        for day in range(0, 5):
            for hr in (9, 10, 14, 15, 16):
                slots.append(dict(id=uid("s-"), especialista=esp, inicio=at(day, hr, 0), fim=at(day, hr, 30), status="livre", caso=None))
    slots = [s for s in slots if s["inicio"] > now()]

    exams = [
        dict(id="e1", paciente="p4", tipo="Espirometria", coleta="u-ubs1", status="aguardando", solicitado=now() - 5 * H,
             params=dict(cvf=3.2, vef1=2.1, pef=5.1, cvf_prev=3.6, vef1_prev=3.0), pdf="espirometria-p4.pdf", laudo=None, laudista=None),
        dict(id="e2", paciente="p3", tipo="Espirometria", coleta="u-ubs2", status="aguardando", solicitado=now() - 26 * H,
             params=dict(cvf=4.2, vef1=3.5, pef=8.4, cvf_prev=4.5, vef1_prev=3.7), pdf="espirometria-p3.pdf", laudo=None, laudista=None),
        dict(id="e3", paciente="p2", tipo="Espirometria", coleta="u-hrt", status="laudado", solicitado=now() - 3 * D,
             params=dict(cvf=2.3, vef1=1.2, pef=3.4, cvf_prev=3.0, vef1_prev=2.4), pdf="espirometria-p2.pdf",
             laudo="Distúrbio ventilatório obstrutivo de grau moderado, sem resposta significativa ao broncodilatador. Correlacionar com quadro clínico.", laudista="u-esp2"),
    ]
    tickets = [
        dict(id="t1", titulo="Não consigo anexar PDF acima de 10 MB", categoria="Anexos", prioridade="Média", status="aberto", autor="u-sol2",
             criado=now() - 6 * H, respostas=[dict(autor="u-sup", ts=now() - 5 * H, texto="O limite do piloto é 10 MB por arquivo. Comprima o PDF ou divida em duas partes.")]),
        dict(id="t2", titulo="Solicitação de perfil de especialista para novo profissional", categoria="Acesso", prioridade="Baixa", status="em_atendimento", autor="u-gestor",
             criado=now() - 2 * D, respostas=[]),
    ]
    meetings = [
        dict(id="m1", titulo="Discussão de casos: Insuficiência Cardíaca", tipo="telegrupo", inicio=at(1, 14, 0), anfitriao="u-esp1",
             participantes=["u-sol1", "u-sol2", "u-enf"], sala="r-" + secrets.token_hex(5), pauta="Manejo da IC descompensada na enfermaria e critérios de alta."),
        dict(id="m2", titulo="Reunião de alinhamento do Núcleo", tipo="reuniao", inicio=at(0, 17, 0), anfitriao="u-admin",
             participantes=["u-gestor", "u-sup"], sala="r-" + secrets.token_hex(5), pauta="Indicadores do piloto e próximos módulos."),
    ]
    audit = [dict(ts=now() - 3 * H, user="u-esp3", acao="Login", alvo="Sessão", ip="10.0.4.21"),
             dict(ts=now() - 2 * H, user="u-esp1", acao="Agendamento de teleatendimento", alvo=e["protocolo"], ip="10.0.7.8")]
    return dict(users=users, units=units, patients=patients, cases=c, slots=slots, exams=exams, tickets=tickets,
                meetings=meetings, audit=audit, notifs=[], contador=7)


def save():
    DATA_FILE.write_text(json.dumps(DB, ensure_ascii=False), encoding="utf-8")


def load():
    global DB
    if DATA_FILE.exists():
        try:
            DB = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return
        except Exception:
            pass
    DB = seed()
    save()


def user_by(uid_):
    return next((u for u in DB["users"] if u["id"] == uid_), None)


def case_by(cid):
    return next((c for c in DB["cases"] if c["id"] == cid), None)


def audit(user, acao, alvo, request=None):
    ip = request.remote if request is not None else "-"
    DB["audit"].insert(0, dict(ts=now(), user=user["id"] if user else "-", acao=acao, alvo=alvo, ip=ip))
    del DB["audit"][300:]


async def push(event):
    msg = json.dumps(event)
    for ws, info in list(CLIENTS.items()):
        if info.get("kind") == "app":
            try:
                await ws.send_str(msg)
            except Exception:
                pass


async def notify(to_ids, texto, link=None, caso=None):
    for t in to_ids:
        DB["notifs"].insert(0, dict(id=uid("n-"), para=t, texto=texto, link=link, ts=now(), lida=False))
    del DB["notifs"][200:]
    await push(dict(t="notify", para=list(to_ids), texto=texto, link=link))


def auth(request):
    tok = request.headers.get("Authorization", "").replace("Bearer ", "") or request.query.get("token", "")
    u = SESSIONS.get(tok)
    if not u:
        raise web.HTTPUnauthorized(text=json.dumps({"erro": "Sessão expirada"}), content_type="application/json")
    return user_by(u)


def pub_user(u):
    return {k: v for k, v in u.items() if k != "senha"}


def jr(data, status=200):
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False))


async def login(request):
    b = await request.json()
    u = next((x for x in DB["users"] if x["email"].lower() == b.get("email", "").lower()), None)
    if not u or b.get("senha") != "telessaude":
        audit(None, "Falha de login", b.get("email", ""), request)
        return jr({"erro": "Usuário ou senha inválidos."}, 401)
    tok = secrets.token_urlsafe(24)
    SESSIONS[tok] = u["id"]
    audit(u, "Login", "Sessão", request)
    save()
    return jr({"token": tok, "user": pub_user(u)})


async def logout(request):
    u = auth(request)
    SESSIONS.pop(request.headers.get("Authorization", "").replace("Bearer ", ""), None)
    audit(u, "Logout", "Sessão", request)
    return jr({"ok": True})


async def state(request):
    u = auth(request)
    out = dict(me=pub_user(u), users=[pub_user(x) for x in DB["users"]], units=DB["units"], patients=DB["patients"],
               cases=DB["cases"], slots=DB["slots"], exams=DB["exams"], tickets=DB["tickets"], meetings=DB["meetings"],
               notifs=[n for n in DB["notifs"] if n["para"] == u["id"]][:30], now=now())
    out["audit"] = DB["audit"] if u["perfil"] in ("admin", "gestor") else []
    return jr(out)


def add_event(c, user, tipo, texto):
    c["timeline"].append(dict(ts=now(), autor=user["id"], tipo=tipo, texto=texto))


async def create_case(request):
    u = auth(request)
    b = await request.json()
    tipo = b.get("tipo", "teleparecer")
    DB["contador"] += 1
    pac = b.get("paciente")
    if b.get("novo_paciente"):
        np = b["novo_paciente"]
        pac = uid("p-")
        DB["patients"].append(dict(id=pac, nome=np["nome"], nasc=np.get("nasc", ""), sexo=np.get("sexo", "M"), cns=np.get("cns", "—"),
                                   unidade=u["unidade"], local=np.get("local", "")))
    c = dict(
        id=uid("c-"), tipo=tipo, protocolo=f"{TIPOS.get(tipo, 'TX')}-2026-{DB['contador']:04d}", status="aguardando",
        prioridade=b.get("prioridade", "Rotina"), modalidade=b.get("modalidade", "assincrona"), hospitalar=bool(b.get("hospitalar")),
        anexos=b.get("anexos", []), timeline=[], resposta=None, agendamento=None, sala="r-" + secrets.token_hex(5), pec=None,
        transcricao=[], especialista=b.get("especialista") or None, anamnese=b.get("anamnese", ""), exame_clinico=b.get("exame_clinico", ""),
        hipotese=b.get("hipotese", ""), duvida=b.get("duvida", ""), queixa=b.get("queixa", ""), criado=now(), prazo=now() + 48 * H,
        info_pedida=None, paciente=pac, solicitante=u["id"], especialidade=b.get("especialidade", ""), unidade=u["unidade"])
    add_event(c, u, "criacao", f"{tipo.capitalize()} solicitado ao serviço de {c['especialidade'] or 'especialidade'}"
                               + (" (fluxo assíncrono, prazo de 48 h)." if c["modalidade"] == "assincrona" else " (teleatendimento síncrono)."))
    slot_id = b.get("slot")
    if slot_id:
        s = next((x for x in DB["slots"] if x["id"] == slot_id and x["status"] == "livre"), None)
        if s:
            s["status"], s["caso"] = "reservado", c["id"]
            c["especialista"] = s["especialista"]
            c["status"] = "teleatendimento_agendado"
            c["agendamento"] = dict(inicio=s["inicio"], fim=s["fim"], slot=s["id"])
            add_event(c, u, "agenda", "Teleatendimento hospitalar agendado na agenda do especialista.")
    DB["cases"].insert(0, c)
    audit(u, "Criação de " + tipo, c["protocolo"], request)
    destino = [c["especialista"]] if c["especialista"] else [x["id"] for x in DB["users"] if x["perfil"] == "especialista" and x.get("especialidade") == c["especialidade"]]
    await notify(destino, f"Novo {tipo} ({c['prioridade']}): {c['protocolo']}", f"/casos/{c['id']}")
    save()
    await push(dict(t="state"))
    return jr(c)


async def case_action(request):
    u = auth(request)
    c = case_by(request.match_info["cid"])
    if not c:
        raise web.HTTPNotFound()
    act = request.match_info["act"]
    b = await request.json() if request.can_read_body else {}
    pend = []
    if act == "assumir":
        c["especialista"] = u["id"]
        c["status"] = "em_analise"
        add_event(c, u, "analise", "Solicitação assumida para análise.")
        pend = [c["solicitante"]]
    elif act == "solicitar_info":
        c["status"] = "info_solicitada"
        c["info_pedida"] = b.get("texto", "")
        c["especialista"] = c["especialista"] or u["id"]
        add_event(c, u, "info", "Solicitado mais informações: " + c["info_pedida"])
        pend = [c["solicitante"]]
    elif act == "enviar_info":
        c["status"] = "em_analise"
        c["anexos"] += b.get("anexos", [])
        add_event(c, u, "info", "Informações complementares enviadas: " + b.get("texto", ""))
        pend = [c["especialista"]] if c["especialista"] else []
    elif act == "agendar":
        s = next((x for x in DB["slots"] if x["id"] == b.get("slot") and x["status"] == "livre"), None)
        if not s:
            return jr({"erro": "Horário indisponível."}, 409)
        s["status"], s["caso"] = "reservado", c["id"]
        c["especialista"] = s["especialista"]
        c["modalidade"] = "sincrona"
        c["status"] = "teleatendimento_agendado"
        c["agendamento"] = dict(inicio=s["inicio"], fim=s["fim"], slot=s["id"])
        add_event(c, u, "agenda", "Marcado teleatendimento síncrono com a presença do paciente.")
        pend = [c["solicitante"], c["especialista"]]
    elif act == "iniciar_atendimento":
        c["status"] = "em_atendimento"
        add_event(c, u, "atendimento", "Teleatendimento iniciado.")
        pend = [x for x in (c["solicitante"], c["especialista"]) if x and x != u["id"]]
    elif act == "salvar_transcricao":
        c["transcricao"] = b.get("linhas", [])
        add_event(c, u, "atendimento", "Transcrição do teleatendimento anexada ao caso.")
    elif act == "responder":
        op = b.get("opcao", "resolvido")
        c["resposta"] = dict(opcao=op, texto=b.get("texto", ""), por=u["id"], ts=now(), assinatura=None)
        c["especialista"] = c["especialista"] or u["id"]
        rotulos = dict(resolvido="Teleparecer resolvido e evoluído no prontuário eletrônico", hospitalar="Seguir fluxo hospitalar já estabelecido",
                       evoluir="Evoluir teleparecer no prontuário")
        c["status"] = "respondido"
        add_event(c, u, "resposta", f"Parecer emitido: {rotulos.get(op, op)}.")
        pend = [c["solicitante"]]
    elif act == "assinar":
        if not c["resposta"]:
            return jr({"erro": "Sem parecer a assinar."}, 400)
        payload = f"{c['protocolo']}|{c['resposta']['texto']}|{u['id']}|{now()}".encode()
        c["resposta"]["assinatura"] = dict(hash=hashlib.sha256(payload).hexdigest(), por=u["id"], ts=now(), tipo=b.get("tipo", "ICP-Brasil (simulada)"))
        add_event(c, u, "assinatura", "Parecer assinado eletronicamente.")
    elif act == "sync_pec":
        c["pec"] = dict(status="enviado", id="Bundle/" + uid(), ts=now())
        add_event(c, u, "pec", "Evolução enviada ao PEC e-SUS APS (homologação, simulada).")
    elif act == "encerrar":
        c["status"] = "encerrado"
        add_event(c, u, "encerramento", "Pedido encerrado no sistema de Telessaúde.")
    elif act == "prioridade":
        c["prioridade"] = b.get("prioridade", c["prioridade"])
        add_event(c, u, "analise", f"Prioridade alterada para {c['prioridade']}.")
    else:
        raise web.HTTPBadRequest()
    audit(u, f"Caso: {act}", c["protocolo"], request)
    if pend:
        await notify([p for p in pend if p and p != u["id"]], f"{c['protocolo']}: {c['timeline'][-1]['texto'][:90]}", f"/casos/{c['id']}")
    save()
    await push(dict(t="state"))
    return jr(c)


async def new_exam(request):
    u = auth(request)
    b = await request.json()
    ex = dict(id=uid("e-"), paciente=b["paciente"], tipo="Espirometria", coleta=u["unidade"], status="aguardando", solicitado=now(),
              params=b["params"], pdf="espirometria.pdf", laudo=None, laudista=None)
    DB["exams"].insert(0, ex)
    audit(u, "Exame enviado para laudo", ex["id"], request)
    await notify([x["id"] for x in DB["users"] if x.get("especialidade") == "Pneumologia"], "Nova espirometria aguardando laudo", "/telediagnostico")
    save()
    await push(dict(t="state"))
    return jr(ex)


async def laudo(request):
    u = auth(request)
    b = await request.json()
    ex = next((x for x in DB["exams"] if x["id"] == request.match_info["eid"]), None)
    if not ex:
        raise web.HTTPNotFound()
    ex["laudo"], ex["laudista"], ex["status"] = b["texto"], u["id"], "laudado"
    ex["assinatura"] = dict(hash=hashlib.sha256(f"{ex['id']}|{b['texto']}|{now()}".encode()).hexdigest(), por=u["id"], ts=now(), tipo="ICP-Brasil (simulada)")
    audit(u, "Laudo emitido", ex["id"], request)
    save()
    await push(dict(t="state"))
    return jr(ex)


async def new_ticket(request):
    u = auth(request)
    b = await request.json()
    t = dict(id=uid("t-"), titulo=b["titulo"], categoria=b.get("categoria", "Outros"), prioridade=b.get("prioridade", "Média"),
             status="aberto", autor=u["id"], criado=now(), respostas=[dict(autor=u["id"], ts=now(), texto=b.get("descricao", ""))] if b.get("descricao") else [])
    DB["tickets"].insert(0, t)
    audit(u, "Chamado aberto", t["titulo"], request)
    await notify([x["id"] for x in DB["users"] if x["perfil"] == "suporte"], f"Novo chamado: {t['titulo']}", "/suporte")
    save()
    await push(dict(t="state"))
    return jr(t)


async def ticket_reply(request):
    u = auth(request)
    b = await request.json()
    t = next((x for x in DB["tickets"] if x["id"] == request.match_info["tid"]), None)
    if not t:
        raise web.HTTPNotFound()
    if b.get("texto"):
        t["respostas"].append(dict(autor=u["id"], ts=now(), texto=b["texto"]))
    if b.get("status"):
        t["status"] = b["status"]
    save()
    await push(dict(t="state"))
    return jr(t)


async def new_meeting(request):
    u = auth(request)
    b = await request.json()
    m = dict(id=uid("m-"), titulo=b["titulo"], tipo=b.get("tipo", "reuniao"), inicio=b["inicio"], anfitriao=u["id"],
             participantes=b.get("participantes", []), sala="r-" + secrets.token_hex(5), pauta=b.get("pauta", ""))
    DB["meetings"].insert(0, m)
    audit(u, "Telerreunião criada", m["titulo"], request)
    await notify(m["participantes"], f"Convite: {m['titulo']}", f"/reunioes")
    save()
    await push(dict(t="state"))
    return jr(m)


async def new_user(request):
    u = auth(request)
    if u["perfil"] != "admin":
        raise web.HTTPForbidden()
    b = await request.json()
    nu = dict(id=uid("u-"), nome=b["nome"], email=b["email"], perfil=b["perfil"], cargo=b.get("cargo", ""), unidade=b["unidade"],
              especialidade=b.get("especialidade", ""))
    DB["users"].append(nu)
    audit(u, "Usuário criado", nu["email"], request)
    save()
    await push(dict(t="state"))
    return jr(pub_user(nu))


async def reset(request):
    u = auth(request)
    if u["perfil"] != "admin":
        raise web.HTTPForbidden()
    global DB
    DB = seed()
    save()
    await push(dict(t="state"))
    return jr({"ok": True})


async def qr(request):
    img = qrcode.make(request.query.get("text", ""), image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return web.Response(body=buf.getvalue(), content_type="image/svg+xml")


async def verify(request):
    h = request.match_info["h"]
    for c in DB["cases"]:
        a = (c.get("resposta") or {}).get("assinatura")
        if a and a["hash"] == h:
            u = user_by(a["por"])
            return jr(dict(valido=True, documento="Teleparecer " + c["protocolo"], por=u["nome"], crm=u.get("crm", ""), ts=a["ts"], tipo=a["tipo"]))
    for e in DB["exams"]:
        a = e.get("assinatura")
        if a and a["hash"] == h:
            u = user_by(a["por"])
            return jr(dict(valido=True, documento="Laudo de espirometria " + e["id"], por=u["nome"], crm=u.get("crm", ""), ts=a["ts"], tipo=a["tipo"]))
    return jr(dict(valido=False))


async def ice(request):
    servers = [{"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]}]
    if os.environ.get("TURN_URL"):
        servers.append({"urls": os.environ["TURN_URL"].split(","), "username": os.environ.get("TURN_USER", ""), "credential": os.environ.get("TURN_PASS", "")})
    return jr(dict(iceServers=servers))


def room_info(room):
    for c in DB["cases"]:
        if c["sala"] == room:
            p = next((x for x in DB["patients"] if x["id"] == c["paciente"]), {})
            return dict(tipo="caso", titulo=f"{c['tipo'].capitalize()} {c['protocolo']}", caso=c["id"], paciente=p.get("nome", "").split(" ")[0])
    for m in DB["meetings"]:
        if m["sala"] == room:
            return dict(tipo="reuniao", titulo=m["titulo"], reuniao=m["id"])
    return None


async def room_get(request):
    info = room_info(request.match_info["room"])
    if not info:
        return jr({"erro": "Sala não encontrada"}, 404)
    return jr(info)


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    tok = request.query.get("token")
    u = user_by(SESSIONS[tok]) if tok in SESSIONS else None
    info = dict(id=uid("w-"), kind="app" if u else "guest", user=u["id"] if u else None,
                name=u["nome"] if u else request.query.get("nome", "Convidado")[:40], perfil=u["perfil"] if u else "paciente", room=None)
    CLIENTS[ws] = info
    await ws.send_str(json.dumps(dict(t="hello", id=info["id"])))
    try:
        async for m in ws:
            if m.type != WSMsgType.TEXT:
                continue
            d = json.loads(m.data)
            t = d.get("t")
            if t == "join":
                room = d["room"]
                if not room_info(room):
                    await ws.send_str(json.dumps(dict(t="error", msg="Sala inexistente")))
                    continue
                info["room"] = room
                peers = ROOMS.setdefault(room, {})
                lista = [dict(id=pid, name=CLIENTS[w]["name"], perfil=CLIENTS[w]["perfil"]) for pid, w in peers.items() if w in CLIENTS]
                await ws.send_str(json.dumps(dict(t="peers", peers=lista)))
                for w in list(peers.values()):
                    await w.send_str(json.dumps(dict(t="peer-joined", peer=dict(id=info["id"], name=info["name"], perfil=info["perfil"]))))
                peers[info["id"]] = ws
            elif t in ("signal", "chat", "transcript", "media-state") and info["room"]:
                peers = ROOMS.get(info["room"], {})
                d["from"] = info["id"]
                d["name"] = info["name"]
                if t == "signal":
                    w = peers.get(d.get("to"))
                    if w:
                        await w.send_str(json.dumps(d))
                else:
                    for pid, w in list(peers.items()):
                        if pid != info["id"]:
                            await w.send_str(json.dumps(d))
    finally:
        CLIENTS.pop(ws, None)
        if info["room"]:
            peers = ROOMS.get(info["room"], {})
            peers.pop(info["id"], None)
            for w in list(peers.values()):
                try:
                    await w.send_str(json.dumps(dict(t="peer-left", id=info["id"])))
                except Exception:
                    pass
    return ws


@web.middleware
async def nocache(request, handler):
    resp = await handler(request)
    if request.path.startswith("/js") or request.path.startswith("/css") or request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


async def index(request):
    return web.FileResponse(STATIC / "index.html")


def make_app():
    app = web.Application(middlewares=[nocache], client_max_size=30 * 1024 * 1024)
    r = app.router
    r.add_post("/api/login", login)
    r.add_post("/api/logout", logout)
    r.add_get("/api/state", state)
    r.add_post("/api/cases", create_case)
    r.add_post("/api/cases/{cid}/{act}", case_action)
    r.add_post("/api/exams", new_exam)
    r.add_post("/api/exams/{eid}/laudo", laudo)
    r.add_post("/api/tickets", new_ticket)
    r.add_post("/api/tickets/{tid}/reply", ticket_reply)
    r.add_post("/api/meetings", new_meeting)
    r.add_post("/api/users", new_user)
    r.add_post("/api/reset", reset)
    r.add_get("/api/qr", qr)
    r.add_get("/api/verify/{h}", verify)
    r.add_get("/api/ice", ice)
    r.add_get("/api/room/{room}", room_get)
    r.add_get("/ws", ws_handler)
    r.add_get("/", index)
    r.add_static("/", STATIC, show_index=False)
    return app


if __name__ == "__main__":
    load()
    port = int(os.environ.get("PORT", "8080"))
    print(f"Telessaúde FEPECS em http://localhost:{port}")
    web.run_app(make_app(), host="0.0.0.0", port=port, print=None)
