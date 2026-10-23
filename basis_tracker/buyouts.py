"""Payment schedules for partner buyouts (liquidating distributions under IRC 736(b)).

A retiring partner paid over time stays a partner for tax purposes until the
last payment (Treas. Reg. 1.736-1(a)(6)). Unless the partner elects otherwise,
each payment first recovers outside basis, and gain is recognized only after
basis is fully recovered (Treas. Reg. 1.736-1(b)(6)). If basis is left after
the final cash payment, the remaining basis is a loss (IRC 731(a)(2)).
"""

from __future__ import annotations

import calendar
from datetime import date

from .models import BuyoutAgreement, Payment


def add_months(d: date, months: int) -> date:
    """Same day `months` later; a month-end date stays on the month end."""
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    if d.day == calendar.monthrange(d.year, d.month)[1]:
        return date(year, month, last_day)
    return date(year, month, min(d.day, last_day))


def payment_schedule(agreement: BuyoutAgreement) -> list[Payment]:
    """Equal quarterly payments; the last payment absorbs rounding."""
    if agreement.method == "Lump sum" or agreement.num_payments <= 1:
        when = agreement.first_payment or agreement.effective
        return [Payment(agreement.partner_id, agreement.entity_id, when, round(agreement.price, 2), 1, 1)]

    n = agreement.num_payments
    first = agreement.first_payment or add_months(agreement.effective, 3)
    regular = round(agreement.price / n, 2)
    payments = []
    for i in range(n):
        amount = regular if i < n - 1 else round(agreement.price - regular * (n - 1), 2)
        payments.append(
            Payment(agreement.partner_id, agreement.entity_id, add_months(first, 3 * i), amount, i + 1, n)
        )
    return payments
