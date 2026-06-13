# Breach Radar

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

**Sem `.env`**, a aplicação sobe com SQLite em memória — útil para explorar a API e rodar os
testes sem depender de Docker/Postgres. Para persistência real, defina `DATABASE_URL` apontando
para um Postgres (ex.: via `docker-compose`, item opcional da Phase 8).

## Como rodar

```bash
uv run uvicorn app.main:app --reload
```

Documentação interativa (Swagger) em <http://127.0.0.1:8000/docs>.

## Como rodar os testes

```bash
uv run pytest
```

A suíte roda com cobertura habilitada (`--cov=app --cov=legacy --cov-report=term-missing`,
configurado em `pyproject.toml`); a meta do desafio é cobertura mínima de 80%. Todos os testes
usam SQLite em memória — nenhuma chamada real à HIBP ou ao Postgres é feita em CI.

## Lint e formatação

```bash
uv run ruff check .
uv run ruff format --check .
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
- [ ] `GET /breaches` e `GET /breaches/{name}` com os filtros descritos no `CLAUDE.md`
- [ ] Testes de resiliência (feed fora do ar) e fechamento da cobertura ≥ 80%
- [ ] `TEST_PLAN.md`
- [ ] Itens opcionais (Docker/compose, CI, Alembic, sync agendado, logs JSON, ETag)

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
11. **Tabelas criadas via `Base.metadata.create_all()`** no startup da app (sem Alembic no MVP;
    migrations ficam como item opcional da Phase 8).
12. **`DATABASE_URL` tem default `sqlite://`** (memória) em `app/config.py` — permite rodar a
    app e a suíte de testes sem `.env`/Docker/Postgres. Em produção, `DATABASE_URL` (via `.env`
    ou `docker-compose`) aponta para o Postgres real; a validação final contra Postgres é
    documentada como passo manual (Phase 8).
