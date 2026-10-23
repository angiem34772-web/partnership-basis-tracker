"""Generate the made-up sample partnership used by the tracker.

Everything here is fictional. It plays the role of the partnership's tax
preparer: it builds the partnership-level story and writes the K-1 style
inputs the tracker reads. The tracker itself never sees this script.

The story
---------
* 2008: Maple Hollow Partners LP (MHP) is formed by 5 seed investors.
* 2009-2021: 20 more investors buy in by contributing cash at the current
  unit value. Two partners are bought out for a lump sum (2014 and 2019).
* Distributions are paid quarterly. A 2016 refinancing funds a special
  distribution, and a 2020 loss year comes with a required loan paydown.
* 2022: MHP divides. Its development business moves to Maple Hollow
  Development LP (MHD), owned by the same partners in the same percentages.
* 2025: 5 partners are bought out of both partnerships effective June 30.
  One takes a lump sum; four take 20 quarterly payments through mid-2030.

Run:  python sample_data/generate_sample_data.py
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

OUT = Path(__file__).parent

ENTITIES = [
    ("MHP", "Maple Hollow Partners LP", date(2008, 1, 1), "Cash contributions from seed investors"),
    ("MHD", "Maple Hollow Development LP", date(2022, 1, 1), "Division of MHP (IRC 708(b)(2)(B))"),
]
DIVISION_DATE = date(2022, 1, 1)
DIVISION_PCT = 0.40  # share of MHP's inside basis and debt moved to MHD

# (id, name, type, admitted, units)
SEED_PARTNERS = [
    ("P01", "Alder Creek Family Trust", "Trust", 1200),
    ("P02", "Dana Whitfield", "Individual", 1000),
    ("P03", "Bramble Point Capital LLC", "LLC", 800),
    ("P04", "Marcus Ellery", "Individual", 600),
    ("P05", "Priya Raman", "Individual", 400),
]
BUY_INS = [
    ("P06", "Thornbury Holdings LLC", "LLC", date(2009, 4, 1), 200),
    ("P07", "Lena Okafor", "Individual", date(2009, 10, 1), 150),
    ("P08", "Gideon Marsh", "Individual", date(2010, 7, 1), 250),
    ("P09", "Copperleaf Ventures LLC", "LLC", date(2011, 1, 1), 300),
    ("P10", "Hollis Grant", "Individual", date(2011, 7, 1), 120),
    ("P11", "Wren Family Trust", "Trust", date(2012, 4, 1), 200),
    ("P12", "Sofia Delgado", "Individual", date(2012, 10, 1), 180),
    ("P13", "Northgate Partners LLC", "LLC", date(2013, 7, 1), 220),
    ("P14", "Ivan Petrov", "Individual", date(2014, 1, 1), 150),
    ("P15", "Juniper Lane Trust", "Trust", date(2014, 10, 1), 260),
    ("P16", "Caleb Fontaine", "Individual", date(2015, 4, 1), 100),
    ("P17", "Ridgeway Equity LLC", "LLC", date(2016, 1, 1), 300),
    ("P18", "Mei Tanaka", "Individual", date(2016, 10, 1), 140),
    ("P19", "Oakmont Family Trust", "Trust", date(2017, 7, 1), 200),
    ("P20", "Rafael Moreno", "Individual", date(2018, 1, 1), 160),
    ("P21", "Silverline Holdings LLC", "LLC", date(2018, 10, 1), 240),
    ("P22", "Nora Lindqvist", "Individual", date(2019, 4, 1), 120),
    ("P23", "Harbor Light Capital LLC", "LLC", date(2020, 1, 1), 180),
    ("P24", "Theo Vance", "Individual", date(2020, 10, 1), 150),
    ("P25", "Elm Street Family Trust", "Trust", date(2021, 7, 1), 200),
]
# (partner, effective date, method, number of quarterly payments)
BUYOUTS = [
    ("P04", date(2014, 6, 30), "Lump sum", 1),
    ("P09", date(2019, 12, 31), "Lump sum", 1),
    ("P02", date(2025, 6, 30), "Lump sum", 1),
    ("P07", date(2025, 6, 30), "Installment", 20),
    ("P12", date(2025, 6, 30), "Installment", 20),
    ("P15", date(2025, 6, 30), "Installment", 20),
    ("P20", date(2025, 6, 30), "Installment", 20),
]
INSTALLMENT_START = date(2025, 9, 30)

# Fair value per unit on January 1 (combined business before the division).
UNIT_VALUE = {
    2008: 1000, 2009: 880, 2010: 900, 2011: 950, 2012: 1010, 2013: 1080, 2014: 1150,
    2015: 1230, 2016: 1300, 2017: 1380, 2018: 1460, 2019: 1540, 2020: 1600, 2021: 1520,
    2022: 1650, 2023: 1740, 2024: 1830, 2025: 1920, 2026: 2010,
}
VALUE_SPLIT = {"MHP": 0.60, "MHD": 0.40}  # after the division

# Partnership-level results: (ordinary income, interest, net capital gain,
# tax-exempt income, nondeductible expenses, year-end debt)
RESULTS = {
    "MHP": {
        2008: (-2_400_000, 40_000, 0, 12_000, 18_000, 6_000_000),
        2009: (-1_500_000, 25_000, -300_000, 10_000, 15_000, 5_800_000),
        2010: (-300_000, 22_000, 0, 9_000, 14_000, 5_600_000),
        2011: (450_000, 24_000, 0, 9_000, 16_000, 5_400_000),
        2012: (900_000, 26_000, 0, 11_000, 18_000, 5_200_000),
        2013: (1_300_000, 30_000, 400_000, 12_000, 20_000, 5_000_000),
        2014: (1_600_000, 32_000, 0, 14_000, 22_000, 4_800_000),
        2015: (1_900_000, 35_000, 0, 15_000, 24_000, 4_600_000),
        2016: (2_100_000, 38_000, 0, 16_000, 26_000, 18_000_000),
        2017: (2_400_000, 45_000, 1_200_000, 18_000, 28_000, 17_500_000),
        2018: (2_600_000, 52_000, 0, 20_000, 30_000, 17_000_000),
        2019: (2_800_000, 60_000, 0, 22_000, 32_000, 16_500_000),
        2020: (-3_200_000, 20_000, 0, 15_000, 20_000, 8_000_000),
        2021: (1_500_000, 18_000, 600_000, 14_000, 22_000, 7_800_000),
        2022: (1_800_000, 30_000, 0, 10_000, 18_000, 4_600_000),
        2023: (2_000_000, 55_000, 500_000, 11_000, 19_000, 4_400_000),
        2024: (2_200_000, 62_000, 0, 12_000, 20_000, 4_200_000),
        2025: (2_300_000, 58_000, 0, 12_000, 21_000, 4_000_000),
    },
    "MHD": {
        2022: (-3_000_000, 8_000, 0, 0, 9_000, 3_000_000),
        2023: (-1_200_000, 10_000, 0, 0, 10_000, 2_900_000),
        2024: (1_600_000, 12_000, 0, 0, 11_000, 6_000_000),
        2025: (1_800_000, 15_000, 300_000, 0, 12_000, 5_800_000),
    },
}
DISTRIBUTION_RATE = 0.45  # quarterly draws total 45% of prior-year ordinary income
SPECIAL_DISTRIBUTIONS = [("MHP", date(2016, 9, 30), 12_000_000, "Special - refinancing proceeds")]


def quarters(year: int):
    """(start, end) dates for each calendar quarter."""
    ends = [date(year, 3, 31), date(year, 6, 30), date(year, 9, 30), date(year, 12, 31)]
    starts = [date(year, 1, 1), date(year, 4, 1), date(year, 7, 1), date(year, 10, 1)]
    return list(zip(starts, ends))


def unit_value(entity: str, on: date) -> float:
    """Linear interpolation of the January 1 values; split after the division."""
    start, nxt = UNIT_VALUE[on.year], UNIT_VALUE[on.year + 1]
    fraction = (on - date(on.year, 1, 1)).days / 365
    value = start + (nxt - start) * fraction
    return value * VALUE_SPLIT[entity] if on >= DIVISION_DATE else value


def build():
    partners = []  # rows for partners.csv
    units = {}  # partner -> units
    admitted = {}
    contributions = []  # (partner, entity, date, amount)
    for pid, name, ptype, n in SEED_PARTNERS:
        partners.append((pid, name, ptype, date(2008, 1, 1), "Seed investor"))
        units[pid], admitted[pid] = n, date(2008, 1, 1)
        contributions.append((pid, "MHP", date(2008, 1, 1), n * 1000))
    for pid, name, ptype, when, n in BUY_INS:
        partners.append((pid, name, ptype, when, "Buy-in"))
        units[pid], admitted[pid] = n, when
        contributions.append((pid, "MHP", when, round(n * unit_value("MHP", when))))
    exits = {pid: when for pid, when, _, _ in BUYOUTS}

    def holders(on_start: date, on_end: date):
        """Partners holding units for the whole period (admitted at its start or
        earlier and not bought out before its end)."""
        return {
            p: u for p, u in units.items()
            if admitted[p] <= on_start and (p not in exits or exits[p] >= on_end)
        }

    k1 = {}  # (partner, entity, year) -> dict
    distributions = []

    def k1_row(pid, entity, year):
        return k1.setdefault((pid, entity, year), {
            "contributions": 0, "ordinary_income": 0.0, "interest_income": 0.0,
            "net_capital_gain": 0.0, "tax_exempt_income": 0.0,
            "nondeductible_expenses": 0.0, "liability_share_end": 0.0,
        })

    for pid, entity, when, amount in contributions:
        k1_row(pid, entity, when.year)["contributions"] += amount

    for entity, years in RESULTS.items():
        for year, (ordinary, interest, capgain, exempt, nondeductible, debt) in years.items():
            prior_income = years.get(year - 1, (0,))[0]
            if entity == "MHP" and year == DIVISION_DATE.year:
                prior_income *= 1 - DIVISION_PCT
            quarterly_draw = max(prior_income, 0) * DISTRIBUTION_RATE / 4
            for q_start, q_end in quarters(year):
                owners = holders(q_start, q_end)
                total = sum(owners.values())
                for pid, u in owners.items():
                    share = u / total
                    row = k1_row(pid, entity, year)
                    row["ordinary_income"] += ordinary / 4 * share
                    row["interest_income"] += interest / 4 * share
                    row["net_capital_gain"] += capgain / 4 * share
                    row["tax_exempt_income"] += exempt / 4 * share
                    row["nondeductible_expenses"] += nondeductible / 4 * share
                    if quarterly_draw:
                        distributions.append((pid, entity, q_end, round(quarterly_draw * share), "Regular"))
                for s_entity, s_date, s_amount, s_kind in SPECIAL_DISTRIBUTIONS:
                    if s_entity == entity and q_start <= s_date <= q_end:
                        for pid, u in owners.items():
                            distributions.append((pid, entity, s_date, round(s_amount * u / total), s_kind))
            year_end = date(year, 12, 31)
            owners = {p: u for p, u in units.items() if admitted[p] <= year_end and (p not in exits or exits[p] > year_end)}
            total = sum(owners.values())
            for pid in list(units):
                if (pid, entity, year) in k1:
                    k1[(pid, entity, year)]["liability_share_end"] = debt * owners.get(pid, 0) / total

    buyouts = []
    for pid, when, method, n in BUYOUTS:
        entities = ["MHP"] if when < DIVISION_DATE else ["MHP", "MHD"]
        for entity in entities:
            price = round(units[pid] * unit_value(entity, when))
            first = when if method == "Lump sum" else INSTALLMENT_START
            buyouts.append((pid, entity, when, price, method, n, first))

    return partners, k1, distributions, buyouts


def write():
    partners, k1, distributions, buyouts = build()

    def save(name, header, rows):
        with (OUT / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    save("entities.csv", ["entity_id", "name", "formed", "formed_by"], ENTITIES)
    save("partners.csv", ["partner_id", "name", "partner_type", "admitted", "admission_type"], partners)
    k1_fields = ["contributions", "ordinary_income", "interest_income", "net_capital_gain",
                 "tax_exempt_income", "nondeductible_expenses", "liability_share_end"]
    save(
        "k1_inputs.csv",
        ["partner_id", "entity_id", "tax_year", *k1_fields],
        [
            (pid, entity, year, *(round(row[f]) for f in k1_fields))
            for (pid, entity, year), row in sorted(k1.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0]))
        ],
    )
    save("distributions.csv", ["partner_id", "entity_id", "paid_on", "amount", "kind"],
         sorted(distributions, key=lambda r: (r[2], r[1], r[0])))
    save("divisions.csv", ["effective", "from_entity", "to_entity", "pct_transferred"],
         [(DIVISION_DATE, "MHP", "MHD", DIVISION_PCT)])
    save("buyouts.csv",
         ["partner_id", "entity_id", "effective", "price", "method", "num_payments", "first_payment"], buyouts)
    print(f"Wrote {len(partners)} partners, {len(k1)} K-1s, {len(distributions)} distributions, "
          f"{len(buyouts)} buyout agreements to {OUT}")


if __name__ == "__main__":
    write()
