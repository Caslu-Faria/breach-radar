"""Conversões entre o model ORM `Breach` e os dicts/schemas usados pela API
e pelo motor de filtros legado (`legacy.breach_matcher`)."""

from __future__ import annotations

from app.models import Breach
from app.schemas import BreachOut


def breach_to_dict(breach: Breach) -> dict:
    """Converte um `Breach` (ORM) para o dict no formato PascalCase do feed
    da HIBP — o formato que `legacy.breach_matcher` espera filtrar."""
    return {
        "Name": breach.name,
        "Domain": breach.domain,
        "BreachDate": breach.breach_date,
        "AddedDate": breach.added_date,
        "PwnCount": breach.pwn_count,
        "DataClasses": breach.data_classes,
        "IsVerified": breach.is_verified,
        "IsSensitive": breach.is_sensitive,
        "IsSpamList": breach.is_spam_list,
    }


def dict_to_breach_out(data: dict) -> BreachOut:
    """Converte um dict PascalCase (pós-filtro/paginação) para `BreachOut`
    (`snake_case`), o formato de resposta da API."""
    return BreachOut(
        name=data["Name"],
        domain=data.get("Domain"),
        breach_date=data.get("BreachDate"),
        added_date=data.get("AddedDate"),
        pwn_count=data.get("PwnCount", 0),
        data_classes=data.get("DataClasses") or [],
        is_verified=bool(data.get("IsVerified", False)),
        is_sensitive=bool(data.get("IsSensitive", False)),
        is_spam_list=bool(data.get("IsSpamList", False)),
    )
