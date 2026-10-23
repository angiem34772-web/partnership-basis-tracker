from datetime import date
from pathlib import Path

import pytest

from basis_tracker.buyouts import payment_schedule
from basis_tracker.loader import Inputs, load_inputs
from basis_tracker.models import BuyoutAgreement, Distribution, Division, Entity, K1Input, Partner
from basis_tracker.rollforward import run


def make_inputs(k1s, distributions=(), divisions=(), buyouts=()):
    return Inputs(
        entities=[
            Entity("A", "Alpha LP", date(2020, 1, 1), "Cash"),
            Entity("B", "Beta LP", date(2022, 1, 1), "Division of A"),
        ],
        partners=[Partner("P1", "Test Partner", "Individual", date(2020, 1, 1), "Seed investor")],
        k1s=list(k1s),
        distributions=list(distributions),
        divisions=list(divisions),
        buyouts=list(buyouts),
    )


def row(results, year, entity="A"):
    return next(y for y in results.years if y.tax_year == year and y.entity_id == entity)


def codes(results):
    return {f.code for f in results.flags}


def test_basic_rollforward_order():
    results = run(make_inputs(
        [K1Input("P1", "A", 2020, contributions=100_000, ordinary_income=20_000, tax_exempt_income=1_000,
                 nondeductible_expenses=500, liability_share_end=50_000)],
        [Distribution("P1", "A", date(2020, 12, 31), 10_000)],
    ))
    y = row(results, 2020)
    assert y.ending_basis == pytest.approx(100_000 + 20_000 + 1_000 + 50_000 - 10_000 - 500)
    assert y.ending_capital == pytest.approx(100_000 + 20_000 + 1_000 - 500 - 10_000)
    assert y.unexplained_difference == 0


def test_loss_limited_to_basis_and_carried_forward():
    results = run(make_inputs([
        K1Input("P1", "A", 2020, contributions=10_000, ordinary_income=-25_000),
        K1Input("P1", "A", 2021, ordinary_income=40_000),
    ]))
    first, second = row(results, 2020), row(results, 2021)
    assert first.losses_allowed == 10_000
    assert first.suspended_losses_end == 15_000
    assert first.ending_basis == 0
    assert first.ending_capital == -15_000  # capital takes the full loss
    assert second.losses_allowed == 15_000
    assert second.ending_basis == 25_000
    assert {"704D_LIMIT", "SUSPENDED_LOSS_RELEASED"} <= codes(results)


def test_distributions_reduce_basis_before_losses():
    # Reg. 1.704-1(d)(2): the distribution comes off first, so the loss is limited.
    results = run(make_inputs(
        [K1Input("P1", "A", 2020, contributions=10_000, ordinary_income=-8_000)],
        [Distribution("P1", "A", date(2020, 6, 30), 5_000)],
    ))
    y = row(results, 2020)
    assert y.losses_allowed == 5_000
    assert y.suspended_losses_end == 3_000


def test_liability_decrease_is_deemed_distribution_with_731_gain():
    results = run(make_inputs([
        K1Input("P1", "A", 2020, contributions=1_000, ordinary_income=-5_000, liability_share_end=20_000),
        K1Input("P1", "A", 2021, liability_share_end=0),
    ]))
    y = row(results, 2021)
    assert y.beginning_basis == 16_000
    assert y.liability_decrease == 20_000
    assert y.gain_on_distributions == 4_000
    assert y.ending_basis == 0
    assert y.unexplained_difference == 0


def test_731_gain_when_cash_exceeds_basis():
    results = run(make_inputs(
        [K1Input("P1", "A", 2020, contributions=5_000)],
        [Distribution("P1", "A", date(2020, 12, 31), 7_000)],
    ))
    y = row(results, 2020)
    assert y.gain_on_distributions == 2_000
    assert y.ending_basis == 0
    assert y.unexplained_difference == 0
    assert "731_GAIN" in codes(results)


def test_division_splits_basis_capital_and_debt():
    results = run(make_inputs(
        [
            K1Input("P1", "A", 2021, contributions=100_000, liability_share_end=50_000),
            K1Input("P1", "A", 2022, liability_share_end=30_000),
            K1Input("P1", "B", 2022, liability_share_end=20_000),
        ],
        divisions=[Division(date(2022, 1, 1), "A", "B", 0.40)],
    ))
    a, b = row(results, 2022, "A"), row(results, 2022, "B")
    assert b.division_adjustment == pytest.approx(60_000)
    assert a.division_adjustment == pytest.approx(-60_000)
    assert a.ending_basis + b.ending_basis == pytest.approx(150_000)
    assert b.ending_capital == pytest.approx(40_000)
    assert a.unexplained_difference == 0 and b.unexplained_difference == 0


def test_installment_buyout_recovers_basis_first_then_gain():
    buyout = BuyoutAgreement("P1", "A", date(2021, 12, 31), 40_000, "Installment", 4, date(2022, 3, 31))
    results = run(make_inputs(
        [K1Input("P1", "A", 2020, contributions=25_000), K1Input("P1", "A", 2021)],
        buyouts=[buyout],
    ))
    gains = [p.gain for p in results.payments]
    recovered = [p.basis_recovered for p in results.payments]
    assert recovered == [10_000, 10_000, 5_000, 0]
    assert gains == [0, 0, 5_000, 10_000]
    assert row(results, 2022).status == "Paid off"


def test_buyout_forfeits_suspended_losses():
    buyout = BuyoutAgreement("P1", "A", date(2021, 6, 30), 4_000, "Lump sum")
    results = run(make_inputs(
        [K1Input("P1", "A", 2020, contributions=10_000, ordinary_income=-12_000), K1Input("P1", "A", 2021)],
        buyouts=[buyout],
    ))
    y = row(results, 2021)
    assert y.suspended_losses_forfeited == 2_000
    assert y.liquidation_gain == 4_000
    assert y.ending_basis == 0 and y.ending_capital == 0
    assert y.unexplained_difference == 0
    assert "SUSPENDED_LOSS_FORFEITED" in codes(results)


def test_lump_sum_loss_on_cash_only_liquidation():
    buyout = BuyoutAgreement("P1", "A", date(2021, 6, 30), 4_000, "Lump sum")
    results = run(make_inputs(
        [K1Input("P1", "A", 2020, contributions=10_000), K1Input("P1", "A", 2021)],
        buyouts=[buyout],
    ))
    y = row(results, 2021)
    assert y.liquidation_loss == 6_000
    assert y.ending_capital == 0
    assert "LIQUIDATION_LOSS" in codes(results)


def test_payment_schedule_totals_price_and_ends_on_quarter_end():
    schedule = payment_schedule(
        BuyoutAgreement("P1", "A", date(2025, 6, 30), 100_000.01, "Installment", 20, date(2025, 9, 30))
    )
    assert len(schedule) == 20
    assert sum(p.amount for p in schedule) == pytest.approx(100_000.01)
    assert schedule[1].paid_on == date(2025, 12, 31)
    assert schedule[-1].paid_on == date(2030, 6, 30)


def test_sample_data_reconciles_every_year():
    results = run(load_inputs(Path(__file__).parent.parent / "sample_data"))
    assert results.years
    assert all(abs(y.unexplained_difference) <= 1 for y in results.years)
    assert {"704D_LIMIT", "731_GAIN", "SUSPENDED_LOSS_RELEASED", "INSTALLMENT_BUYOUT"} <= codes(results)
