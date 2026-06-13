# Breach Radar

[![CI](https://github.com/Caslu-Faria/breach-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/Caslu-Faria/breach-radar/actions/workflows/ci.yml)

API REST em **Python (FastAPI) + PostgreSQL** que sincroniza e expõe o catálogo público de
breaches do [HIBP](https://haveibeenpwned.com/api/v3/breaches), com filtros ricos sobre os
dados. Projeto desenvolvido para o desafio backend Neuroscan (ver `CLAUDE.md`).

> **Status**: projeto em desenvolvimento — veja [Status do projeto](#status-do-projeto) para o
> que já está implementado.

## Stack

- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- SQLAlchemy 2.0 (ORM)
- PostgreSQL (produção) / SQLite (testes e modo local sem configuração)
- Alembic (migrations do schema do Postgres)
- pydantic-settings (configuração via variáveis de ambiente / `.env`)
- pytest + pytest-cov + respx (testes)
- ruff (lint e formatação)
- [uv](https://docs.astral.sh/uv/) (ambiente e dependências)

## Setup

### 1. Ambiente Python

Requer Python 3.11+. Com [`uv`](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
uv sync   # cria .venv e instala dependências (app + dev), a partir do pyproject.toml
```

### 2. Configuração (opcional)

```bash
cp .env.example .env
```

Variáveis lidas por `app/config.py`:

| Variável               | Default                                          | Descrição                              |
|-------------------------|--------------------------------------------------|-----------------------------------------|
| `DATABASE_URL`          | `sqlite://` (SQLite em memória)                  | string de conexão SQLAlchemy            |
| `HIBP_API_URL`          | `https://haveibeenpwned.com/api/v3/breaches`     | endpoint do feed de breaches da HIBP     |
| `HIBP_USER_AGENT`       | `breach-radar-app (contato@example.com)`         | header `User-Agent` exigido pela HIBP    |
| `HIBP_TIMEOUT_SECONDS`  | `10`                                              | timeout (segundos) do client HTTP        |
| `ENABLE_SCHEDULED_SYNC` | `false`                                           | ativa o sync periódico em background (ver [Sync agendado](#sync-agendado)) |
| `SYNC_INTERVAL_MINUTES` | `60`                                              | intervalo entre execuções do sync agendado |

**Sem `.env`**, a aplicação sobe com SQLite em memória — útil para explorar a API e rodar os
testes sem depender de Docker/Postgres. Para persistência real, defina `DATABASE_URL` apontando
para um Postgres (ex.: via `docker-compose`, ver [Rodando com Docker](#rodando-com-docker-postgres-real)).

## Como rodar

```bash
uv run uvicorn app.main:app --reload
```

Documentação interativa (Swagger) em <http://127.0.0.1:8000/docs>.

## Como rodar os testes

```bash
uv run pytest
```

A suíte roda com cobertura habilitada e `--cov-fail-under=80` (configurado em
`pyproject.toml`); a meta do desafio é cobertura mínima de 80% e a suíte atinge 100%. Todos os
testes usam SQLite em memória — nenhuma chamada real à HIBP ou ao Postgres é feita em CI.

Para a estratégia de testes (casos positivos/negativos/extremos por endpoint, o que não foi
testado e por quê, riscos identificados), veja [`TEST_PLAN.md`](TEST_PLAN.md).

## Lint e formatação

```bash
uv run ruff check .
uv run ruff format --check .
```

## CI

`.github/workflows/ci.yml` roda em cada push/PR: instala dependências com `uv`, `ruff check`,
`ruff format --check` e `pytest` (cobertura ≥ 80%, sem Postgres — usa SQLite, igual ao ambiente
local).

## Rodando com Docker (Postgres real)

O `docker-compose.yml` sobe a API junto com um Postgres 16 real — é o caminho recomendado
para validar a aplicação contra o banco de produção (e não apenas SQLite):

```bash
docker compose up --build
```

- **`db`**: Postgres 16 com `healthcheck` (`pg_isready`); dados persistem no volume nomeado
  `breach_radar_pgdata`.
- **`app`**: builda a imagem a partir do `Dockerfile` (Python 3.11 + `uv`) e só inicia depois
  que o `healthcheck` do `db` ficar saudável (`depends_on: condition: service_healthy`).
  `DATABASE_URL` já vem configurada no `docker-compose.yml` apontando para
  `postgresql+psycopg://postgres:postgres@db:5432/breach_radar` (hostname `db`, o nome do
  serviço na rede interna do Compose — diferente do `.env.example`, que assume Postgres
  acessível em `localhost` para quem roda a API fora do Docker).
- API disponível em <http://127.0.0.1:8000/docs>. O `command` do serviço `app` roda
  `alembic upgrade head` antes do `uvicorn`, aplicando as migrations no Postgres.

Para parar: `docker compose down` (acrescente `-v` para também remover o volume de dados do
Postgres).

## Migrations (Alembic)

O schema do Postgres é versionado via [Alembic](https://alembic.sqlalchemy.org/) em
`alembic/versions/`. A URL de conexão vem de `app.config.settings.database_url`
(`alembic/env.py`), então basta `.env`/variáveis de ambiente estarem configuradas:

```bash
uv run alembic upgrade head                          # aplica todas as migrations pendentes
uv run alembic revision --autogenerate -m "mensagem" # gera uma nova migration a partir dos models
```

Com `docker compose up`, isso roda automaticamente antes da API subir (ver seção anterior).
**SQLite continua usando `Base.metadata.create_all()` no startup** (default sem `.env`, usado
em testes e modo local) — o Alembic é o caminho de schema apenas para Postgres.

## Sync agendado

Com `ENABLE_SCHEDULED_SYNC=true` no `.env`, a aplicação inicia um
[APScheduler](https://apscheduler.readthedocs.io/) (`BackgroundScheduler`) no startup que roda
`sync_breaches` a cada `SYNC_INTERVAL_MINUTES` minutos (default `60`), sem precisar chamar
`POST /sync` manualmente. Se o feed da HIBP estiver indisponível num ciclo agendado, o erro é
logado e ignorado — o agendador continua rodando até o próximo ciclo (mesma resiliência do
endpoint manual, sem propagar `503` para lugar nenhum).

**Desativado por padrão** (`ENABLE_SCHEDULED_SYNC=false`) para não disparar chamadas reais à
HIBP durante os testes/CI.

## Logs estruturados (JSON)

`app/logging_config.py` configura o logger raiz (`configure_logging()`, chamado na importação
de `app/main.py`) para emitir uma linha JSON por log em stdout — `timestamp`, `level`, `logger`,
`message` e quaisquer campos extras. Os eventos de `sync_breaches` (`app/sync.py`) usam isso
para registrar início, conclusão (com `total_from_feed`/`breaches_created`/`breaches_updated`/
`breaches_skipped`) e falha do feed — tanto via `POST /sync` quanto via
[sync agendado](#sync-agendado). Exemplo de linha de log:

```json
{"timestamp": "2026-06-13 18:00:00", "level": "INFO", "logger": "app.sync", "message": "sync concluído", "total_from_feed": 829, "breaches_created": 829, "breaches_updated": 0, "breaches_skipped": 0}
```

## Cache HTTP (ETag)

`GET /breaches` e `GET /breaches/{name}` (`app/etag.py`) respondem com um header `ETag` —
SHA-256 do JSON do corpo da resposta, entre aspas (ex.: `"3f9a...c1"`). Se o cliente reenviar a
mesma requisição com `If-None-Match: <etag>` e o conteúdo não tiver mudado, a API responde
`304 Not Modified` sem corpo, evitando reenviar a listagem/detalhe inteiros. Qualquer mudança no
catálogo (novo `/sync`) muda o conteúdo serializado e, portanto, o ETag.

```bash
curl -i http://localhost:8000/breaches/Adobe
# HTTP/1.1 200 OK
# ETag: "3f9a1c...e2c1"

curl -i http://localhost:8000/breaches/Adobe -H 'If-None-Match: "3f9a1c...e2c1"'
# HTTP/1.1 304 Not Modified
# ETag: "3f9a1c...e2c1"
```

## Status do projeto

- [x] Setup do ambiente (`uv`, `pyproject.toml`, estrutura de pastas)
- [x] Bug hunt em `legacy/breach_matcher.py` — 3 bugs corrigidos e documentados em
      [`legacy/BUGS_FOUND.md`](legacy/BUGS_FOUND.md), com testes que reproduzem cada um
- [x] Camada de banco de dados: `app/config.py`, `app/database.py`, `app/models.py` (model
      `Breach`) e esqueleto da app FastAPI (`app/main.py`, cria as tabelas no startup)
- [x] Cliente HIBP (`app/hibp_client.py`) + `POST /sync` (`app/sync.py`,
      `app/routers/sync.py`) — idempotente (upsert por `Name`), `503` se o feed estiver
      indisponível/inválido, defaults para campos ausentes (decisão #10)
- [x] `GET /breaches` e `GET /breaches/{name}` (`app/routers/breaches.py`) com os 12 filtros
      combinados em AND (`legacy.breach_matcher.filter_breaches`), paginação (`page`/`page_size`)
      e validação manual dos query params (`app/validators.py`, decisão #13) → `400` com
      mensagem clara para parâmetros malformados
- [x] Testes de resiliência (`tests/test_resilience.py`): com o banco já populado por um
      `/sync` anterior, feed da HIBP em timeout/`500` → `GET /breaches` e
      `GET /breaches/{name}` continuam `200` a partir do banco local, e um novo `/sync` retorna
      `503` sem alterar o banco. Cobertura fechada em 100% (`--cov-fail-under=80`,
      `tests/test_database.py` cobre `app/database.py`)
- [x] [`TEST_PLAN.md`](TEST_PLAN.md): estratégia de testes, casos positivos/negativos/extremos
      por endpoint, o que não foi testado e por quê, riscos identificados
- Itens opcionais (Phase 8):
  - [x] Docker + docker-compose (app + Postgres 16 com healthcheck) — ver
        [Rodando com Docker](#rodando-com-docker-postgres-real)
  - [x] CI (GitHub Actions) — ver [CI](#ci)
  - [x] Alembic (migrations) — ver [Migrations (Alembic)](#migrations-alembic)
  - [x] Sync agendado (APScheduler) — ver [Sync agendado](#sync-agendado)
  - [x] Logs estruturados em JSON — ver [Logs estruturados (JSON)](#logs-estruturados-json)
  - [x] Cache HTTP (ETag/If-None-Match) — ver [Cache HTTP (ETag)](#cache-http-etag)

## Decisões técnicas e suposições

1. **Código síncrono**: FastAPI com `def` síncrono, SQLAlchemy síncrono e `httpx` síncrono —
   evita a complexidade de sessões/fixtures assíncronas, sem perda real de performance no
   escopo deste projeto.
2. **`breach_date`/`added_date` armazenados como `String`** — passthrough exato do formato da
   HIBP (`YYYY-MM-DD` / ISO 8601), sem conversão entre o banco e os dicts que
   `legacy/breach_matcher.py` filtra.
3. **Resposta da API em `snake_case`** (`name`, `domain`, `breach_date`, ...) — idiomático em
   Python/REST; difere do PascalCase usado pelo feed da HIBP.
4. **`name` (slug da HIBP) como chave primária** da tabela `breaches` — o upsert do `/sync` vira
   um get-or-create por PK.
5. **Upsert manual** (get-or-create por PK) em vez de `ON CONFLICT` — portátil entre SQLite
   (testes) e Postgres (produção).
6. **`legacy/breach_matcher.py`** (já corrigido e estendido com os 12 filtros) é o motor de
   filtros real usado por `GET /breaches`, não um exercício isolado.
7. **`added_date_from`/`added_date_to`** aceitam `YYYY-MM-DD` e comparam apenas com os 10
   primeiros caracteres de `AddedDate` — mesma semântica de `breach_date_from`/`breach_date_to`.
8. **Paginação por `page`/`page_size`** (padrão `page=1`, `page_size=20`, máximo `100`) — o
   catálogo é pequeno (~800 registros), então offset simples é suficiente e mais simples de
   implementar/testar do que cursores.
9. **`POST /sync` retorna `503`** se o feed da HIBP falhar (timeout, 5xx, JSON inválido).
   `GET /breaches*` nunca chama a HIBP, então continua respondendo a partir do banco local
   mesmo com o feed fora do ar (resiliência).
10. **Registros malformados no `/sync`**: sem `Name` → registro pulado; sem
    `Domain`/`BreachDate`/`DataClasses` → armazenados como `""`/`None`/`[]`; sem
    `PwnCount`/flags booleanas → `0`/`False`. Um registro ruim nunca derruba o `/sync` inteiro.
11. **Tabelas criadas via `Base.metadata.create_all()`** no startup da app **apenas quando o
    dialeto é SQLite** (`database.engine.dialect.name == "sqlite"`, ver `app/main.py`) — cobre
    testes e o modo local sem `.env`. Em Postgres, o schema é gerenciado pelo Alembic
    (`alembic upgrade head`, ver [Migrations (Alembic)](#migrations-alembic)).
12. **`DATABASE_URL` tem default `sqlite://`** (memória) em `app/config.py` — permite rodar a
    app e a suíte de testes sem `.env`/Docker/Postgres. Em produção, `DATABASE_URL` (via `.env`
    ou `docker-compose`) aponta para o Postgres real.
13. **Filtros e paginação de `GET /breaches` declarados como `str | None = Query(None)`** —
    evita o `422` automático do FastAPI para parâmetros malformados. Cada filtro é validado
    manualmente em `app/validators.py` (`parse_date_param`, `parse_non_negative_int_param`,
    `parse_bool_param`, `parse_positive_int_param`, `validate_name_param`), que levanta
    `HTTPException(400, "...")` com uma mensagem indicando o campo e o formato esperado —
    atende ao requisito do `CLAUDE.md` de `400` com mensagem clara para parâmetros inválidos.
14. **`GET /breaches` reaproveita `legacy.breach_matcher`** como motor de filtros: os registros
    do banco são convertidos para o dict PascalCase do feed da HIBP (`app/filters.breach_to_dict`),
    filtrados via `filter_breaches(...)` (12 filtros, semântica AND) e paginados via
    `paginate(...)`, antes de voltar para `BreachOut` (snake_case) com
    `app/filters.dict_to_breach_out`. `total_pages = ceil(total / page_size)`, e `0` quando não
    há nenhum resultado.
15. **`app/database.py` extrai `_create_engine(database_url)`** — função pura que decide entre
    SQLite em memória (`StaticPool`) e `create_engine` padrão (Postgres/produção). Permite testar
    o ramo não-SQLite (`tests/test_database.py`) sem recarregar o módulo nem depender de um
    Postgres real.
16. **Docker**: `Dockerfile` baseado na imagem oficial `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`,
    com a instalação de dependências (`uv sync --frozen --no-dev`) numa camada separada da cópia
    do código-fonte. `docker-compose.yml` sobe `app` + `db` (`postgres:16` com `healthcheck`
    `pg_isready`); o `app` só inicia após o `db` ficar saudável. Ambiente de desenvolvimento sem
    Docker disponível — configuração não validada localmente via `docker compose up`; fica como
    passo de verificação manual do usuário.
17. **CI**: `.github/workflows/ci.yml` reusa exatamente os comandos documentados em
    [Como rodar os testes](#como-rodar-os-testes) e [Lint e formatação](#lint-e-formatação)
    (`uv sync`, `ruff check`, `ruff format --check`, `pytest`) — sem etapa de Postgres, já que a
    suíte roda 100% em SQLite.
18. **Alembic**: `alembic/env.py` lê `target_metadata` de `app.database.Base` (importando
    `app.models` para registrar `Breach`) e a URL de `app.config.settings.database_url` — uma
    única fonte de verdade para o schema, sem URL duplicada em `alembic.ini`. A migration
    inicial (`alembic/versions/..._create_breaches_table.py`) replica manualmente as colunas de
    `Breach` (mais previsível que `--autogenerate` contra o SQLite em memória usado por padrão).
    `app/main.py` só roda `create_all()` quando o dialeto é `sqlite`; `docker-compose.yml` roda
    `alembic upgrade head` antes do `uvicorn` para Postgres.
19. **Sync agendado** (`app/scheduler.py`): `start_scheduler()` retorna `None` (sem agendar
    nada) quando `ENABLE_SCHEDULED_SYNC=false` (default) — garante que testes/CI nunca disparem
    chamadas reais à HIBP. Quando ativo, `BackgroundScheduler.add_job` chama `run_sync_job` a
    cada `SYNC_INTERVAL_MINUTES`; `run_sync_job` abre/fecha sua própria `Session` (independente
    do `get_db()` por request) e captura `HIBPFeedError` — um ciclo com o feed fora do ar só gera
    um log de aviso, sem derrubar o agendador. `app/main.py` encerra o scheduler
    (`shutdown()`) no shutdown da app.
20. **Logs JSON** (`app/logging_config.py`): `JSONFormatter` serializa cada `LogRecord`
    (`timestamp`/`level`/`logger`/`message` + qualquer `extra`); `configure_logging()` substitui
    os handlers do logger raiz por um único `StreamHandler` com esse formatter. Chamado uma vez
    na importação de `app/main.py`. `app/sync.py` é o único ponto que loga eventos de negócio
    (início/conclusão/falha do sync) — os campos de contagem usam o prefixo `breaches_*`
    (`breaches_created`/`breaches_updated`/`breaches_skipped`) porque `created` colide com o
    atributo padrão `LogRecord.created` (timestamp interno), e `logging` recusa `extra` que
    sobrescreva atributos do record.
21. **ETag forte via SHA-256 do corpo** (`app/etag.py`): `compute_etag()` serializa o
    `response_model` (`model_dump_json()`) e aplica SHA-256, entre aspas — qualquer mudança no
    conteúdo (inclusive um novo `/sync`) muda o ETag. A comparação de `If-None-Match` é uma
    igualdade exata de string (sem suporte a `*`, listas de ETags ou comparação fraca `W/`) —
    suficiente para o caso de uso (cliente que guarda o último ETag recebido) e simples de
    testar. `list_breaches`/`get_breach` passam a retornar `BreachListResponse | Response`
    /`BreachOut | Response`: no caminho `304`, `etag_response()` devolve um `Response` cru
    (sem corpo), ignorando o `response_model` da rota.
