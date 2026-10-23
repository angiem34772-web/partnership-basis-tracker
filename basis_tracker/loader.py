"""Read the CSV input files into model objects."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import BuyoutAgreement, Distribution, Division, Entity, K1Input, Partner


@dataclass
class Inputs:
    entities: list[Entity]
    partners: list[Partner]
    k1s: list[K1Input]
    distributions: list[Distribution]
    divisions: list[Division]
    buyouts: list[BuyoutAgreement]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _num(value: str) -> float:
    return float(value) if value else 0.0


def load_inputs(data_dir: str | Path) -> Inputs:
    d = Path(data_dir)
    entities = [
        Entity(r["entity_id"], r["name"], _date(r["formed"]), r["formed_by"])
        for r in _rows(d / "entities.csv")
    ]
    partners = [
        Partner(r["partner_id"], r["name"], r["partner_type"], _date(r["admitted"]), r["admission_type"])
        for r in _rows(d / "partners.csv")
    ]
    k1s = [
        K1Input(
            partner_id=r["partner_id"],
            entity_id=r["entity_id"],
            tax_year=int(r["tax_year"]),
            contributions=_num(r["contributions"]),
            ordinary_income=_num(r["ordinary_income"]),
            interest_income=_num(r["interest_income"]),
            net_capital_gain=_num(r["net_capital_gain"]),
            tax_exempt_income=_num(r["tax_exempt_income"]),
            nondeductible_expenses=_num(r["nondeductible_expenses"]),
            liability_share_end=_num(r["liability_share_end"]),
        )
        for r in _rows(d / "k1_inputs.csv")
    ]
    distributions = [
        Distribution(r["partner_id"], r["entity_id"], _date(r["paid_on"]), _num(r["amount"]), r["kind"])
        for r in _rows(d / "distributions.csv")
    ]
    divisions = [
        Division(_date(r["effective"]), r["from_entity"], r["to_entity"], _num(r["pct_transferred"]))
        for r in _rows(d / "divisions.csv")
    ]
    buyouts = [
        BuyoutAgreement(
            partner_id=r["partner_id"],
            entity_id=r["entity_id"],
            effective=_date(r["effective"]),
            price=_num(r["price"]),
            method=r["method"],
            num_payments=int(r["num_payments"] or 1),
            first_payment=_date(r["first_payment"]),
        )
        for r in _rows(d / "buyouts.csv")
    ]
    _validate(entities, partners, k1s, distributions, buyouts)
    return Inputs(entities, partners, k1s, distributions, divisions, buyouts)


def _validate(entities, partners, k1s, distributions, buyouts) -> None:
    entity_ids = {e.entity_id for e in entities}
    partner_ids = {p.partner_id for p in partners}
    for item in [*k1s, *distributions, *buyouts]:
        if item.partner_id not in partner_ids:
            raise ValueError(f"Unknown partner {item.partner_id!r} in {item}")
        if item.entity_id not in entity_ids:
            raise ValueError(f"Unknown entity {item.entity_id!r} in {item}")
    seen = set()
    for k in k1s:
        key = (k.partner_id, k.entity_id, k.tax_year)
        if key in seen:
            raise ValueError(f"Duplicate K-1 input for {key}")
        seen.add(key)
