# Plano de implementação — Breach Radar

> Este documento registra o plano de desenvolvimento combinado antes de iniciar a implementação.
> Serve como referência/contexto para as próximas sessões. Nada deste plano foi executado ainda.

## Contexto

O repositório é greenfield (só `CLAUDE.md`, `.gitignore`, PDFs do desafio, já versionado em
`github.com/Caslu-Faria/breach-radar`). O objetivo é construir a API "Breach Radar" descrita no
`CLAUDE.md`, priorizando código **simples, legível e fácil de manter por um dev júnior**: estrutura
plana, funções pequenas e nomeadas, sem camadas extras (sem service/repository/use-case), filtros
em funções puras testáveis isoladamente.

Ambiente atual: macOS, Python 3.9.6 instalado, sem `docker`/`docker-compose`/`psql`/`brew`. O
usuário optou por **instalar Python 3.11+ e usar a sintaxe moderna `str | None`** — então o Phase 0
inclui instalar uma versão nova do Python via `uv` (não depende de brew/Xcode build tools).

## Decisões adotadas (documentar como suposições no README)

1. **Sync em todo o código** (FastAPI `def` síncrono + SQLAlchemy síncrono + `httpx` síncrono) —
   evita complexidade de sessões/fixtures async, sem perda real de performance neste escopo.
2. **`breach_date`/`added_date` como `String`** (passthrough exato do formato da HIBP:
   `YYYY-MM-DD` / ISO8601) — zero conversão entre linhas do banco e os dicts que
   `legacy/breach_matcher.py` filtra.
3. **Resposta da API em `snake_case`** (`name`, `domain`, `breach_date`, ...) — idiomático em
   Python/REST; documentar que difere do PascalCase da HIBP.
4. **`name` (slug da HIBP) como chave primária** da tabela `breaches` — upsert vira
   `db.get(Breach, name)`.
5. **Upsert manual** (get-or-create por PK), não `ON CONFLICT` — portátil entre SQLite (testes) e
   Postgres (prod).
6. **`legacy/breach_matcher.py` corrigido + estendido é o motor de filtros real** usado por
   `GET /breaches` (não um exercício isolado). Vive em `legacy/`, é importado diretamente pelos
   routers.
7. **`added_date_from`/`added_date_to` aceitam `YYYY-MM-DD`** e comparam com os 10 primeiros
   caracteres de `AddedDate` — mesma lógica/contrato de `breach_date_from/to`.
8. **Paginação**: `page`/`page_size`, padrão `page=1`, `page_size=20`, máximo `page_size=100`.
   Justificativa no README: catálogo pequeno (~800 registros), offset simples é suficiente.
9. **`POST /sync` retorna `503`** (com `{"detail": "..."}`) se o feed da HIBP falhar
   (timeout/5xx/conexão/JSON inválido) — `GET /breaches*` nunca chama a HIBP, então não é afetado
   (resiliência).
10. **Registros malformados no `/sync`**: `Name` ausente → registro pulado (contado em
    `skipped`); `Domain`/`BreachDate`/`DataClasses` ausentes → armazenados como `""`/`None`/`[]`
    (nunca casam com filtros correspondentes, mas aparecem na listagem sem filtro);
    `PwnCount`/flags ausentes → `0`/`False`. Nunca derruba o `/sync` por causa de um registro ruim.
11. **Tabela criada via `Base.metadata.create_all()`** no startup (sem Alembic no MVP; Alembic
    fica no Phase 8 opcional).
12. **Docker/Postgres não estão disponíveis neste ambiente** — os testes rodam 100% em SQLite
    in-memory (compatível, já que `data_classes` usa o tipo `JSON` genérico do SQLAlchemy, que
    funciona em ambos os dialetos). Os arquivos de Docker/compose serão escritos no Phase 8, mas a
    validação final contra Postgres real fica documentada no README como passo manual do usuário
    (`docker-compose up`).

## Phase 0 — Setup do ambiente e scaffolding

- Instalar Python 3.11+ via `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`, depois
  `uv python install 3.11` e `uv venv --python 3.11`). `uv` também gerencia dependências
  (`uv pip install ...` ou `uv sync` a partir do `pyproject.toml`).
- `pyproject.toml`: metadata, dependências (`fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`,
  `pydantic>=2`, `pydantic-settings`, `psycopg[binary]`, `httpx`) + dev (`pytest`, `pytest-cov`,
  `respx`, `ruff`); `[tool.ruff]`; `[tool.pytest.ini_options]` com
  `addopts = "--cov=app --cov=legacy --cov-report=term-missing"`.
- `.env.example`: `DATABASE_URL`, `HIBP_API_URL`, `HIBP_USER_AGENT`, `HIBP_TIMEOUT_SECONDS`.
- Pastas vazias: `app/`, `app/routers/`, `legacy/`, `tests/`, `tests/fixtures/`, `tests/legacy/`
  com `__init__.py` onde necessário.
- Verificar `ruff check .` e `pytest` rodando (mesmo sem testes ainda).

## Phase 1 — Bug hunt em `legacy/breach_matcher.py` (auto-contido)

- Criar `legacy/breach_matcher.py` com o conteúdo **exato** (com os 3 bugs) reproduzido no
  `CLAUDE.md`.
- `tests/legacy/test_breach_matcher.py`: testes que **falham** expondo cada bug:
  - `domain_matches`: `query="Dropbox"` (maiúsculo) vs `Domain="dropbox.com"` → hoje `False`,
    contrato diz `True` (falta `.lower()` na query).
  - `within_breach_date`: `date_to="2019-12-31"` com `BreachDate="2019-12-31"` → hoje excluído,
    contrato diz incluído (`bd >= date_to` deveria ser `bd > date_to`).
  - `paginate`: `page=1, page_size=2` numa lista de 3 → hoje retorna 1 item
    (`items[0:1]`), contrato diz 2 (`items[0:2]`); também testar "paginar do início ao fim deve
    cobrir todos os itens" (falha hoje, perde 1 item por página).
- `legacy/BUGS_FOUND.md` (pt-BR): para cada bug — descrição, repro mínimo, severidade (paginação e
  data são **Alta** — escondem registros do índice silenciosamente; domínio é **Média**),
  impacto em produção.
- Corrigir os 3 bugs in-place.
- Estender `legacy/breach_matcher.py` com `name_matches`, `within_added_date`,
  `bool_field_matches`, e ampliar `filter_breaches()` com `name`, `added_date_from/to`,
  `is_verified/is_sensitive/is_spam_list` (mesmo padrão `if <param> is not None and not
  <matches>(): continue`). Testes para cada nova função + combinações em `filter_breaches`.

## Phase 2 — Camada de banco de dados

- `app/config.py`: `Settings` (pydantic-settings) — `database_url`, `hibp_api_url`,
  `hibp_user_agent`, `hibp_timeout_seconds`.
- `app/database.py`: `engine`, `SessionLocal`, `Base`, `get_db()`.
- `app/models.py`: model `Breach` —
  ```python
  class Breach(Base):
      __tablename__ = "breaches"
      name: Mapped[str] = mapped_column(String, primary_key=True)
      domain: Mapped[str | None] = mapped_column(String, nullable=True)
      breach_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
      added_date: Mapped[str | None] = mapped_column(String(25), nullable=True)
      pwn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
      data_classes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
      is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
      is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
      is_spam_list: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  ```
- `app/main.py`: `FastAPI()` + evento de startup chamando `Base.metadata.create_all(bind=engine)`.
  Sem routers ainda.
- `tests/conftest.py`: fixtures `db_session` (SQLite in-memory + `StaticPool`) e `client`
  (`TestClient` com `app.dependency_overrides[get_db]`).
- `tests/test_main.py`: app sobe, `/docs` responde 200.

## Phase 3 — Cliente HIBP + sync + `POST /sync`

- `app/hibp_client.py`: `fetch_breaches()` (GET com header `User-Agent`, timeout configurável) +
  `HIBPFeedError`, normalizando timeout/erro de conexão/status HTTP/JSON inválido/JSON-não-lista.
- `app/schemas.py`: `SyncResult` (`total_from_feed`, `created`, `updated`, `skipped`).
- `app/sync.py`: `sync_breaches(db) -> dict` — busca o feed (propaga `HIBPFeedError` sem tocar no
  banco se falhar), faz upsert manual por `name`, aplica os defaults da decisão #10.
- `app/routers/sync.py`: `POST /sync` → `HIBPFeedError` vira `HTTPException(503, ...)`.
- `tests/fixtures/hibp_sample.json`: 6-8 breaches de exemplo, incluindo registros sem
  `DataClasses`/`Domain`/`BreachDate`/`Name` e datas/pwn_counts variados (para os testes de
  filtro do Phase 4).
- `tests/test_hibp_client.py` e `tests/test_sync.py` (com `respx`): sucesso, timeout, 500, JSON
  malformado, JSON não-lista, `/sync` 2x sem duplicar, registros malformados tratados.

## Phase 4 — `GET /breaches` e `GET /breaches/{name}`

- `app/filters.py`: `breach_to_dict(breach: Breach) -> dict` (linha ORM → dict no formato HIBP
  PascalCase, o formato que `legacy.breach_matcher` espera).
- `app/schemas.py`: `BreachOut`, `BreachListResponse` (items, page, page_size, total,
  total_pages).
- `app/validators.py`: validadores que recebem `str | None` e devolvem o tipo certo ou levantam
  `HTTPException(400, "...")`: `parse_date_param`, `parse_non_negative_int_param`,
  `parse_bool_param`, `validate_name_param` (usa `is_valid_breach_name`),
  `parse_positive_int_param` (para `page`/`page_size`, com default).
- `app/routers/breaches.py`:
  - `GET /breaches`: todos os filtros declarados como `str | None = Query(None)` (evita 422
    automático), validados manualmente via `app/validators.py`, depois
    `db.query(Breach).all()` → `breach_to_dict` → `legacy.breach_matcher.filter_breaches(...)`
    (todos os 12 filtros, semântica AND) → `paginate(...)` → `BreachListResponse`.
  - `GET /breaches/{name}`: valida slug com `is_valid_breach_name` (400 se inválido), busca por
    PK (404 se não existir).
- Registrar router em `app/main.py`.
- Testes:
  - `tests/test_validators.py` — cada validador, casos válidos/inválidos/limites.
  - `tests/test_breaches_list_filters.py` — cada um dos 12 filtros isolado + combinações AND;
    `name`/data/pwn_count/bool inválidos → 400.
  - `tests/test_breaches_pagination.py` — primeira página, última (parcial), página exagerada
    (vazia, `total` correto), `page_size=1` percorrendo todas as páginas sem perder item (cobre
    o bug #3 corrigido), `page`/`page_size` inválidos → 400.
  - `tests/test_breaches_detail.py` — encontrado (200), não encontrado (404), slug inválido no
    path (400).

## Phase 5 — Resiliência e cobertura

- Testes dedicados: popular o banco (via `/sync` com feed mockado OK, ou seed direto), depois
  mockar a HIBP como indisponível (timeout/500) e confirmar que `GET /breaches` e
  `GET /breaches/{name}` continuam respondendo 200 com os dados já sincronizados; novo `/sync`
  nesse cenário retorna 503 e não altera o banco.
- Rodar suíte completa com `--cov-fail-under=80`; fechar lacunas de cobertura (provavelmente
  `app/main.py` e ramos de erro dos validators).

## Phase 6 — Documentação (pt-BR)

- `README.md`: visão geral, setup (uv/venv, instalar deps, copiar `.env.example`), como rodar a
  API (`uvicorn app.main:app --reload`), como rodar os testes (`pytest`), justificativa da
  paginação, e seção de decisões/suposições técnicas cobrindo os itens da seção "Decisões
  adotadas" acima.
- `TEST_PLAN.md`: estratégia de testes, casos positivos/negativos/extremos por endpoint (espelha
  a tabela de testes dos Phases 1-5), o que não foi testado e por quê (chamadas reais à HIBP;
  concorrência em `/sync`), riscos identificados (filtragem em Python não escala para datasets
  muito grandes; `/sync` sem autenticação/rate-limit).
- Revisar `legacy/BUGS_FOUND.md` para clareza final.

## Phase 7 — QA final

- `ruff check .` e `ruff format --check .`.
- `pytest --cov` ≥ 80%, revisar `--cov-report=term-missing`.
- Commitar em `main` (commits pequenos por fase, conforme o trabalho avança).

## Phase 8 — Opcionais (somente após Phases 0-7 estarem sólidas)

- **Docker + docker-compose**: `Dockerfile` (uvicorn), `docker-compose.yml` (app + `postgres:16`
  com healthcheck), `.dockerignore`. Documentar no README que é o caminho recomendado para rodar
  contra Postgres real.
- **CI (GitHub Actions)**: `.github/workflows/ci.yml` — checkout, setup Python 3.11, instalar
  deps, `ruff check`, `pytest --cov --cov-fail-under=80` (sem precisar de Postgres, testes usam
  SQLite).
- **Alembic**: migration inicial para `breaches`; ajustar `app/main.py` para não rodar
  `create_all()` quando Alembic estiver presente (ou manter só para o caminho de testes/SQLite).
- **Sync agendado**: `APScheduler` no startup, controlado por flag de config
  (`ENABLE_SCHEDULED_SYNC`) para não disparar em testes.
- **Logs estruturados em JSON**: `logging` + formatter JSON nos eventos de sync.
- **Cache HTTP (`ETag`/`If-None-Match`)** em `GET /breaches*`.

## Verificação

- `pytest` (cobertura ≥ 80%, todos os cenários da seção QA do `CLAUDE.md` cobertos).
- `ruff check .` sem erros.
- Smoke manual: subir `uvicorn app.main:app --reload`, abrir `/docs`, rodar `POST /sync` (com
  feed real ou mockado), testar `GET /breaches` com cada filtro e `GET /breaches/{name}`.
- Validação final contra Postgres real via `docker-compose up` (Phase 8) — documentar como passo
  do usuário se Docker não estiver disponível neste ambiente.

## Arquivos críticos

- `legacy/breach_matcher.py` e `legacy/BUGS_FOUND.md`
- `app/models.py`, `app/database.py`, `app/config.py`
- `app/hibp_client.py`, `app/sync.py`, `app/routers/sync.py`
- `app/validators.py`, `app/filters.py`, `app/routers/breaches.py`, `app/schemas.py`
- `tests/conftest.py`, `tests/fixtures/hibp_sample.json`
- `README.md`, `TEST_PLAN.md`
