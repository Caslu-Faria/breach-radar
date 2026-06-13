"""Endpoints `GET /breaches` (listagem com filtros) e `GET /breaches/{name}`
(detalhe de um breach)."""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.etag import etag_response
from app.filters import breach_to_dict, dict_to_breach_out
from app.models import Breach
from app.schemas import BreachListResponse, BreachOut
from app.validators import (
    parse_bool_param,
    parse_date_param,
    parse_non_negative_int_param,
    parse_positive_int_param,
    validate_name_param,
)
from legacy.breach_matcher import filter_breaches, paginate

router = APIRouter()


@router.get("/breaches", response_model=BreachListResponse)
def list_breaches(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    domain: str | None = Query(None, description="Match parcial e case-insensitive em Domain"),
    name: str | None = Query(None, description="Busca exata pelo slug (Name)"),
    data_class: str | None = Query(None, description="Classe de dados exposta (case-insensitive)"),
    breach_date_from: str | None = Query(None, description="BreachDate >= YYYY-MM-DD"),
    breach_date_to: str | None = Query(None, description="BreachDate <= YYYY-MM-DD"),
    added_date_from: str | None = Query(None, description="AddedDate >= YYYY-MM-DD"),
    added_date_to: str | None = Query(None, description="AddedDate <= YYYY-MM-DD"),
    min_pwn_count: str | None = Query(None, description="PwnCount >= valor (inteiro >= 0)"),
    max_pwn_count: str | None = Query(None, description="PwnCount <= valor (inteiro >= 0)"),
    is_verified: str | None = Query(None, description="IsVerified == true/false"),
    is_sensitive: str | None = Query(None, description="IsSensitive == true/false"),
    is_spam_list: str | None = Query(None, description="IsSpamList == true/false"),
    page: str | None = Query(None, description="Página (1-indexada), default 1"),
    page_size: str | None = Query(None, description="Itens por página (1-100), default 20"),
) -> BreachListResponse | Response:
    """Lista breaches do catálogo local, com filtros combinados em AND.

    Todos os filtros são opcionais. Parâmetros malformados (datas fora do
    formato `YYYY-MM-DD`, `*_pwn_count`/`page`/`page_size` não-inteiros ou
    fora de faixa, `name` com slug inválido, flags booleanas fora de
    `true`/`false`) retornam `400`.

    Define o header `ETag`; se `If-None-Match` casar com o ETag atual,
    responde `304 Not Modified` sem corpo.
    """
    if name is not None:
        name = validate_name_param(name)

    breach_date_from = parse_date_param(breach_date_from, "breach_date_from")
    breach_date_to = parse_date_param(breach_date_to, "breach_date_to")
    added_date_from = parse_date_param(added_date_from, "added_date_from")
    added_date_to = parse_date_param(added_date_to, "added_date_to")
    parsed_min_pwn_count = parse_non_negative_int_param(min_pwn_count, "min_pwn_count")
    parsed_max_pwn_count = parse_non_negative_int_param(max_pwn_count, "max_pwn_count")
    parsed_is_verified = parse_bool_param(is_verified, "is_verified")
    parsed_is_sensitive = parse_bool_param(is_sensitive, "is_sensitive")
    parsed_is_spam_list = parse_bool_param(is_spam_list, "is_spam_list")
    page_number = parse_positive_int_param(page, "page", default=1)
    page_size_number = parse_positive_int_param(page_size, "page_size", default=20, max_value=100)

    all_breaches = [breach_to_dict(b) for b in db.query(Breach).all()]
    matches = filter_breaches(
        all_breaches,
        name=name,
        domain=domain,
        data_class=data_class,
        breach_date_from=breach_date_from,
        breach_date_to=breach_date_to,
        added_date_from=added_date_from,
        added_date_to=added_date_to,
        min_pwn_count=parsed_min_pwn_count,
        max_pwn_count=parsed_max_pwn_count,
        is_verified=parsed_is_verified,
        is_sensitive=parsed_is_sensitive,
        is_spam_list=parsed_is_spam_list,
    )

    total = len(matches)
    total_pages = ceil(total / page_size_number) if total else 0
    page_items = paginate(matches, page_number, page_size_number)

    result = BreachListResponse(
        items=[dict_to_breach_out(b) for b in page_items],
        page=page_number,
        page_size=page_size_number,
        total=total,
        total_pages=total_pages,
    )
    return etag_response(request, response, result)


@router.get("/breaches/{name}", response_model=BreachOut)
def get_breach(
    name: str, request: Request, response: Response, db: Session = Depends(get_db)
) -> BreachOut | Response:
    """Detalhe de um breach pelo `name` (slug).

    `400` se `name` não for um slug válido, `404` se não houver breach com
    esse `name` no catálogo local.

    Define o header `ETag`; se `If-None-Match` casar com o ETag atual,
    responde `304 Not Modified` sem corpo.
    """
    validate_name_param(name)

    breach = db.get(Breach, name)
    if breach is None:
        raise HTTPException(status_code=404, detail=f"breach '{name}' não encontrado")

    result = dict_to_breach_out(breach_to_dict(breach))
    return etag_response(request, response, result)
