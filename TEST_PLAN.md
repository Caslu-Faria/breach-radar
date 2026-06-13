# TEST_PLAN.md — Breach Radar

Este documento descreve a estratégia de testes do projeto, os casos cobertos por endpoint
(positivos, negativos e extremos), o que **não** foi testado (e por quê) e os riscos
identificados na aplicação.

## 1. Estratégia geral

- **Framework**: `pytest` + `pytest-cov`. Cobertura mínima exigida: 80% (`--cov-fail-under=80`,
  configurado em `pyproject.toml`); a suíte atual atinge **100%** (`app/` + `legacy/`).
- **Mock do feed HIBP**: `respx` intercepta `httpx.get(settings.hibp_api_url, ...)`. **Nenhum
  teste faz chamada real à internet/HIBP** — requisito do `CLAUDE.md` para CI.
- **Banco de dados**: SQLite **em memória** com `StaticPool` (fixture `db_session` em
  `tests/conftest.py`). Cada teste recebe um schema limpo (`create_all`/`drop_all` por teste) —
  testes são independentes e podem rodar em qualquer ordem.
- **Cliente HTTP da API**: `fastapi.testclient.TestClient` com `app.dependency_overrides[get_db]`
  apontando para a sessão de teste (fixture `client`).
- **Dados de teste**:
  - `tests/fixtures/hibp_sample.json` — 8 breaches representativos do feed HIBP, incluindo
    registros sem `DataClasses`, sem `Domain`, sem `BreachDate` e sem `Name` (cobre os defaults
    da decisão #10 e o caso "registro pulado").
  - Conjuntos seedados diretamente via ORM (`tests/test_breaches_list_filters.py`,
    `tests/test_breaches_pagination.py`, `tests/test_breaches_detail.py`) para isolar os testes
    de filtro/paginação do comportamento de `/sync`.
- **Execução**: `uv run pytest` (169 testes). Lint/format via `uv run ruff check .` /
  `ruff format --check .`.

## 2. Bug hunt — `legacy/breach_matcher.py`

Os 3 bugs plantados, repro, severidade e correção estão documentados em
[`legacy/BUGS_FOUND.md`](legacy/BUGS_FOUND.md). Cada bug tem um teste que falhava antes da
correção (`tests/legacy/test_breach_matcher.py`) e passa depois:

| # | Função | Bug | Severidade | Teste |
|---|--------|-----|------------|-------|
| 1 | `domain_matches` | query não normalizada para minúsculas | Média | `test_uppercase_query_matches_lowercase_domain_bug` |
| 2 | `within_breach_date` | `date_to` exclusivo em vez de inclusivo (`>=` em vez de `>`) | Alta | `test_inclusive_upper_bound_bug` |
| 3 | `paginate` | off-by-one no slice — cada página perde 1 item (`page_size=1` sempre vazio) | Alta | `test_page_size_is_respected_bug`, `test_page_size_one_returns_empty_bug`, `test_full_traversal_covers_all_items_bug` |

Além da correção, o módulo foi **estendido** (decisão #6) com `name_matches`,
`within_added_date`, `bool_field_matches` e os parâmetros correspondentes em `filter_breaches`,
cada um com testes próprios e em combinação (`TestFilterBreaches`).

## 3. Casos por endpoint

### `POST /sync` (`tests/test_sync.py`, `tests/test_resilience.py`)

| Caso | Tipo | Resultado esperado |
|------|------|--------------------|
| Feed OK, banco vazio | Positivo | `200`, `created == total_válidos`, `updated == 0`, `skipped == nº sem `Name`` |
| Rodar `/sync` duas vezes com o mesmo feed | Positivo / idempotência | 2ª chamada: `created == 0`, `updated == total_válidos`; sem duplicar linhas (`Name` é PK) |
| Registro existente com campos alterados | Positivo | `updated == 1`, valores do registro refletem o novo feed |
| Registros sem `DataClasses`/`Domain`/`BreachDate` | Extremo (decisão #10) | armazenados como `[]` / `""` / `None`, sync não falha |
| Registro sem `Name` | Extremo (decisão #10) | ignorado e contado em `skipped`, não derruba o sync |
| Feed em timeout | Negativo | `503`, banco **não** alterado |
| Feed responde `500` | Negativo | `503`, banco **não** alterado |
| Feed retorna JSON inválido | Negativo | `503`, banco **não** alterado |
| `/sync` ok seguido de `/sync` com feed indisponível | Extremo / resiliência | 2º `/sync` → `503`, mas os dados do 1º `/sync` permanecem intactos |

### `GET /breaches` (`tests/test_breaches_list_filters.py`, `tests/test_breaches_pagination.py`)

Todos os 12 filtros são testados isoladamente e em combinação (semântica **AND**):

| Filtro | Positivo | Negativo (→ 400) |
|--------|----------|-------------------|
| `domain` | match parcial, case-insensitive (`dropbox`/`DROPBOX`), substring comum (`.com`) | — (string livre, sem validação de formato) |
| `name` | match exato, case-sensitive | slug com caractere inválido (espaço) → `400` |
| `breach_date_from`/`_to` | janela inclusiva nos dois limites (inclui `BreachDate == breach_date_to`) | formato fora de `YYYY-MM-DD` (`2020/01/01`) → `400` |
| `added_date_from`/`_to` | janela inclusiva, compara só os 10 primeiros chars de `AddedDate` | data inválida (`not-a-date`) → `400` |
| `data_class` | case-insensitive, classe comum a vários breaches e classe específica de um único | — |
| `min_pwn_count`/`max_pwn_count` | limite inferior, superior e faixa combinada | negativo (`-1`) e não-inteiro (`abc`) → `400` |
| `is_verified`/`is_sensitive`/`is_spam_list` | `true`/`false` cada flag isolada | valor fora de `true`/`false` (`maybe`) → `400` |
| combinação de filtros | AND entre `is_verified` + `data_class` + `min_pwn_count` retorna a interseção | combinação sem resultados → `200` com `items: []`, `total: 0` |

**Paginação** (`page`/`page_size`, default `1`/`20`, máximo `page_size=100`):

| Caso | Tipo | Resultado esperado |
|------|------|--------------------|
| Primeira página (`page=1, page_size=2` de 5 itens) | Positivo | 2 itens, `total=5`, `total_pages=3` |
| Última página parcial (`page=3, page_size=2` de 5 itens) | Extremo | 1 item (resto), `total_pages=3` |
| Página muito além do total (`page=100`) | Extremo | `200`, `items: []`, `total`/`total_pages` corretos (não é erro) |
| `page_size=1` percorrendo todas as páginas | Extremo (cobre bug #3) | todos os 5 itens aparecem exatamente uma vez, nenhum perdido |
| Página imediatamente após a última, com `page_size=1` | Extremo | `items: []` |
| Sem `page`/`page_size` | Positivo | default `page=1`, `page_size=20` |
| `page_size=100` (limite máximo) | Extremo | aceito, `200` |
| `page` ∈ `{0, -1, "abc", "1.5"}` | Negativo | `400` |
| `page_size` ∈ `{0, -1, "abc", "101"}` | Negativo | `400` |

### `GET /breaches/{name}` (`tests/test_breaches_detail.py`)

| Caso | Tipo | Resultado esperado |
|------|------|--------------------|
| `name` existente | Positivo | `200`, corpo em `snake_case` com todos os campos |
| `name` inexistente (mas slug válido) | Negativo | `404` |
| `name` com slug inválido (`Invalid%20Name`, `Adobe;DROP`) | Negativo / segurança | `400` (validado **antes** da consulta ao banco) |

### Resiliência (`tests/test_resilience.py`)

Cenário: banco populado via `/sync` (feed mockado OK); depois o feed da HIBP fica indisponível
(timeout/`500`):

| Caso | Resultado esperado |
|------|---------------------|
| `GET /breaches` com feed em timeout | `200`, dados servidos do banco local (`total == total_válidos`) |
| `GET /breaches` com feed respondendo `500` | `200`, idem |
| `GET /breaches/{name}` com feed indisponível | `200`, dados servidos do banco local |
| Novo `POST /sync` com feed indisponível | `503`, banco permanece com os dados do `/sync` anterior |

### Camada de banco (`tests/test_database.py`)

- `_create_engine` com `sqlite://` usa `StaticPool` (necessário para SQLite em memória
  compartilhar a conexão entre sessões).
- `_create_engine` com URL não-SQLite (ex.: Postgres) usa `create_engine` padrão.
- `get_db()` produz uma sessão utilizável e a fecha ao final (generator/`finally`).

### Validadores (`tests/test_validators.py`)

Cada validador de `app/validators.py` é testado isoladamente: valor ausente (`None` →
`None`/default), valor válido nos limites (`0`, `page_size=100`), e valores inválidos
(formato errado, negativo, não-inteiro, fora de `true`/`false`, slug inválido, acima de
`max_value`) → `HTTPException(400)`.

### Cliente HIBP (`tests/test_hibp_client.py`)

`fetch_breaches()`: sucesso (200 + JSON lista), header `User-Agent` enviado, timeout, erro de
conexão, status != 200, JSON inválido e JSON que não é uma lista — todos os casos de erro
levantam `HIBPFeedError`.

## 4. O que não foi testado e por quê

- **Chamadas reais à HIBP**: proibidas por requisito do desafio (CI não pode depender de rede
  externa). O contrato do cliente HTTP (`fetch_breaches`) é validado via `respx` cobrindo todos
  os ramos de erro; a integração real fica para validação manual (ver README, smoke test).
- **Concorrência em `/sync`**: duas requisições simultâneas a `/sync` poderiam, em teoria,
  gerar uma condição de corrida no upsert manual (`get` + `add`/`commit`) — duas sessões
  poderiam tentar criar a mesma linha (`Name`) ao mesmo tempo. Não testado porque o
  `TestClient` síncrono e o SQLite em memória do conjunto de testes não reproduzem esse cenário
  de forma realista; em Postgres, uma constraint de PK faria a segunda transação falhar com
  `IntegrityError` não tratado. Listado como risco abaixo.
- **Volume real do feed (~800+ breaches)**: os testes usam conjuntos pequenos (5-8 registros)
  para manter os casos legíveis e determinísticos. O comportamento com o volume real do feed
  HIBP não é exercitado automaticamente — fica para o smoke test manual (README).
- **Postgres real**: a suíte roda 100% em SQLite em memória (decisão #12). A validação final
  contra Postgres via `docker-compose` (Phase 8, opcional) é um passo manual documentado no
  README.
- **Itens opcionais não implementados** (Docker/compose, CI, Alembic, sync agendado, logs
  estruturados, cache HTTP `ETag`): fora do escopo testado por não existirem no código —
  consulte a seção "Status do projeto" do README.

## 5. Riscos identificados

1. **Filtragem em memória não escala**: `GET /breaches` carrega *todos* os registros
   (`db.query(Breach).all()`) e aplica `filter_breaches`/`paginate` em Python a cada
   requisição. Para o catálogo atual da HIBP (~800 registros) isso é trivial, mas não escalaria
   para um catálogo ordens de magnitude maior sem mover os filtros para SQL (`WHERE`/`LIKE`/
   `ORDER BY` + `LIMIT`/`OFFSET`).
2. **`/sync` sem autenticação ou rate limit**: qualquer cliente pode chamar `POST /sync`
   repetidamente, gerando carga tanto no banco local quanto no feed da HIBP (sem cache `ETag`,
   cada chamada baixa o catálogo inteiro). Não há proteção contra abuso.
3. **Upsert concorrente em `/sync`**: como descrito acima, duas chamadas simultâneas a `/sync`
   poderiam colidir no `get-or-create` por PK (`Name`) em Postgres, resultando em
   `IntegrityError` não tratado em uma das transações. Mitigação possível: `INSERT ... ON
   CONFLICT DO UPDATE` (Postgres) ou serializar `/sync` (lock/flag).
4. **Sem sincronização automática**: o catálogo local só é atualizado quando alguém chama
   `POST /sync` manualmente — sem agendamento (APScheduler/cron, item opcional da Phase 8), os
   dados podem ficar desatualizados indefinidamente.
5. **`DATABASE_URL` default em memória**: se a aplicação subir em produção sem `.env`/variável
   de ambiente configurada, ela usa SQLite em memória (decisão #12) — qualquer reinício do
   processo perde todo o catálogo sincronizado. É um default conveniente para
   desenvolvimento/testes, mas perigoso se esquecido em produção; o README destaca isso.
