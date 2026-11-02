# Painel Projeto Mais Especialistas (ATEM/PROADI-SUS, HAOC)

Painel em **Python + Streamlit + Plotly**, em português, para acompanhar consultas e procedimentos dos especialistas.

- **Especialista**: login por e-mail/senha; vê somente os próprios dados (KPIs, evolução mensal/semanal, top procedimentos e CIDs, dificuldade, mentorias, posição opcional no ranking).
- **Supervisor** (mentores + admin): visão geral, ranking total/por especialidade/por mentor, comparativos, alertas de baixa atividade, drill-down por especialista, filtros de período, especialidade e mentor.
- Abas `Desistencia N` ficam **fora de KPIs e rankings** e aparecem na aba *Status*.

## Instalação e execução

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
# 1. coloque o Excel em data/acompanhamento.xlsx (a pasta data/ é ignorada pelo git)
# 2. (opcional) crie data/supervisores.csv com colunas nome,email dos mentores
# 3. gere os usuários
.\.venv\Scripts\python scripts\gerar_usuarios.py --admin "admin@dominio.com:Nome do Admin"
# 4. rode
.\.venv\Scripts\streamlit run app.py
.\.venv\Scripts\python -m pytest
```

`gerar_usuarios.py` cria `data/usuarios.json` (apenas **hashes bcrypt**) e `data/senhas_iniciais.csv` (senhas em texto, só dos usuários novos — distribua e apague o arquivo). Usuários existentes não são alterados; rodar de novo só adiciona os novos. Especialistas são criados a partir do e-mail da aba; supervisores a partir de `supervisores.csv` e `--admin`.

## Fontes de dados (`atem/datasource.py`)

Interface `DataSource.load() -> Dataset`. Escolha por `DATA_SOURCE`:

| Variável (env ou `.streamlit/secrets.toml`) | Uso |
|---|---|
| `DATA_SOURCE` | `excel` (padrão), `redcap` (registros estruturados) ou `redcap_files` (anexos) |
| `EXCEL_PATH` | caminho do Excel (padrão `data/acompanhamento.xlsx`) |
| `CURSO_PATHS` | planilhas do curso (EAD), separadas por vírgula (padrão: `data/curso_*.xlsx`) |
| `REDCAP_URL`, `REDCAP_TOKEN` | API do REDCap (token **nunca** no código) |
| `REDCAP_CACHE_TTL` | cache em segundos (padrão 60) |
| `REDCAP_FIELD_MAP` | JSON `{campo_padrão: nome_real_no_redcap}` |
| `REDCAP_UPLOAD_FORM` | formulário dos anexos (padrão `upload_docs`) |
| `REDCAP_ATTENDANCE_FIELD` | upload de atendimentos (padrão `atendimento_especialistas`) |
| `REDCAP_COURSE_FIELD` | upload do curso (padrão `curso_especialistas`) |
| `REDCAP_COURSE_FIELDS` | JSON `{campo_upload: nome_do_curso}` para uploads separados; tem prioridade sobre o campo único |
| `ATEM_USERS_FILE` | padrão `data/usuarios.json` |
| `ATEM_USERS_JSON` | JSON de contas com hashes bcrypt nos secrets; prioridade sobre o arquivo local |
| `AUTH_PROVIDER` | `local` (padrão) ou `supabase`; Supabase nunca usa contas locais como alternativa |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | URL do projeto e chave publicável; não usar chave secreta ou `service_role` |

**Curso (EAD)**: as planilhas `curso_*.xlsx` (uma aba por fotografia semanal, ex. `L11 - 26.10`; a aba `BASE` e dados pessoais como CPF/telefone são ignorados) alimentam a aba **Curso** do supervisor e **Meu curso** do especialista. O vínculo com o especialista é por e-mail e, na falta, por nome. No REDCap, o curso é lido do mesmo export, com um registro por aluno × atividade × fotografia e os campos `curso_nome, curso_email, curso_curso, curso_modulo, curso_atividade, curso_concluido, curso_acesso, curso_data, curso_rotulo` (também ajustáveis via `REDCAP_FIELD_MAP`). Os dados são consultados com cache de 60 s; o botão "Atualizar dados" força nova consulta e a barra lateral mostra a hora da última leitura.

Na visão geral do supervisor, alunos vinculados a abas de desistência ficam fora
do curso, dos indicadores e dos rankings de atendimentos.

**RedcapSource**: usa *Export Records* (`content=record`, `type=flat`). Espera registros planos, um por atividade/mentoria, com os campos de `CAMPOS_REDCAP_PADRAO` (nome, email, especialidade, mentor, status, cid, procedimento, data, mentoria_mes…). Ajuste com `REDCAP_FIELD_MAP`. **Ainda não foi testado contra um REDCap real** (apenas com resposta simulada): valide o mapeamento de campos com seu projeto.

### Planilhas anexadas ao REDCap

Para usar os uploads sem depender de planilhas locais, configure `.streamlit/secrets.toml`
(ignorado pelo Git):

```toml
DATA_SOURCE = "redcap_files"
REDCAP_URL = "https://seu-servidor/redcap/api/"
REDCAP_TOKEN = "configure-o-token-localmente"
REDCAP_UPLOAD_FORM = "upload_docs"
REDCAP_ATTENDANCE_FIELD = "atendimento_especialistas"
REDCAP_COURSE_FIELDS = '{"curso_especialistas_onco":"Oncologia","curso_especialistas_anestesio":"Anestesiologia"}'
```

O token precisa de permissão de exportação de registros, metadados e arquivos. O painel usa
*Export Records* para localizar os anexos e *Export File* (`content=file`, `action=export`)
para baixá-los por HTTPS. Os formatos aceitos são XLSX, XLSM e ODS. Todas as abas de
especialistas são lidas; as abas semanais dos cursos também continuam sendo lidas.

Os IDs devem ser numéricos e crescentes, um por mês, sem exibir esse identificador na interface.
A planilha de atendimentos do maior ID com anexo é tratada como **base completa com histórico**:
arquivos de meses anteriores não são somados, evitando duplicidade. Para cursos, é usado o
anexo mais recente de cada campo configurado em `REDCAP_COURSE_FIELDS`, independentemente
do nome do arquivo. Envie Oncologia em `curso_especialistas_onco` e Anestesiologia em
`curso_especialistas_anestesio` no mesmo registro mensal. Ambos devem ter ao menos um
upload válido; se algum estiver ausente ou ilegível, o painel informa erro.
Eventos e instâncias são preservados na exportação. Para projetos antigos com campo
único, `REDCAP_COURSE_FIELD` continua disponível quando o mapeamento não é definido.
O status de preenchimento do formulário não é um filtro de publicação.

Não há fallback para dados locais: ausência de arquivos, falha na API ou formato inválido
gera erro visível. Os arquivos são baixados em diretório temporário e removidos após o
processamento, inclusive em caso de erro; os dados interpretados ficam no cache do painel
por até 60 segundos. O botão **Atualizar dados** limpa o cache e consulta novamente.
O cache guarda somente as tabelas e o horário da consulta; o `Dataset` é reconstruído
fora dele, sem compartilhar objetos mutáveis entre sessões.
O cache expira, mas não atualiza sozinho uma tela ociosa: a próxima interação ou o botão
consulta a fonte. Ao alterar a configuração, reinicie o Streamlit.

**Agrupamentos**: procedimentos da mesma família (ex.: quimioterapia estágio 1/2) são somados em um só item, e CIDs são agrupados pelo código pai (ex.: C50, C508 → C50 Neoplasia maligna da mama), em `atem/agrupamento.py`.

**Mapa (supervisor)**: a aba **Mapa** mostra o Brasil por estado (atendimentos, nº de especialistas ou média), os médicos alocados, barras por região e mapa de calor região × especialidade. O estado é lido de UF/Local de atuação.

## Login pelo Supabase

Documentos e atividades permanecem no REDCap. O Supabase armazena as contas no
**Auth** e os perfis/permissões em `public.atem_perfis`, sem copiar os documentos.

1. No SQL Editor do projeto, execute `scripts/supabase_schema.sql`. O script ativa
   RLS: o usuário autenticado só lê o próprio perfil ativo e não pode inserir ou
   alterar permissões. Contas novas não recebem acesso automaticamente; não há
   promoção a supervisor via metadados do usuário.
2. Em Authentication > configuração de usuários, desabilite novos cadastros públicos
   (*Allow new users to sign up*). Em Authentication > Users, crie a conta de cada
   participante usando **Create new user**, com senha inicial forte entregue por canal
   seguro e e-mail confirmado somente após validar o titular. Para este fluxo de senha,
   não dependa de links de convite, que exigiriam um callback adicional.
3. Use o exemplo comentado no fim do SQL para inserir o perfil do supervisor
   associado ao UUID da conta. Para especialistas, defina `perfil='especialista'`
   e `especialista_id` igual ao identificador do acompanhamento (`onco-1`, `anest-1`,
   etc.), não ao ID mensal do upload. Não reutilize contas de teste.
4. Configure SMTP próprio para enviar recuperação de senha aos participantes:
   o envio padrão do Supabase tem restrições de destinatários e limites baixos.
   Em Authentication > Email Templates > Reset Password, inclua
   `<p>Seu código de recuperação: <strong>{{ .Token }}</strong></p>` e oriente a
   digitá-lo em **Esqueci minha senha** no painel. O fluxo usa código OTP de
   recuperação, não um callback com token na URL. Não aumente o prazo padrão de expiração.
   A nova senha deve ter pelo menos 12 caracteres; configure a política de senha
   e os limites de tentativas também no Supabase.
5. Configure os secrets:

   ```toml
   AUTH_PROVIDER = "supabase"
   SUPABASE_URL = "https://seu-projeto.supabase.co"
   SUPABASE_PUBLISHABLE_KEY = "sb_publishable_SUBSTITUA"
   ```

   Reinicie o Streamlit. Antes de ativar, confirme que existe ao menos uma conta
   supervisora com perfil ativo. Enquanto o projeto não estiver provisionado, o
   ambiente local pode continuar com `AUTH_PROVIDER="local"`.

O token de acesso e o de renovação ficam apenas na sessão do Streamlit, não no
cache global, em arquivo, na URL ou em logs. A identidade é validada na API Auth e
o perfil é consultado novamente antes de cada execução do painel. Se o perfil for
desativado ou a consulta falhar, os dados não são apresentados. A sessão é renovada
quando necessário; **Sair** encerra a sessão local e tenta invalidar sua renovação
no Supabase. Uma tela já aberta não é apagada retroativamente; a próxima interação
aplica a revogação. Não há migração automática das senhas locais.

## Piloto no Streamlit Community Cloud

1. Obtenha autorização institucional para processar os dados nesse serviço externo.
   Renove tokens ou senhas que tenham sido compartilhados em conversa.
2. Publique apenas o código no GitHub. Nunca inclua `data/`, `.env` ou
   `.streamlit/secrets.toml`. O modelo público `.streamlit/secrets.example.toml`
   contém apenas campos de exemplo.
3. Configure Supabase Auth e os perfis conforme a seção anterior, sem reutilizar
   acessos de teste. A geração local de usuários continua disponível apenas para
   o modo `AUTH_PROVIDER="local"`.
4. Em https://share.streamlit.io/, entre com GitHub e crie um app apontando para
   este repositório, para a branch publicada e para `app.py`. Selecione Python 3.12
   nas configurações avançadas.
5. Cole o modelo de secrets no painel do serviço, configure a URL e o **novo**
   token do REDCap, além da URL e chave publicável do Supabase. Defina
   `AUTH_PROVIDER="supabase"`. Não publique `ATEM_USERS_JSON` nem os acessos locais
   nesse modo. As senhas e os documentos não vão para o GitHub.
6. Publique e confirme login de supervisor e especialista, isolamento entre contas,
   leitura dos dois cursos e o botão **Atualizar dados**. A instância hospedada
   precisa conseguir alcançar a API do REDCap; acesso pela máquina local não prova
   acesso pela nuvem.

Esta opção tem limites gratuitos e hibernação; o Supabase Free também pode pausar
por inatividade. O cadastro e as permissões são administrados no Supabase; recuperação
por código exige SMTP e o template descritos acima. Antes de convidar usuários,
valide a entrega real dos e-mails e o isolamento das contas na instância publicada.

## Premissas

- Cada linha de *Atividades* é um atendimento; é **Consulta** se o nome do procedimento contém "consulta" (inclui teleconsulta) ou o código SIGTAP começa com `0301`; senão, **Procedimento**.
- Ranking = nº de atendimentos no período; empate divide a mesma posição.
- Alertas: ativos com menos de N atendimentos nos últimos X dias, relativos à data do último registro da base.
- Mentorias: nas abas fornecidas ainda estão vazias; o parser aceita meses nas linhas ou colunas.
- Segurança: toda a interface obtém dados via `auth.dados_visiveis`, que filtra pelo `especialista_id` do usuário logado (nunca por entrada do usuário). Se o painel for exposto na internet, use HTTPS.
- Dados reais (Excel, usuários, senhas) ficam em `data/`, ignorada pelo git. Não os commite.
