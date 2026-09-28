"""Build a synthetic payables book and write an exception memo from SQL.

Money is integer euros. The population is fictional. The four queries are the
analysis: duplicates, split purchases, a contract price left behind, and VAT
booked at the pre-2025 rate.
"""

from __future__ import annotations

import html
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "payables.db"
REPORT_PATH = ROOT / "report" / "index.html"
SQL = {name: (ROOT / "sql" / name).read_text(encoding="utf-8") for name in (
    "01_duplicates.sql",
    "02_split_purchases.sql",
    "03_price_drift.sql",
    "04_vat_rate.sql",
)}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE vendors (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  contract_unit_eur INTEGER,
  vat_bps INTEGER NOT NULL,
  solo_limit_eur INTEGER NOT NULL
);

CREATE TABLE invoices (
  id INTEGER PRIMARY KEY,
  vendor_id INTEGER NOT NULL REFERENCES vendors(id),
  invoice_no TEXT NOT NULL,
  invoice_date TEXT NOT NULL,
  sku TEXT NOT NULL,
  qty INTEGER NOT NULL,
  unit_eur INTEGER NOT NULL,
  net_eur INTEGER NOT NULL,
  vat_eur INTEGER NOT NULL,
  gross_eur INTEGER NOT NULL,
  booked_vat_bps INTEGER NOT NULL,
  entered_by TEXT NOT NULL
);
"""

VENDORS = [
    ("North Paper s.r.o.", "Office", None, 2300, 20000),
    ("Lumen Facilities s.r.o.", "Facilities", None, 2300, 5000),
    ("Danube Hosting s.r.o.", "IT", 42, 2300, 20000),
    ("Karpat Clean s.r.o.", "Facilities", None, 2300, 20000),
    ("Hron Print s.r.o.", "Office", None, 2300, 20000),
    ("Vah Courier s.r.o.", "Logistics", None, 2300, 20000),
    ("Orava Legal s.r.o.", "Professional", None, 2300, 20000),
    ("Myjava Catering s.r.o.", "Office", None, 2300, 20000),
    ("Ipel Security s.r.o.", "Facilities", None, 2300, 20000),
    ("Topla Studio s.r.o.", "Marketing", None, 2300, 20000),
    ("Rimava Parts s.r.o.", "Maintenance", None, 2300, 20000),
    ("Nitra Energy s.r.o.", "Utilities", None, 2300, 20000),
]


def euro(amount: int) -> str:
    return f"€{amount:,.0f}"


def build_db() -> None:
    rng = random.Random(11)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO vendors (id, name, category, contract_unit_eur, vat_bps, solo_limit_eur) VALUES (?, ?, ?, ?, ?, ?)",
        [(i + 1, *vendor) for i, vendor in enumerate(VENDORS)],
    )

    rows: list[tuple] = []
    next_id = 1

    def add(vendor_id, number, date, sku, qty, unit, vat_bps, clerk):
        nonlocal next_id
        net = qty * unit
        vat = net * vat_bps // 10000
        rows.append((next_id, vendor_id, number, date, sku, qty, unit, net, vat, net + vat, vat_bps, clerk))
        next_id += 1

    # Ordinary book: small invoices, correct 23% VAT, unique numbers.
    for month in range(1, 19):
        year = 2025 + (month - 1) // 12
        mon = (month - 1) % 12 + 1
        for vendor_id in range(1, len(VENDORS) + 1):
            if vendor_id == 3:
                continue  # Danube Hosting is the contract series below
            for copy in range(rng.randint(2, 4)):
                day = rng.randint(1, 27)
                unit = rng.randint(40, 180)
                qty = rng.randint(1, 12)
                add(
                    vendor_id,
                    f"N{vendor_id:02d}-{year}{mon:02d}-{copy+1}",
                    f"{year}-{mon:02d}-{day:02d}",
                    "GEN",
                    qty,
                    unit,
                    2300,
                    rng.choice(("h.kovac", "m.sisak", "a.nemecek")),
                )

    # 12 exact duplicates. Second copy three days later, same number and money.
    duplicate_specs = [
        (1, "NP-1044", "2025-03-04", "2025-03-07", 80, 52),
        (1, "NP-1102", "2025-06-11", "2025-06-14", 40, 96),
        (5, "HP-220", "2025-04-02", "2025-04-05", 25, 188),
        (5, "HP-261", "2025-09-16", "2025-09-19", 60, 74),
        (4, "KC-88", "2025-05-20", "2025-05-23", 12, 210),
        (4, "KC-103", "2025-11-03", "2025-11-06", 18, 160),
        (6, "VC-17", "2025-07-08", "2025-07-11", 30, 95),
        (6, "VC-29", "2026-01-13", "2026-01-16", 22, 140),
        (9, "IS-55", "2025-08-19", "2025-08-22", 8, 640),
        (9, "IS-71", "2026-02-09", "2026-02-12", 6, 890),
        (10, "TS-14", "2025-10-21", "2025-10-24", 15, 320),
        (12, "NE-40", "2026-03-02", "2026-03-05", 10, 540),
    ]
    for vendor_id, number, first, second, qty, unit in duplicate_specs:
        add(vendor_id, number, first, "GEN", qty, unit, 2300, "h.kovac")
        add(vendor_id, number, second, "GEN", qty, unit, 2300, "import.batch")

    # Lumen Facilities: pairs that each sit under €5,000 and together cross it.
    lumen_pairs = [
        ("LF-501", "LF-502", "2025-04-07", "2025-04-10", 2400, 2700),
        ("LF-518", "LF-519", "2025-05-12", "2025-05-15", 2600, 2550),
        ("LF-540", "LF-541", "2025-07-01", "2025-07-04", 3100, 2200),
        ("LF-560", "LF-562", "2025-09-08", "2025-09-11", 2800, 2900),
        ("LF-588", "LF-590", "2025-11-18", "2025-11-21", 3300, 2200),
        ("LF-601", "LF-603", "2026-01-06", "2026-01-09", 2500, 2650),
        ("LF-620", "LF-621", "2026-03-16", "2026-03-19", 3600, 2100),
        ("LF-644", "LF-646", "2026-05-04", "2026-05-07", 2950, 2400),
    ]
    for first_no, second_no, first_date, second_date, first_net, second_net in lumen_pairs:
        add(2, first_no, first_date, "CALLOUT", 1, first_net, 2300, "m.sisak")
        add(2, second_no, second_date, "CALLOUT", 1, second_net, 2300, "m.sisak")

    # Danube Hosting: one seat invoice a month. Contract stays at €42.
    drift = [42, 42, 42, 45, 48, 51, 54, 58, 62, 66, 70, 74]
    for index, unit in enumerate(drift):
        year = 2025 + (6 + index) // 12
        mon = (6 + index) % 12 + 1
        add(3, f"DH-{year}{mon:02d}", f"{year}-{mon:02d}-15", "SEAT-HOST", 90, unit, 2300, "a.nemecek")

    # Eighteen service invoices booked at the old 20% standard rate.
    for index in range(18):
        year = 2025 + index // 12
        mon = index % 12 + 1
        add(7, f"OL-VAT-{index+1:02d}", f"{year}-{mon:02d}-20", "ADVICE", 1, 8000, 2000, "h.kovac")

    conn.executemany(
        """
        INSERT INTO invoices (
          id, vendor_id, invoice_no, invoice_date, sku, qty, unit_eur,
          net_eur, vat_eur, gross_eur, booked_vat_bps, entered_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def query(name: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(SQL[name]))
    finally:
        conn.close()


def bars(values: list[int]) -> str:
    peak = max(values) or 1
    rects = []
    for index, value in enumerate(values):
        height = round(120 * value / peak)
        x = 28 + index * 36
        y = 140 - height
        rects.append(f'<rect x="{x}" y="{y}" width="22" height="{height}" fill="#111"/>')
        rects.append(f'<text x="{x + 11}" y="156" text-anchor="middle" font-size="9" fill="#555">{index + 1}</text>')
    return (
        '<svg viewBox="0 0 470 170" role="img" aria-label="Exception euros by quarter">'
        + "".join(rects)
        + "</svg>"
    )


def quarter_key(date: str) -> int:
    year, month, _day = date.split("-")
    return (int(year) - 2025) * 4 + (int(month) - 1) // 3


def render() -> None:
    duplicates = query("01_duplicates.sql")
    splits = query("02_split_purchases.sql")
    drift = query("03_price_drift.sql")
    vat_rows = query("04_vat_rate.sql")

    duplicate_eur = sum(row["gross_eur"] for row in duplicates)
    split_excess = sum(row["combined_net_eur"] - row["solo_limit_eur"] for row in splits)
    overcharge = sum(row["overcharge_eur"] for row in drift)
    vat_gap = sum(row["vat_gap_eur"] for row in vat_rows)
    total = duplicate_eur + overcharge + vat_gap

    if not (len(duplicates) == 12 and len(splits) == 8 and overcharge == 13500 and len(vat_rows) == 18 and vat_gap > 0):
        raise SystemExit(
            f"story drifted duplicates={len(duplicates)} splits={len(splits)} "
            f"overcharge={overcharge} vat={vat_gap}"
        )

    quarters = [0] * 6
    for row in duplicates:
        quarters[min(quarter_key(row["second_date"]), 5)] += row["gross_eur"]
    for row in drift:
        if row["overcharge_eur"]:
            quarters[min(quarter_key(row["month"] + "-15"), 5)] += row["overcharge_eur"]
    for row in vat_rows:
        quarters[min(quarter_key(row["invoice_date"]), 5)] += row["vat_gap_eur"]

    duplicate_lines = "\n".join(
        f"<tr><td>{html.escape(row['vendor'])}</td><td>{html.escape(row['invoice_no'])}</td>"
        f"<td>{row['first_date']}</td><td>{row['second_date']}</td><td class='num'>{euro(row['gross_eur'])}</td></tr>"
        for row in duplicates
    )
    drift_lines = "\n".join(
        f"<tr><td>{row['month']}</td><td class='num'>{euro(row['unit_eur'])}</td>"
        f"<td class='num'>{euro(row['contract_unit_eur'])}</td>"
        f"<td class='num'>{euro(row['overcharge_eur'])}</td></tr>"
        for row in drift
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Payables exception memo</title>
  <style>
    body {{ margin: 0; background: #fff; color: #111; font-family: Cambria, Georgia, serif; }}
    main {{ width: min(740px, calc(100% - 40px)); margin: 0 auto; padding: 48px 0 72px; }}
    .kicker {{ font-family: "Segoe UI", sans-serif; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; margin: 0 0 18px; }}
    h1 {{ font-size: 42px; line-height: 1.05; font-weight: 500; margin: 0 0 16px; }}
    h2 {{ font-size: 26px; font-weight: 500; margin: 0; }}
    .deck {{ font-size: 20px; line-height: 1.4; margin: 0 0 28px; }}
    .rule {{ border: 0; border-top: 4px solid #111; margin: 0 0 22px; }}
    .total {{ font-family: "Segoe UI", sans-serif; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; }}
    .total b {{ display: block; font-family: Cambria, Georgia, serif; font-size: 56px; letter-spacing: -0.03em; font-weight: 500; color: #9f1d1d; }}
    figure {{ margin: 28px 0; }}
    figcaption, .note, footer {{ font-family: "Segoe UI", sans-serif; color: #444; font-size: 13px; }}
    svg {{ width: 100%; height: auto; }}
    section {{ padding: 22px 0; border-top: 1px solid #111; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; font-family: "Segoe UI", sans-serif; }}
    table {{ width: 100%; border-collapse: collapse; font-family: "Segoe UI", sans-serif; font-size: 14px; }}
    th, td {{ text-align: left; padding: 6px 4px; border-bottom: 1px solid #ddd; vertical-align: top; }}
    th {{ font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }}
    p {{ line-height: 1.5; }}
    pre {{ background: #f4f4f4; padding: 12px; overflow: auto; font-size: 12px; line-height: 1.45; }}
  </style>
</head>
<body>
<main>
  <p class="kicker">Exception memo · Atelier Ledger s.r.o. · Bratislava · 23 Sep 2026</p>
  <hr class="rule" />
  <h1>The payables book paid {euro(total)} it did not owe.</h1>
  <p class="deck">Four checks on a synthetic invoice population. No model. A join, a date window, a lag, and a rate that changed on 1 January 2025.</p>
  <p class="total">Money that should not have left the account<b>{euro(total)}</b></p>
  <figure>
    {bars(quarters)}
    <figcaption>Figure 1. Euros in the exception set by quarter, from Q1 2025. Duplicates, the hosting overcharge, and the VAT gap. Split purchases are a control break, not cash already lost, so they are not in the total or the bars.</figcaption>
  </figure>

  <section>
    <h2>01 · Twelve invoices were paid twice</h2>
    <p>{euro(duplicate_eur)} left the account a second time. The match is strict: same supplier, same invoice number, same gross. The second copy arrived three days later and was entered by <span>import.batch</span>, not by the clerk who booked the original. That is an interface failure, not twelve independent mistakes.</p>
    <table>
      <thead><tr><th>Supplier</th><th>Number</th><th>First</th><th>Second</th><th>Gross</th></tr></thead>
      <tbody>{duplicate_lines}</tbody>
    </table>
    <p class="note">Query: sql/01_duplicates.sql. The self-join keeps the later row as the duplicate by ordering on id.</p>
  </section>

  <section>
    <h2>02 · Eight purchases walked around a €5,000 signature</h2>
    <p>Lumen Facilities has a single-signature limit of €5,000 net. These eight pairs use different invoice numbers, each under the line, three or four days apart. Together they clear it by {euro(split_excess)}. This memo does not call that fraud. It calls it a control that can be stepped over. A reviewer who only sorts by amount, one invoice at a time, will not see it. The same-number duplicates from finding 01 are excluded here on purpose.</p>
    <p class="note">Query: sql/02_split_purchases.sql. The window is six days. Both legs have to be material, above 40% of the limit, so two tiny invoices cannot fake a pair.</p>
  </section>

  <section>
    <h2>03 · The hosting contract stayed at €42. The invoices did not.</h2>
    <p>Danube Hosting bills 90 seats a month. The contract price is €42. From the fourth month the unit price steps up, to €74 at the end. The lag against the prior month is in the query. The sum of the gap is {euro(overcharge)}.</p>
    <table>
      <thead><tr><th>Month</th><th>Billed</th><th>Contract</th><th>Overcharge</th></tr></thead>
      <tbody>{drift_lines}</tbody>
    </table>
    <p class="note">Query: sql/03_price_drift.sql. LAG(unit_eur) is the month-to-month change. The contract column does not move.</p>
  </section>

  <section>
    <h2>04 · Eighteen invoices still use the old 20% VAT</h2>
    <p>From 1 January 2025 the standard Slovak VAT rate is 23%. The vendor master on these suppliers is 23%. Eighteen service invoices were booked at 20%, the previous standard rate. The tax gap is {euro(vat_gap)}. The cash already paid is not the whole point. The return is wrong, and a later correction is more expensive than the booking.</p>
    <p class="note">Query: sql/04_vat_rate.sql. Gap = net × (master rate − booked rate). Rates are stored in basis points so 23% is 2300 and the arithmetic stays in integers.</p>
  </section>

  <section>
    <h2>What was not counted</h2>
    <p>Late-payment interest, foreign currency, and credit notes. A duplicate that was credited back would fall out of the join only if the credit carried the same invoice number and the same gross with the opposite sign. This book has no such credits. Adding them without a test would make the €{total:,.0f} look cleaner than the ledger is.</p>
    <p>The companies are fictional. The rate change is not: standard Slovak VAT moved from 20% to 23% on 1 January 2025.</p>
  </section>
  <footer>Generated from data/payables.db by build_report.py. Re-run the script and the sentences move with the queries.</footer>
</main>
</body>
</html>
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(page, encoding="utf-8")
    print(f"duplicates={len(duplicates)} {duplicate_eur}")
    print(f"splits={len(splits)} excess={split_excess}")
    print(f"overcharge={overcharge} vat_gap={vat_gap} total={total}")
    print(REPORT_PATH)


if __name__ == "__main__":
    build_db()
    render()
