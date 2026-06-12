# CLAUDE.md

Este arquivo fornece orientações ao Claude Code (claude.ai/code) ao trabalhar com código neste
repositório.

> Toda a documentação deste projeto (CLAUDE.md, README.md, TEST_PLAN.md,
> legacy/BUGS_FOUND.md, mensagens de commit, comentários quando necessários, etc.) deve ser
> escrita em **português brasileiro**.

## Conventions

- Sugerir commits após cada nova implementação de feature ou task
- Explicar o motivo de todas as edições sugeridas
- Criar PRs após commits
- Documentar o projeto após cada phase ou implementação concluída

## Estado do repositório

Este repositório atualmente **não contém código de aplicação** — apenas o briefing do desafio:

- `Desafio backend Neuroscan .pdf` — especificação completa do desafio "Breach Radar".
- `Desafio backend Neuroscan 2.pdf` — listagem de código-fonte de `legacy/breach_matcher.py`,
  o módulo legado usado no exercício de bug hunt (fonte reconstruída abaixo).

Tudo abaixo foi extraído desses dois PDFs para que sessões futuras não precisem reler os PDFs.
O projeto (API, testes, migrations, Docker etc.) ainda precisa ser construído do zero seguindo
esta especificação.

## Projeto: Breach Radar

- Linguagem: Python
- Framework: FastApi
- Banco de dados: PostgreSQL

## Objetivo do projeto

Construir o **Breach Radar**: uma API REST em **Python + PostgreSQL** que sincroniza e expõe ocatálogo público de breaches da HIBP (`https://haveibeenpwned.com/api/v3/breaches`), com filtros ricos.

- O endpoint `/breaches` da HIBP é público (sem API key), mas **exige header `User-Agent`**
  (sem ele a resposta é 403). Retorna um array JSON com ~800+ breaches.
- Cada breach traz os campos: `Name` (slug único, ex.: `Adobe`, `LinkedIn`), `Domain`,
  `BreachDate` (`YYYY-MM-DD`), `AddedDate` (ISO 8601 com hora), `PwnCount` (inteiro),
  `DataClasses` (lista de strings) e os booleanos `IsVerified`, `IsSensitive`, `IsSpamList`.
- O Swagger/OpenAPI deve ser exposto em `/docs` — isso sugere fortemente **FastAPI** como
  framework (FastAPI serve `/docs` automaticamente), embora a especificação não obrigue
  explicitamente.

## Endpoints da API

| Método | Rota               | Descrição                              |
|--------|--------------------|------------------------------------------|
| POST   | `/sync`            | Sincroniza o armazenamento local com o feed da HIBP |
| GET    | `/breaches`        | Lista breaches com filtros                |
| GET    | `/breaches/{name}` | Detalhe de um breach                      |

### Filtros de `GET /breaches` (principal critério de avaliação da Parte 1)

Todos os filtros devem se combinar com semântica **E / AND**.

- `domain` — match parcial e case-insensitive em `Domain`.
- `name` — busca exata pela chave do breach (`Name`); deve validar formato de slug → `400` se
  inválido.
- `breach_date_from` / `breach_date_to` — janela inclusiva sobre `BreachDate`.
- `added_date_from` / `added_date_to` — janela sobre `AddedDate`.
- `data_class` — match case-insensitive contra qualquer item de `DataClasses` (ex.: `Passwords`,
  `Email addresses`).
- `min_pwn_count` / `max_pwn_count` — faixa sobre `PwnCount` (inteiros ≥ 0).
- `is_verified` / `is_sensitive` / `is_spam_list` — flags booleanas.
- A estratégia de paginação é livre (`page`/`page_size`, `limit`/`offset`, cursor etc.) — a
  decisão deve ser **justificada no README.md**.

### Regras de negócio

1. **Idempotência** — rodar `POST /sync` várias vezes não deve duplicar breaches; `Name` é a
   chave de upsert.
2. **Resiliência** — se o feed da HIBP estiver fora do ar, `GET /breaches*` deve continuar
   respondendo a partir do cache/DB local.
3. **Validação** — parâmetros malformados (data fora do formato `YYYY-MM-DD`,
   `*_pwn_count` não-inteiro ou negativo, `name` com caracteres inválidos) → `400` com mensagem
   clara.

## Requisitos de QA (Parte 2)

### Testes (cobertura mínima de 80%)

Mocar o feed externo (`respx`, `responses` ou similar) — **sem chamadas reais à HIBP em CI**.
Cenários obrigatórios:

- Feed fora do ar (timeout / 500).
- JSON malformado ou campos faltando (breach sem `DataClasses`, `Domain` ou `BreachDate`).
- `/sync` rodado duas vezes → sem duplicação.
- Cada filtro isoladamente, e em combinação.
- Parâmetro inválido → `400`.
- Casos extremos de paginação (primeira página, última página, valor de página exagerado).

### `TEST_PLAN.md`

Deve documentar: estratégia de testes, casos positivos/negativos/extremos, o que **não** foi
testado e por quê, e riscos identificados na aplicação.

### Bug hunt — `legacy/breach_matcher.py`

Este módulo (usado por `GET /breaches` para filtragem) tem **3 bugs plantados**. As docstrings
descrevem o contrato *pretendido* — essa é a fonte da verdade, não a implementação.
Para cada bug:

1. Documentar em `legacy/BUGS_FOUND.md`: o que está errado, como reproduzir, severidade e
   impacto em produção (este é um produto de cybersec — um breach crítico sumindo
   silenciosamente do índice é um incidente).
2. Escrever um teste que **falhe**, expondo o bug.
3. Corrigir e garantir que o teste passe.

Fonte reconstruída (criar este arquivo como `legacy/breach_matcher.py` para iniciar o exercício):

```python
"""
breach_matcher.py — utilitários de filtragem do catálogo de breaches (legado).

Este módulo é usado pelo endpoint GET /breaches para decidir quais registros
entram na resposta. Cada função opera sobre um "breach" no formato do feed da
HIBP (um dict), por exemplo:

    {
        "Name": "Adobe",
        "Domain": "adobe.com",
        "BreachDate": "2013-10-04",
        "AddedDate": "2013-12-04T00:00:00Z",
        "PwnCount": 152445165,
        "DataClasses": ["Email addresses", "Password hints", "Passwords"],
        "IsVerified": True,
        "IsSensitive": False,
        "IsSpamList": False,
    }

NOTA: código legado herdado de outra squad. As docstrings descrevem como cada
função DEVERIA se comportar — são a fonte da verdade do contrato.
"""
from __future__ import annotations

import re

# Slug de um breach: letras, dígitos, ponto e hífen. Não pode ser vazio.
_NAME_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


def is_valid_breach_name(name: str) -> bool:
    """Retorna True se `name` é um slug de breach válido.

    Contrato: aceita apenas letras, dígitos, '.' e '-', e não pode ser vazio.
    Qualquer outro caractere (espaço, ';', aspas, etc.) torna o nome inválido.
    """
    if not name:
        return False
    return _NAME_RE.fullmatch(name) is not None


def domain_matches(breach: dict, query: str) -> bool:
    """Filtro de domínio: match PARCIAL e CASE-INSENSITIVE no campo `Domain`.

    Ex.: query="adobe"   casa com Domain="adobe.com".
         query="Dropbox" casa com Domain="dropbox.com".
    Breaches sem domínio (Domain vazio/ausente) nunca casam.
    """
    domain = (breach.get("Domain") or "").lower()
    return query in domain


def data_class_matches(breach: dict, wanted: str) -> bool:
    """Retorna True se o breach expõe a classe de dados `wanted`.

    Contrato: comparação CASE-INSENSITIVE contra cada item de `DataClasses`.
    Ex.: wanted="passwords" casa com DataClasses=["Email addresses", "Passwords"]
    """
    wanted_norm = wanted.strip().lower()
    return any(wanted_norm == dc.strip().lower() for dc in breach.get("DataClasses", []))


def within_breach_date(
    breach: dict,
    date_from: str | None = None,
    date_to: str | None = None,
) -> bool:
    """Filtra por `BreachDate` dentro da janela [date_from, date_to], INCLUSIVA.

    Datas no formato 'YYYY-MM-DD'. Limite None significa "sem limite" daquele lado.
    Ex.: date_from='2019-01-01', date_to='2019-12-31' deve INCLUIR um breach de
         BreachDate='2019-12-31'.
    """
    bd = breach.get("BreachDate") or ""
    if date_from and bd < date_from:
        return False
    if date_to and bd >= date_to:
        return False
    return True


def paginate(items: list, page: int, page_size: int) -> list:
    """Retorna a fatia da página `page` (1-indexada) com até `page_size` itens.

    Ex.: page=1, page_size=20 -> itens de índice 0..19.
         page=2, page_size=20 -> itens de índice 20..39.
    Paginando da primeira à última página, todos os itens devem aparecer.
    """
    start = (page - 1) * page_size
    end = start + page_size - 1
    return items[start:end]


def filter_breaches(
    breaches: list[dict],
    *,
    domain: str | None = None,
    data_class: str | None = None,
    breach_date_from: str | None = None,
    breach_date_to: str | None = None,
    min_pwn_count: int | None = None,
    max_pwn_count: int | None = None,
) -> list[dict]:
    """Aplica todos os filtros informados (semântica E / AND) e devolve os matches."""
    result = []
    for b in breaches:
        if domain is not None and not domain_matches(b, domain):
            continue
        if data_class is not None and not data_class_matches(b, data_class):
            continue
        if not within_breach_date(b, breach_date_from, breach_date_to):
            continue
        pwn = b.get("PwnCount", 0)
        if min_pwn_count is not None and pwn < min_pwn_count:
            continue
        if max_pwn_count is not None and pwn > max_pwn_count:
            continue
        result.append(b)
    return result
```

## Itens opcionais (Parte 3 — pontos extras)

- Docker + docker-compose (app + Postgres subindo com 1 comando).
- CI configurado (GitHub Actions com lint + testes + cobertura).
- Migrations versionadas (Alembic ou similar).
- Agendamento automático da sync (cron / APScheduler).
- Logs estruturados em JSON.
- Cache HTTP com `ETag` / `If-None-Match`.

## Entrega e avaliação

- Repositório Git público (ou `.zip`).
- `README.md` com setup, como rodar os testes e decisões técnicas/suposições (incluindo a
  justificativa da estratégia de paginação).
- `TEST_PLAN.md` e `legacy/BUGS_FOUND.md` conforme descrito acima.

Pesos da avaliação: endpoints/filtros 25%, qualidade dos testes 30%, bug hunt 25%, código
limpo/documentação 20%, opcionais até +10% extra.
