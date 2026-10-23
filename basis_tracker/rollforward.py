"""Roll each partner's outside basis and tax-basis capital account forward.

Ordering within a tax year follows Treas. Reg. 1.704-1(d)(2) and IRC 705:

1. Increase basis for contributions, income (taxable and tax-exempt), and any
   increase in the partner's share of partnership liabilities (IRC 752(a)).
2. Decrease basis for cash distributions, including a net decrease in the
   liability share, which is a deemed cash distribution (IRC 752(b)).
   Distributions above basis are gain (IRC 731(a)(1)). Quarterly draws are
   tested at year end (Treas. Reg. 1.731-1(a)(1)(ii)).
3. Decrease basis for nondeductible, noncapital expenses.
4. Decrease basis for losses, limited to remaining basis (IRC 704(d)). Losses
   over the limit carry forward, keeping their character pro rata.
5. In a buyout year, close the capital account, forfeit any suspended losses,
   and apply the liquidating payments (see buyouts.py).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .buyouts import payment_schedule
from .loader import Inputs
from .models import BuyoutAgreement, Flag, K1Input, Payment, YearResult

CENT = 0.005


@dataclass
class _State:
    basis: float = 0.0
    capital: float = 0.0
    liabilities: float = 0.0
    suspended_ordinary: float = 0.0
    suspended_capital: float = 0.0
    explained: float = 0.0
    liquidated: bool = False
    # Basis and capital moved by a division at the start of the year
    division_basis: float = 0.0
    division_capital: float = 0.0

    @property
    def suspended(self) -> float:
        return self.suspended_ordinary + self.suspended_capital


@dataclass
class PaymentResult:
    payment: Payment
    basis_before: float
    basis_recovered: float
    gain: float
    loss: float
    basis_after: float


@dataclass
class DivisionResult:
    partner_id: str
    from_entity: str
    to_entity: str
    basis_before: float
    basis_transferred: float
    capital_transferred: float
    liabilities_transferred: float
    suspended_transferred: float


@dataclass
class Results:
    years: list[YearResult] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    payments: list[PaymentResult] = field(default_factory=list)
    divisions: list[DivisionResult] = field(default_factory=list)


def run(inputs: Inputs) -> Results:
    results = Results()
    states: dict[tuple[str, str], _State] = defaultdict(_State)

    k1_by_key = {(k.partner_id, k.entity_id, k.tax_year): k for k in inputs.k1s}
    dists_by_key = defaultdict(list)
    for d in inputs.distributions:
        dists_by_key[(d.partner_id, d.entity_id, d.paid_on.year)].append(d)
    buyout_by_key: dict[tuple[str, str], BuyoutAgreement] = {
        (b.partner_id, b.entity_id): b for b in inputs.buyouts
    }
    payments_by_key = defaultdict(list)
    for b in inputs.buyouts:
        for p in payment_schedule(b):
            payments_by_key[(p.partner_id, p.entity_id, p.paid_on.year)].append(p)

    all_years = {k.tax_year for k in inputs.k1s} | {y for (_, _, y) in payments_by_key}
    entity_order = [e.entity_id for e in inputs.entities]

    for year in range(min(all_years), max(all_years) + 1):
        for division in (d for d in inputs.divisions if d.effective.year == year):
            _apply_division(division, states, results)

        keys = {(p, e) for (p, e, y) in k1_by_key if y == year}
        keys |= {(p, e) for (p, e, y) in payments_by_key if y == year}
        for partner_id, entity_id in sorted(keys, key=lambda k: (entity_order.index(k[1]), k[0])):
            k1 = k1_by_key.get((partner_id, entity_id, year)) or K1Input(
                partner_id, entity_id, year, liability_share_end=states[(partner_id, entity_id)].liabilities
            )
            row = _roll_year(
                state=states[(partner_id, entity_id)],
                k1=k1,
                distributions=sum(d.amount for d in dists_by_key[(partner_id, entity_id, year)]),
                buyout=buyout_by_key.get((partner_id, entity_id)),
                payments=sorted(payments_by_key[(partner_id, entity_id, year)], key=lambda p: p.paid_on),
                results=results,
            )
            results.years.append(row)
    return results


def _apply_division(division, states, results) -> None:
    """Assets-over division: the resulting partnership's interests are distributed
    to the partners, who take a carryover basis (IRC 732(a)). Each partner's
    outside basis, tax capital, liability share, and suspended losses are split
    in the same proportion as the inside basis that moved."""
    pct = division.pct_transferred
    for (partner_id, entity_id), old in list(states.items()):
        if entity_id != division.from_entity or old.liquidated:
            continue
        new = states[(partner_id, division.to_entity)]
        moved = _State(
            basis=old.basis * pct,
            capital=old.capital * pct,
            liabilities=old.liabilities * pct,
            suspended_ordinary=old.suspended_ordinary * pct,
            suspended_capital=old.suspended_capital * pct,
            explained=old.explained * pct,
        )
        results.divisions.append(
            DivisionResult(
                partner_id, division.from_entity, division.to_entity,
                basis_before=old.basis,
                basis_transferred=moved.basis,
                capital_transferred=moved.capital,
                liabilities_transferred=moved.liabilities,
                suspended_transferred=moved.suspended,
            )
        )
        for attr in ("basis", "capital", "liabilities", "suspended_ordinary", "suspended_capital", "explained"):
            setattr(old, attr, getattr(old, attr) - getattr(moved, attr))
            setattr(new, attr, getattr(new, attr) + getattr(moved, attr))
        old.division_basis -= moved.basis
        new.division_basis += moved.basis
        old.division_capital -= moved.capital
        new.division_capital += moved.capital


def _roll_year(state, k1, distributions, buyout, payments, results) -> YearResult:
    row = YearResult(k1.partner_id, k1.entity_id, k1.tax_year)

    def flag(code: str, message: str, amount: float = 0.0) -> None:
        row.flags.append(code)
        results.flags.append(Flag(k1.partner_id, k1.entity_id, k1.tax_year, code, message, round(amount, 2)))

    # Division transfers already moved the balances; show them as their own line.
    division, capital_division = state.division_basis, state.division_capital
    state.division_basis = state.division_capital = 0.0

    row.beginning_basis = state.basis - division
    row.division_adjustment = division
    row.beginning_capital = state.capital - capital_division
    row.capital_division_adjustment = capital_division
    row.beginning_liabilities = state.liabilities
    row.prior_suspended_losses = state.suspended

    # 1. Increases
    liability_change = k1.liability_share_end - state.liabilities
    row.contributions = k1.contributions
    row.income_items = max(k1.ordinary_income, 0) + k1.interest_income + max(k1.net_capital_gain, 0)
    row.tax_exempt_income = k1.tax_exempt_income
    row.liability_increase = max(liability_change, 0)
    basis = state.basis + row.contributions + row.income_items + row.tax_exempt_income + row.liability_increase

    # 2. Distributions, including deemed distributions from a liability decrease
    row.cash_distributions = distributions
    row.liability_decrease = max(-liability_change, 0)
    total_distributed = row.cash_distributions + row.liability_decrease
    if total_distributed > basis + CENT:
        row.gain_on_distributions = total_distributed - basis
        flag(
            "731_GAIN",
            f"Distributions of {total_distributed:,.0f} exceed basis of {basis:,.0f}; "
            f"{row.gain_on_distributions:,.0f} is gain under IRC 731(a)(1).",
            row.gain_on_distributions,
        )
        basis = 0.0
    else:
        basis -= total_distributed

    # 3. Nondeductible, noncapital expenses
    row.nondeductible_expenses = k1.nondeductible_expenses
    row.nondeductible_allowed = min(k1.nondeductible_expenses, basis)
    nondeductible_excess = k1.nondeductible_expenses - row.nondeductible_allowed
    basis -= row.nondeductible_allowed
    if nondeductible_excess > CENT:
        flag(
            "NONDEDUCTIBLE_OVER_BASIS",
            "Nondeductible expenses exceed remaining basis; excess is not carried forward. Review treatment.",
            nondeductible_excess,
        )

    # 4. Losses, limited to basis (IRC 704(d))
    current_ordinary = max(-k1.ordinary_income, 0)
    current_capital = max(-k1.net_capital_gain, 0)
    row.current_losses = current_ordinary + current_capital
    pool_ordinary = current_ordinary + state.suspended_ordinary
    pool_capital = current_capital + state.suspended_capital
    pool = pool_ordinary + pool_capital
    row.losses_allowed = min(pool, basis)
    suspended_total = pool - row.losses_allowed
    new_suspended_ordinary = suspended_total * pool_ordinary / pool if pool else 0.0
    new_suspended_capital = suspended_total - new_suspended_ordinary
    basis -= row.losses_allowed
    if pool - row.losses_allowed > CENT:
        flag(
            "704D_LIMIT",
            f"Losses of {pool:,.0f} exceed basis of {row.losses_allowed:,.0f}; "
            f"{pool - row.losses_allowed:,.0f} suspended under IRC 704(d).",
            pool - row.losses_allowed,
        )
    elif state.suspended > CENT:
        flag(
            "SUSPENDED_LOSS_RELEASED",
            f"Prior-year suspended losses of {state.suspended:,.0f} are now allowed.",
            state.suspended,
        )

    # Tax-basis capital account: full income and losses, actual cash only.
    row.net_income_for_capital = (
        k1.ordinary_income + k1.interest_income + k1.net_capital_gain + k1.tax_exempt_income
    )
    capital = (
        state.capital + k1.contributions + row.net_income_for_capital
        - k1.nondeductible_expenses - distributions
    )

    explained = state.explained + row.gain_on_distributions + nondeductible_excess
    explained += (new_suspended_ordinary + new_suspended_capital) - state.suspended

    # 5. Buyout
    if buyout and buyout.effective.year == k1.tax_year:
        row.status = f"Bought out {buyout.effective:%m/%d/%Y}"
        suspended = new_suspended_ordinary + new_suspended_capital
        if suspended > CENT:
            row.suspended_losses_forfeited = suspended
            flag(
                "SUSPENDED_LOSS_FORFEITED",
                f"Suspended losses of {suspended:,.0f} are lost when the interest is liquidated.",
                suspended,
            )
            new_suspended_ordinary = new_suspended_capital = 0.0
        row.capital_closed_on_liquidation = -capital
        explained += capital
        capital = 0.0
        state.liquidated = True
        if buyout.method != "Lump sum":
            flag(
                "INSTALLMENT_BUYOUT",
                f"Buyout of {buyout.price:,.0f} paid in {buyout.num_payments} quarterly installments. "
                "Partner stays a partner until paid off; basis is recovered first (Reg. 1.736-1(b)(6)).",
                buyout.price,
            )
    elif state.liquidated:
        row.status = "Receiving buyout payments"

    for payment in payments:
        before = basis
        recovered = min(payment.amount, basis)
        gain = payment.amount - recovered
        basis -= recovered
        loss = 0.0
        if payment.is_final and basis > CENT:
            loss = basis
            basis = 0.0
        explained -= recovered + loss
        row.liquidating_payments += payment.amount
        row.liquidation_gain += gain
        row.liquidation_loss += loss
        results.payments.append(PaymentResult(payment, before, recovered, gain, loss, basis))
        if payment.is_final and not row.status.startswith("Bought out"):
            row.status = "Paid off"

    if row.liquidation_gain > CENT:
        flag("LIQUIDATION_GAIN", f"Gain of {row.liquidation_gain:,.0f} on buyout payments.", row.liquidation_gain)
    if row.liquidation_loss > CENT:
        flag("LIQUIDATION_LOSS", f"Loss of {row.liquidation_loss:,.0f} on final buyout payment.", row.liquidation_loss)
    if capital < -CENT and state.capital >= -CENT:
        flag(
            "NEGATIVE_TAX_CAPITAL",
            f"Tax-basis capital account turned negative ({capital:,.0f}); basis is supported by debt.",
            capital,
        )

    # Save state and finish the row
    state.basis = basis
    state.capital = capital
    state.liabilities = k1.liability_share_end
    state.suspended_ordinary = new_suspended_ordinary
    state.suspended_capital = new_suspended_capital
    state.explained = explained

    row.suspended_losses_end = state.suspended
    row.ending_basis = basis
    row.ending_capital = capital
    row.ending_liabilities = state.liabilities
    row.basis_capital_difference = basis - capital - state.liabilities
    row.explained_difference = explained
    if abs(row.unexplained_difference) > 1:
        flag("RECONCILIATION", "Basis does not reconcile to capital plus liabilities.", row.unexplained_difference)
    return row
