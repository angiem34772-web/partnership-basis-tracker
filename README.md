# Partnership Basis Tracker

**A Python tool that tracks each partner's tax basis and capital account in a partnership, year by year, and flags the tax issues a preparer needs to catch.**

Built by an Enrolled Agent and corporate tax analyst who works on complex partnerships, to show how tax rules can be turned into tested, repeatable code.

> All data in this repository is made up. The partnerships, partners, and amounts are fictional.

---

## In plain English

When someone invests in a partnership, the IRS requires them to track their **basis**: roughly, how much they have invested, plus their share of profits and debt, minus losses and cash taken out. Basis decides whether a loss can be deducted this year, whether a cash distribution is taxable, and how much gain or loss a partner has when they leave.

Tracking it by hand in spreadsheets is slow and error-prone, especially over many years, with partners joining and leaving, and when a partnership splits in two. This project automates it:

1. **Reads** each partner's yearly K-1 amounts (the tax form partnerships send to their partners).
2. **Rolls basis and capital forward** every year, applying the IRS ordering rules.
3. **Flags problems** such as losses that can't be deducted yet and distributions that trigger tax.
4. **Handles the hard events**: a partnership split and partner buyouts paid as a lump sum or in installments.
5. **Exports a formatted Excel workbook** a reviewer can audit line by line.

It also checks its own math: every year, each partner's basis is reconciled to their capital account plus share of debt, and any difference has to be explained. On the sample data there are **0 unexplained differences across 430 partner-years**.

## Skills shown

| Area | What this project shows |
|---|---|
| Partnership tax | Outside basis, tax-basis capital, IRC 704(d) loss limits, 731 distributions, 752 liabilities, 708 divisions, 736 buyouts |
| Python | Clean package structure, dataclasses, a command line interface, no heavy dependencies |
| Data | CSV inputs, validation, a reproducible sample data generator |
| Excel | Formatted, filterable multi-tab report built with openpyxl |
| Quality | Automated tests with pytest, plus a built-in reconciliation check |

## The sample partnership

The sample data tells the story of a fictional real estate partnership, **Maple Hollow Partners LP**:

| Year | Event |
|---|---|
| 2008 | Formed by **5 seed investors** contributing $4.0 million. Start-up losses during the financial crisis. |
| 2009 to 2021 | **20 more investors buy in** at the current unit value. **2 partners are bought out** for a lump sum (2014 and 2019). |
| Every quarter | Cash **distributions** to partners, based on the prior year's income. |
| 2016 | Loan refinancing funds a $12 million special distribution. |
| 2020 | Loss year plus a required loan paydown, which counts as a deemed cash distribution. |
| 2022 | The partnership **divides in two**: the development business moves to **Maple Hollow Development LP**, with the same partners in the same percentages. |
| 2022 to 2023 | Development start-up losses exceed some partners' basis, so part of the loss is **suspended**, then released in 2024. |
| 2025 | **5 partners are bought out** of both partnerships. One takes a **lump sum**; four are paid in **20 quarterly installments** through mid-2030. |

### One partner's story

Priya Raman (P05), a seed investor, in Maple Hollow Development LP:

| Year | Loss reported | Loss allowed | Suspended (carried forward) | What happened |
|---|---:|---:|---:|---|
| 2022 | 173,410 | 98,663 | 74,747 | Loss is larger than basis, so the excess is suspended |
| 2023 | 69,364 | 0 | 144,111 | No basis left; a debt paydown also triggers 5,202 of taxable gain |
| 2024 | 0 | 144,111 | 0 | Profits and new debt restore basis; all suspended losses are released |

And Sofia Delgado (P12), bought out of Maple Hollow Partners LP for $212,153 in 20 quarterly payments: her first 17 payments are a tax-free recovery of her $186,504 basis, and gain starts with payment 18 in December 2029.

## The Excel report

Running the tool creates [`output/partnership_basis_report.xlsx`](output/partnership_basis_report.xlsx):

| Tab | What it shows |
|---|---|
| Summary | Partnerships, partner counts, and a count of every flag raised |
| Partner Summary | One line per partner per partnership: totals and where they stand now |
| Basis Rollforward | Year-by-year outside basis, in the IRS ordering, with flagged rows highlighted |
| Capital Accounts | Tax-basis capital, debt share, and the reconciliation check |
| Flags | Every issue found, with the amount and a plain-English explanation |
| Buyout Schedules | Each buyout payment: basis recovered, then gain or loss |
| 2022 Division | How each partner's basis, capital, and debt split between the two partnerships |
| K-1 Inputs | The starting data |

## How to run it

You need Python 3.10 or newer.

```bash
git clone https://github.com/angiem34772-web/partnership-basis-tracker.git
cd partnership-basis-tracker
pip install -r requirements.txt

python -m basis_tracker          # builds output/partnership_basis_report.xlsx
python -m pytest                 # runs the tests
```

To use your own data, put CSV files with the same columns as the ones in [`sample_data/`](sample_data/) in a folder and run:

```bash
python -m basis_tracker --data my_folder --out my_report.xlsx
```

To rebuild the sample data from scratch: `python sample_data/generate_sample_data.py`.

## Tax rules implemented

For reviewers with a tax background, here is what the engine does and where it comes from.

**Annual ordering** ([`rollforward.py`](basis_tracker/rollforward.py)), following IRC 705 and Treas. Reg. 1.704-1(d)(2):

1. Increase basis for contributions, taxable and tax-exempt income, and any increase in the partner's share of liabilities (IRC 752(a)).
2. Decrease basis for cash distributions and any net decrease in liability share, which is a deemed distribution (IRC 752(b)). Amounts over basis are gain under IRC 731(a)(1). Quarterly draws are tested at year end (Reg. 1.731-1(a)(1)(ii)).
3. Decrease basis for nondeductible, noncapital expenses.
4. Decrease basis for losses, limited to remaining basis (IRC 704(d)). The excess carries forward with its character (ordinary or capital) kept pro rata.

**Tax-basis capital account**: contributions plus all income, minus all losses (before the basis limit), nondeductible expenses, and cash distributions. Debt is excluded.

**Partnership division** ([`rollforward.py`](basis_tracker/rollforward.py)): treated as an assets-over division under IRC 708(b)(2)(B). Each partner's interest in the new partnership takes a carryover basis (IRC 732(a)), and basis, capital, liability share, and suspended losses are split in the same proportion as the inside basis that moved (40% in the sample).

**Buyouts** ([`buyouts.py`](basis_tracker/buyouts.py)): liquidating payments under IRC 736(b).
- A partner paid in installments remains a partner for tax purposes until the last payment (Reg. 1.736-1(a)(6)).
- Each payment recovers basis first, and gain is recognized only after basis is fully recovered (Reg. 1.736-1(b)(6)).
- Basis left after the final cash payment is a loss (IRC 731(a)(2)).
- The partner's capital account closes on the buyout date, and any suspended losses are forfeited.

## Assumptions and limits

This is a portfolio project, kept small on purpose. A production version would also need:

- IRC 754 elections and the 743(b) and 734(b) basis adjustments
- IRC 751 "hot assets" (unrealized receivables and inventory) on buyouts, and 736(a) payments
- At-risk (IRC 465) and passive activity (IRC 469) limits, which apply after the basis limit
- Book (704(b)) capital accounts, revaluations, and 704(c) allocations
- Liability allocation between recourse and nonrecourse debt (the sample allocates all debt by ownership percentage)
- Interest on installment buyout notes

## Project structure

```
basis_tracker/
  models.py           data structures for K-1 inputs, events, and results
  loader.py           reads and validates the CSV inputs
  rollforward.py      the basis and capital engine, division, and buyout handling
  buyouts.py          quarterly installment schedules
  excel_export.py     the formatted Excel report
  __main__.py         command line entry point
sample_data/          fictional input CSVs and the script that generates them
tests/                pytest tests for each tax rule
output/               the generated Excel report
```

## About me

I'm an Enrolled Agent (EA) and corporate tax analyst specializing in complex partnerships. I'm interested in roles where tax expertise meets automation and data.

Connect with me on [LinkedIn](https://www.linkedin.com/in/angie-jenkins-ea).

## License

MIT. See [LICENSE](LICENSE).
