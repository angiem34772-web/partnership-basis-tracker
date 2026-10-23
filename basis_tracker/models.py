"""Data structures for K-1 inputs, events, and rollforward results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Entity:
    entity_id: str
    name: str
    formed: date
    formed_by: str  # e.g. "Cash contributions" or "Division of MHP"


@dataclass(frozen=True)
class Partner:
    partner_id: str
    name: str
    partner_type: str  # Individual, Trust, LLC
    admitted: date
    admission_type: str  # Seed investor or Buy-in


@dataclass(frozen=True)
class K1Input:
    """One partner's K-1 amounts from one partnership for one tax year."""

    partner_id: str
    entity_id: str
    tax_year: int
    contributions: float = 0.0
    ordinary_income: float = 0.0  # Box 1, negative for a loss
    interest_income: float = 0.0  # Box 5
    net_capital_gain: float = 0.0  # Boxes 8/9a, negative for a loss
    tax_exempt_income: float = 0.0  # Box 18A/B
    nondeductible_expenses: float = 0.0  # Box 18C
    liability_share_end: float = 0.0  # Item K, end of year


@dataclass(frozen=True)
class Distribution:
    """A cash distribution reported on the K-1 (Box 19A)."""

    partner_id: str
    entity_id: str
    paid_on: date
    amount: float
    kind: str = "Regular"


@dataclass(frozen=True)
class Division:
    """A partnership division under IRC 708(b)(2)(B), assets-over form."""

    effective: date
    from_entity: str
    to_entity: str
    pct_transferred: float  # share of inside basis and liabilities moved


@dataclass(frozen=True)
class BuyoutAgreement:
    """Liquidation of a partner's entire interest by the partnership (IRC 736(b))."""

    partner_id: str
    entity_id: str
    effective: date
    price: float
    method: str  # "Lump sum" or "Installment"
    num_payments: int = 1
    first_payment: date | None = None


@dataclass(frozen=True)
class Payment:
    partner_id: str
    entity_id: str
    paid_on: date
    amount: float
    number: int
    of: int

    @property
    def is_final(self) -> bool:
        return self.number == self.of


@dataclass
class Flag:
    partner_id: str
    entity_id: str
    tax_year: int
    code: str
    message: str
    amount: float = 0.0


@dataclass
class YearResult:
    """Basis and tax capital rollforward for one partner, one entity, one year."""

    partner_id: str
    entity_id: str
    tax_year: int

    # Outside basis
    beginning_basis: float = 0.0
    division_adjustment: float = 0.0
    contributions: float = 0.0
    income_items: float = 0.0  # ordinary income, interest, capital gain (positive only)
    tax_exempt_income: float = 0.0
    liability_increase: float = 0.0
    cash_distributions: float = 0.0
    liability_decrease: float = 0.0  # deemed distribution under IRC 752(b)
    gain_on_distributions: float = 0.0  # IRC 731(a)(1)
    nondeductible_expenses: float = 0.0
    nondeductible_allowed: float = 0.0
    current_losses: float = 0.0  # losses reported this year
    prior_suspended_losses: float = 0.0  # carried in from prior years
    losses_allowed: float = 0.0
    suspended_losses_end: float = 0.0  # IRC 704(d) carryforward
    suspended_losses_forfeited: float = 0.0
    liquidating_payments: float = 0.0
    liquidation_gain: float = 0.0
    liquidation_loss: float = 0.0
    ending_basis: float = 0.0

    # Tax-basis capital account
    beginning_capital: float = 0.0
    capital_division_adjustment: float = 0.0
    net_income_for_capital: float = 0.0  # all income less all losses, before limits
    capital_closed_on_liquidation: float = 0.0
    ending_capital: float = 0.0

    beginning_liabilities: float = 0.0
    ending_liabilities: float = 0.0

    # Self-check: outside basis less (tax capital + liability share)
    basis_capital_difference: float = 0.0
    explained_difference: float = 0.0

    status: str = "Active"
    flags: list[str] = field(default_factory=list)

    @property
    def unexplained_difference(self) -> float:
        return round(self.basis_capital_difference - self.explained_difference, 2)
