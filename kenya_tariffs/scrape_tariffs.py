#!/usr/bin/env python3
"""
Kenya Electricity Tariff Scraper
Source: https://www.stimatracker.com/historic#tariffs
Uses lxml for HTML parsing.
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests
from lxml import html


URL = "https://www.stimatracker.com/historic"
OUTPUT_DIR = Path(__file__).parent


def fetch_page(url: str) -> str:
    """Fetch the HTML page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def parse_typical_costs(tree) -> List[Dict]:
    """
    Extract Table 1: Monthly typical cost per kWh.
    Returns 209 rows from 2008-12 to 2026-04.
    """
    all_tables = tree.xpath("//section[@class='container']//table")
    table = all_tables[0]
    rows = table.xpath(".//tbody/tr")

    headers = [
        "Period",
        "Average_electricity_cost_KES_kWh",
        "DL", "DL2", "DC", "SC1", "SC3",
        "CI1", "CI2", "CI3", "CI4", "CI5", "CI6", "EM", "IT",
        "DL_Peak", "DL_Off_peak",
        "DL2_Peak", "DL2_Off_peak",
        "DC_Peak", "DC_Off_peak",
        "SC1_Peak", "SC1_Off_peak",
        "SC3_Peak", "SC3_Off_peak",
        "CI1_Peak", "CI1_Off_peak",
        "CI4_Peak", "CI4_Off_peak",
        "CI5_Peak", "CI5_Off_peak",
        "EM_Peak", "EM_Off_peak",
        "IT_Peak", "IT_Off_peak",
        "Notes",
    ]

    data = []
    for row in rows:
        cells = row.xpath("./td/text()")
        if not cells:
            continue
        cells = [c.strip() for c in cells]
        # Pad to match header count
        while len(cells) < len(headers):
            cells.append("")
        data.append(dict(zip(headers, cells[: len(headers)])))

    return data


def parse_surcharges(tree) -> List[Dict]:
    """
    Extract Table 2: Monthly surcharges (FCC, FERFA, IA, WARMA).
    """
    all_tables = tree.xpath("//section[@class='container']//table")
    table = all_tables[1]  # Second table is surcharges
    rows = table.xpath(".//tbody/tr")

    headers = [
        "Period",
        "Fuel_Cost_Charge_KES",
        "Forex_Fluctuation_Adjustment_KES",
        "Inflation_Adjustment_KES",
        "WARMA_Levy_KES",
    ]

    data = []
    for row in rows:
        tds = row.xpath("./td")
        if not tds:
            continue
        cells = [td.text_content().strip() for td in tds]
        if cells:
            data.append(dict(zip(headers, cells)))

    return data


def parse_historical_tariffs(tree) -> List[Dict]:
    """
    Extract Tables 3-12: Historical tariff structures by era.
    Each table is preceded by an <h3> or <h4> with the period label.
    """
    # Get all tariff tables (skip first 2)
    all_tables = tree.xpath("//section[@class='container']//table")
    tariff_tables = all_tables[2:]

    data = []

    for table in tariff_tables:
        # Find the period label from preceding h3 or h4
        period_label = ""
        for tag in ("h3", "h4"):
            prev = table.xpath(f"./preceding::{tag}[1]")
            if prev:
                period_label = prev[0].text_content().strip()
                break

        rows = table.xpath(".//tr")
        for row in rows:
            cells = row.xpath("./td")
            if not cells:
                continue

            texts = [c.text_content().strip().replace("\xa0", " ") for c in cells if c.text_content().strip()]
            if not texts:
                continue

            # Skip header rows
            first = texts[0]
            if any(h in first for h in ("Tariff", "Charges", "Fixed charge", "Energy charge", "Demand charge")):
                continue

            # Parse tariff code and description
            tariff_code = ""
            description = ""
            match = re.match(
                r"^([A-Z]+\d*(?:\s*\([^)]+\))?)\s*(.*)", first, re.DOTALL
            )
            if match:
                tariff_code = match.group(1).strip()
                description = match.group(2).strip()
            else:
                tariff_code = first

            # Extract charge values
            fixed_charge = ""
            energy_charge = ""
            demand_charge = ""

            for text in texts[1:]:
                text_clean = text.strip()
                if text_clean.lower() == "n/a":
                    demand_charge = "n/a"
                elif re.match(r"^\d+\.?\d*$", text_clean):
                    if not fixed_charge:
                        fixed_charge = text_clean
                    elif not energy_charge:
                        energy_charge = text_clean
                    elif not demand_charge:
                        demand_charge = text_clean
                elif any(k in text_clean for k in (":", "kWh", "First", "TOU")):
                    energy_charge = text_clean

            data.append({
                "Period": period_label,
                "Tariff_Code": tariff_code,
                "Description": description,
                "Fixed_Charge_KES": fixed_charge,
                "Energy_Charge_KES_kWh": energy_charge,
                "Demand_Charge_KES_kVA": demand_charge,
            })

    return data


def write_csv(path: Path, data: List[Dict]) -> None:
    """Write a list of dicts to CSV."""
    if not data:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  CSV -> {path.name}")


def write_json(path: Path, payload: dict) -> None:
    """Write JSON output."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"  JSON -> {path.name}")


def write_xlsx(path: Path, sheets: Dict[str, List[Dict]]) -> None:
    """Write multi-sheet Excel if openpyxl is available."""
    try:
        from openpyxl import Workbook
    except ImportError:
        print("  Skipping Excel (openpyxl not installed). Run: pip install openpyxl")
        return

    wb = Workbook()
    first = True
    for sheet_name, data in sheets.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(title=sheet_name)

        if data:
            headers = list(data[0].keys())
            ws.append(headers)
            for row in data:
                ws.append([row.get(h, "") for h in headers])

    wb.save(path)
    print(f"  Excel -> {path.name}")


def main() -> None:
    print("=" * 60)
    print("Kenya Electricity Tariff Scraper")
    print("=" * 60)

    # 1. Fetch
    print("\n[1/3] Fetching page...")
    html_text = fetch_page(URL)
    tree = html.fromstring(html_text)
    print(f"      Parsed HTML with lxml ({len(html_text):,} chars)")

    # 2. Parse
    print("\n[2/3] Extracting tables...")
    typical_costs = parse_typical_costs(tree)
    print(f"      Table 1: {len(typical_costs)} monthly cost rows")

    surcharges = parse_surcharges(tree)
    print(f"      Table 2: {len(surcharges)} monthly surcharge rows")

    historical = parse_historical_tariffs(tree)
    periods = {r["Period"] for r in historical}
    print(f"      Tables 3-12: {len(historical)} tariff entries across {len(periods)} periods")

    # 3. Write outputs
    print("\n[3/3] Writing files...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(OUTPUT_DIR / "01_monthly_typical_costs.csv", typical_costs)
    write_csv(OUTPUT_DIR / "02_monthly_surcharges.csv", surcharges)
    write_csv(OUTPUT_DIR / "03_historical_tariff_structures.csv", historical)

    write_xlsx(
        OUTPUT_DIR / "kenya_electricity_tariffs.xlsx",
        {
            "Monthly Typical Costs": typical_costs,
            "Monthly Surcharges": surcharges,
            "Historical Tariff Structures": historical,
        },
    )

    write_json(
        OUTPUT_DIR / "kenya_electricity_tariffs.json",
        {
            "source": URL,
            "scrape_date": datetime.now().strftime("%Y-%m-%d"),
            "description": "Historical electricity tariff data for Kenya",
            "data": {
                "monthly_typical_costs": typical_costs,
                "monthly_surcharges": surcharges,
                "historical_tariff_structures": historical,
            },
        },
    )

    # Summary
    print("\n" + "=" * 60)
    print("Done.")
    print(f"  Time span  : {typical_costs[-1]['Period']} -> {typical_costs[0]['Period']}")
    print(f"  Output dir : {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
