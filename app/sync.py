"""Sincronização do catálogo local de breaches com o feed da HIBP."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.hibp_client import fetch_breaches
from app.models import Breach
from app.schemas import SyncResult


def sync_breaches(db: Session) -> SyncResult:
    """Busca o feed da HIBP e faz upsert no catálogo local por `Name`.

    `Name` é a chave de upsert: registros já existentes são atualizados
    (`updated`), novos são criados (`created`). Registros sem `Name` são
    ignorados e contados em `skipped`. Campos ausentes recebem os defaults
    `""`/`None`/`[]`/`0`/`False` (`Domain`/`BreachDate` e `AddedDate`/
    `DataClasses`/`PwnCount`/flags, respectivamente), nunca derrubando o sync
    por um único registro malformado.

    Se o feed falhar, `HIBPFeedError` se propaga sem que o banco seja
    alterado.
    """
    feed = fetch_breaches()

    created = 0
    updated = 0
    skipped = 0

    for item in feed:
        name = item.get("Name")
        if not name:
            skipped += 1
            continue

        breach = db.get(Breach, name)
        if breach is None:
            breach = Breach(name=name)
            db.add(breach)
            created += 1
        else:
            updated += 1

        breach.domain = item.get("Domain") or ""
        breach.breach_date = item.get("BreachDate")
        breach.added_date = item.get("AddedDate")
        breach.pwn_count = item.get("PwnCount") or 0
        breach.data_classes = item.get("DataClasses") or []
        breach.is_verified = bool(item.get("IsVerified", False))
        breach.is_sensitive = bool(item.get("IsSensitive", False))
        breach.is_spam_list = bool(item.get("IsSpamList", False))

    db.commit()

    return SyncResult(
        total_from_feed=len(feed),
        created=created,
        updated=updated,
        skipped=skipped,
    )
