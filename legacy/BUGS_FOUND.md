# Bugs encontrados em `legacy/breach_matcher.py`

Este documento registra os 3 bugs plantados no módulo legado `legacy/breach_matcher.py`,
encontrados comparando a implementação com o contrato descrito nas docstrings de cada função.
Para cada bug há um teste que **falha** em `tests/legacy/test_breach_matcher.py` (rodar com
`pytest tests/legacy/test_breach_matcher.py -v` para reproduzir).

---

## Bug 1 — `domain_matches`: query não normalizada para minúsculas

- **Severidade**: Média
- **Função afetada**: `domain_matches(breach, query)`
- **Teste que expõe o bug**: `TestDomainMatches::test_uppercase_query_matches_lowercase_domain_bug`

### O que está errado

O contrato diz que o match de domínio deve ser **case-insensitive**, citando explicitamente
`query="Dropbox"` como exemplo que deve casar com `Domain="dropbox.com"`. A implementação atual
normaliza apenas o lado `Domain` (`.lower()`), mas não normaliza `query`:

```python
def domain_matches(breach: dict, query: str) -> bool:
    domain = (breach.get("Domain") or "").lower()
    return query in domain  # <- query não passou por .lower()
```

### Como reproduzir

```python
domain_matches({"Domain": "dropbox.com"}, "Dropbox")  # retorna False, deveria ser True
```

`"Dropbox" in "dropbox.com"` é `False` em Python porque `"D"` (maiúsculo) não é igual a `"d"`.

### Impacto em produção

`GET /breaches?domain=...` é o filtro de busca por domínio mais usado pelo time de resposta a
incidentes ("esse domínio apareceu em algum breach catalogado?"). Qualquer busca digitada com a
capitalização "natural" do nome da empresa (`Dropbox`, `LinkedIn`, `GitHub`, `PayPal`...) retorna
**zero resultados falsos-negativos** mesmo que o breach exista na base — o analista conclui
erroneamente que o domínio não está em nenhum vazamento catalogado. Não há perda de dados no
banco, mas há **perda de confiança na busca** e risco de um analista pular uma investigação por
achar que "não há nada sobre esse domínio".

### Correção

Normalizar `query` para minúsculas antes da comparação, igual já é feito para `domain`:

```python
def domain_matches(breach: dict, query: str) -> bool:
    domain = (breach.get("Domain") or "").lower()
    return query.lower() in domain
```

---

## Bug 2 — `within_breach_date`: limite superior (`date_to`) exclusivo em vez de inclusivo

- **Severidade**: Alta
- **Função afetada**: `within_breach_date(breach, date_from, date_to)`
- **Teste que expõe o bug**: `TestWithinBreachDate::test_inclusive_upper_bound_bug`

### O que está errado

O contrato é explícito: a janela `[date_from, date_to]` é **inclusiva** dos dois lados, com
exemplo concreto — `date_to='2019-12-31'` deve **incluir** um breach com
`BreachDate='2019-12-31'`. A implementação usa `>=`, que **exclui** esse caso:

```python
def within_breach_date(breach, date_from=None, date_to=None) -> bool:
    bd = breach.get("BreachDate") or ""
    if date_from and bd < date_from:
        return False
    if date_to and bd >= date_to:   # <- deveria ser `>`
        return False
    return True
```

### Como reproduzir

```python
within_breach_date({"BreachDate": "2019-12-31"}, date_to="2019-12-31")  # retorna False, deveria ser True
```

### Impacto em produção

Qualquer consulta com `breach_date_to` igual à data exata de um breach faz esse breach
**desaparecer silenciosamente** do resultado, sem erro, sem aviso. Em um produto de threat
intelligence isso é especialmente grave em consultas de janela "fechada" comuns em investigações
(ex.: "todos os breaches de 2019" → `breach_date_from=2019-01-01&breach_date_to=2019-12-31`):
qualquer breach cuja data de vazamento caia exatamente em `2019-12-31` — incluindo
potencialmente um breach crítico — fica de fora do relatório sem nenhum indício de que algo foi
omitido. Isso é exatamente o cenário descrito no `CLAUDE.md`: "um breach crítico sumindo
silenciosamente do índice é um incidente".

### Correção

Trocar `>=` por `>` no segundo `if`, restaurando a semântica inclusiva:

```python
    if date_to and bd > date_to:
        return False
```

---

## Bug 3 — `paginate`: off-by-one no slice (perde o último item de cada página)

- **Severidade**: Alta
- **Função afetada**: `paginate(items, page, page_size)`
- **Testes que expõem o bug**:
  - `TestPaginate::test_first_page`
  - `TestPaginate::test_second_page`
  - `TestPaginate::test_page_size_is_respected_bug`
  - `TestPaginate::test_page_size_one_returns_empty_bug`
  - `TestPaginate::test_full_traversal_covers_all_items_bug`

### O que está errado

O contrato diz que `page=1, page_size=20` deve retornar os itens de índice `0..19` (20 itens) e
que "paginando da primeira à última página, todos os itens devem aparecer". A implementação
subtrai 1 de `end` antes de fazer o slice, fazendo cada página retornar **`page_size - 1`
itens**:

```python
def paginate(items: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    end = start + page_size - 1   # <- o "-1" é o bug
    return items[start:end]
```

Slices em Python já são exclusivos no limite superior (`items[start:end]` não inclui `items[end]`),
então subtrair 1 de `end` é redundante e corta um item de cada página.

### Como reproduzir

```python
paginate([1, 2, 3], page=1, page_size=2)
# retorna [1]      -> deveria retornar [1, 2]

paginate(["a", "b", "c"], page=1, page_size=1)
# retorna []        -> deveria retornar ["a"]
# (start == end sempre quando page_size=1, então o slice é SEMPRE vazio)

# Navegação completa com page_size=2 sobre ["a", "b", "c"]:
paginate(items, page=1, page_size=2) + paginate(items, page=2, page_size=2)
# retorna ["a", "c"] -> deveria retornar ["a", "b", "c"] (perde "b")
```

### Impacto em produção

Este é o bug de maior impacto do lote:

- Com `page_size=1` (caso extremo, mas válido), **toda chamada a `GET /breaches` retorna uma
  lista vazia**, independente do total de registros — o endpoint parece "sem dados" mesmo com a
  base populada.
- Para qualquer `page_size`, **1 breach por página simplesmente nunca aparece em nenhuma
  página** — não é um erro visível (não há exceção, nem contagem inconsistente de `total` se
  `total` for calculado sobre a lista completa antes de paginar), é um item que
  **desaparece silenciosamente** da navegação. Um analista navegando página por página nunca vê
  esse breach, mesmo que ele exista no índice.
- Combinado com filtros (ex.: busca por uma `data_class` sensível com muitos resultados), o
  registro "perdido" pode ser justamente o breach mais crítico da lista, dependendo da ordenação.

Novamente, esse é o cenário de incidente citado no `CLAUDE.md`: um breach relevante "sumindo"
do índice sem nenhum sinal de erro.

### Correção

Remover o `- 1`, deixando o slice padrão do Python fazer o trabalho (exclusivo no limite
superior já é o comportamento desejado):

```python
def paginate(items: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]
```

---

## Resumo

| # | Função | Severidade | Sintoma |
|---|--------|------------|---------|
| 1 | `domain_matches` | Média | Busca por domínio com query em maiúsculas não casa com domínio em minúsculas |
| 2 | `within_breach_date` | Alta | Breach com `BreachDate == date_to` é excluído indevidamente |
| 3 | `paginate` | Alta | Cada página perde 1 item; `page_size=1` retorna sempre `[]` |

Todos os 3 bugs foram corrigidos em `legacy/breach_matcher.py` e os testes correspondentes em
`tests/legacy/test_breach_matcher.py` passam após a correção.
