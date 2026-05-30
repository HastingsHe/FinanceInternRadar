"""
Seed the database with real finance companies and historical data.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

COMPANIES = [
    # --- US Bulge Bracket ---
    ("Goldman Sachs", "US", "Bulge Bracket",
     "Global investment banking, securities and investment management firm.",
     "https://www.goldmansachs.com", "https://www.goldmansachs.com/careers/students/", 1),
    ("JPMorgan Chase", "US", "Bulge Bracket",
     "Largest US bank by assets, leading investment banking franchise.",
     "https://www.jpmorganchase.com", "https://careers.jpmorgan.com/us/en/students", 1),
    ("Morgan Stanley", "US", "Bulge Bracket",
     "Global financial services firm specializing in investment banking and wealth management.",
     "https://www.morganstanley.com", "https://www.morganstanley.com/careers/students-graduates", 1),
    ("Citi", "US", "Bulge Bracket",
     "Global bank with strong presence in 160+ countries.",
     "https://www.citigroup.com", "https://www.citigroup.com/global/careers/students-and-graduates", 0),
    ("Bank of America Merrill Lynch", "US", "Bulge Bracket",
     "One of the world's largest financial institutions.",
     "https://www.bankofamerica.com", "https://campus.bankofamerica.com", 0),

    # --- US Elite Boutique ---
    ("Evercore", "US", "Boutique",
     "Premier independent investment banking advisory firm.",
     "https://www.evercore.com", "https://www.evercore.com/careers/students/", 1),
    ("Lazard", "US", "Boutique",
     "Global financial advisory and asset management firm.",
     "https://www.lazard.com", "https://www.lazard.com/careers/students/", 1),
    ("Moelis & Company", "US", "Boutique",
     "Independent investment bank providing strategic advisory services.",
     "https://www.moelis.com", "https://www.moelis.com/careers/students/", 0),
    ("PJT Partners", "US", "Boutique",
     "Global advisory-focused investment bank.",
     "https://www.pjtpartners.com", "https://www.pjtpartners.com/careers/", 0),
    ("Centerview Partners", "US", "Boutique",
     "Premier independent investment banking advisory firm.",
     "https://www.centerview.com", "https://www.centerview.com/careers/", 1),

    # --- US Quant / Prop Trading ---
    ("Jane Street", "US", "Prop Trading",
     "Quantitative trading firm and liquidity provider.",
     "https://www.janestreet.com", "https://www.janestreet.com/join-jane-street/", 1),
    ("Citadel / Citadel Securities", "US", "Hedge Fund",
     "Leading global multi-strategy hedge fund and market maker.",
     "https://www.citadel.com", "https://www.citadel.com/careers/students/", 1),
    ("Two Sigma", "US", "Hedge Fund",
     "Systematic investment manager using technology and data science.",
     "https://www.twosigma.com", "https://www.twosigma.com/careers/", 0),
    ("D.E. Shaw & Co.", "US", "Hedge Fund",
     "Global investment and technology development firm.",
     "https://www.deshaw.com", "https://www.deshaw.com/careers", 1),
    ("Hudson River Trading", "US", "Prop Trading",
     "Multi-asset quantitative trading firm.",
     "https://www.hudsonrivertrading.com", "https://www.hudsonrivertrading.com/careers/", 1),
    ("DRW", "US", "Prop Trading",
     "Diversified principal trading firm.",
     "https://www.drw.com", "https://drw.com/careers/students/", 1),

    # --- US Asset Management ---
    ("BlackRock", "US", "Asset Management",
     "World's largest asset manager with ~$10T AUM.",
     "https://www.blackrock.com", "https://careers.blackrock.com/students", 1),
    ("PIMCO", "US", "Asset Management",
     "Global fixed income investment management firm.",
     "https://www.pimco.com", "https://www.pimco.com/us/en/careers/students/", 0),
    ("Bridgewater Associates", "US", "Hedge Fund",
     "World's largest hedge fund, known for radical transparency culture.",
     "https://www.bridgewater.com", "https://www.bridgewater.com/careers", 1),

    # --- UK Banks ---
    ("HSBC", "UK", "Bulge Bracket",
     "One of the world's largest banking and financial services organizations.",
     "https://www.hsbc.com", "https://www.hsbc.com/careers/students-and-graduates", 1),
    ("Barclays", "UK", "Bulge Bracket",
     "British universal bank with strong investment banking division.",
     "https://www.barclays.com", "https://search.jobs.barclays/students-graduates", 1),
    ("Rothschild & Co", "UK", "Boutique",
     "One of the world's largest independent financial advisory groups.",
     "https://www.rothschildandco.com", "https://www.rothschildandco.com/en/careers/students-graduates/", 1),

    # --- UK Asset Management / Boutique ---
    ("Schroders", "UK", "Asset Management",
     "Global asset management company with 200+ years of history.",
     "https://www.schroders.com", "https://www.schroders.com/en/careers/early-careers/", 1),
    ("Baillie Gifford", "UK", "Asset Management",
     "Independent investment management firm based in Edinburgh.",
     "https://www.bailliegifford.com", "https://www.bailliegifford.com/en/uk/careers/graduates-and-interns/", 1),
    ("Man Group", "UK", "Hedge Fund",
     "World's largest publicly listed hedge fund company.",
     "https://www.man.com", "https://www.man.com/careers/students", 1),

    # --- UK Prop / FinTech ---
    ("XTX Markets", "UK", "Prop Trading",
     "Leading quantitative-driven electronic market maker.",
     "https://www.xtxmarkets.com", "https://www.xtxmarkets.com/careers/", 1),
    ("G-Research", "UK", "Quant",
     "Quantitative research and technology firm in London.",
     "https://www.gresearch.com", "https://www.gresearch.com/careers/", 1),

    # --- Hidden Gems / US ---
    ("Akuna Capital", "US", "Prop Trading",
     "Options market making and proprietary trading firm.",
     "https://www.akunacapital.com", "https://www.akunacapital.com/careers/students", 1),
    ("Optiver", "US", "Prop Trading",
     "Global electronic market maker with focus on options.",
     "https://www.optiver.com", "https://www.optiver.com/working-at-optiver/campus/", 1),
    ("SIG (Susquehanna)", "US", "Prop Trading",
     "Global quantitative trading firm founded in 1987.",
     "https://www.sig.com", "https://www.sig.com/careers/students/", 1),
    ("Virtu Financial", "US", "Prop Trading",
     "Market maker and liquidity provider across global markets.",
     "https://www.virtu.com", "https://www.virtu.com/careers/students/", 0),
    ("Clear Street", "US", "FinTech",
     "Modern infrastructure for capital markets.",
     "https://www.clearstreet.io", "https://clearstreet.io/careers/students", 1),
]

# Historical opening dates: (company_name, program, season, year, open_date, close_date)
HISTORICAL = [
    # Goldman Sachs
    ("Goldman Sachs", "Summer Analyst", "Summer", 2023, "2023-07-01", "2023-10-15"),
    ("Goldman Sachs", "Summer Analyst", "Summer", 2024, "2024-07-01", "2024-10-13"),
    ("Goldman Sachs", "Summer Analyst", "Summer", 2025, "2025-07-01", "2025-10-15"),
    # JPMorgan
    ("JPMorgan Chase", "Investment Banking Summer Analyst", "Summer", 2023, "2023-06-01", "2023-09-30"),
    ("JPMorgan Chase", "Investment Banking Summer Analyst", "Summer", 2024, "2024-06-01", "2024-09-30"),
    ("JPMorgan Chase", "Investment Banking Summer Analyst", "Summer", 2025, "2025-06-01", "2025-10-05"),
    ("JPMorgan Chase", "Quant Summer Associate", "Summer", 2024, "2024-07-15", "2024-11-01"),
    ("JPMorgan Chase", "Quant Summer Associate", "Summer", 2025, "2025-07-15", "2025-11-05"),
    # Morgan Stanley
    ("Morgan Stanley", "Summer Analyst", "Summer", 2023, "2023-06-15", "2023-09-15"),
    ("Morgan Stanley", "Summer Analyst", "Summer", 2024, "2024-06-15", "2024-09-20"),
    ("Morgan Stanley", "Summer Analyst", "Summer", 2025, "2025-07-01", "2025-10-01"),
    # Jane Street
    ("Jane Street", "Quantitative Trading Intern", "Summer", 2023, "2023-08-01", "2023-12-31"),
    ("Jane Street", "Quantitative Trading Intern", "Summer", 2024, "2024-08-01", "2024-12-31"),
    ("Jane Street", "Quantitative Trading Intern", "Summer", 2025, "2025-08-01", "2025-12-31"),
    ("Jane Street", "Software Engineering Intern", "Summer", 2024, "2024-08-01", "2024-12-31"),
    ("Jane Street", "Software Engineering Intern", "Summer", 2025, "2025-08-01", "2025-12-31"),
    # BlackRock
    ("BlackRock", "Summer Analyst", "Summer", 2023, "2023-08-15", "2023-12-01"),
    ("BlackRock", "Summer Analyst", "Summer", 2024, "2024-08-15", "2024-12-01"),
    ("BlackRock", "Summer Analyst", "Summer", 2025, "2025-08-15", "2025-12-05"),
    # Evercore
    ("Evercore", "Summer Analyst", "Summer", 2023, "2023-04-15", "2023-08-01"),
    ("Evercore", "Summer Analyst", "Summer", 2024, "2024-04-15", "2024-08-01"),
    ("Evercore", "Summer Analyst", "Summer", 2025, "2025-04-15", "2025-08-01"),
    # Citadel
    ("Citadel / Citadel Securities", "Quantitative Research Intern", "Summer", 2023, "2023-07-01", "2023-12-31"),
    ("Citadel / Citadel Securities", "Quantitative Research Intern", "Summer", 2024, "2024-07-01", "2024-12-31"),
    ("Citadel / Citadel Securities", "Quantitative Research Intern", "Summer", 2025, "2025-07-15", "2025-12-31"),
    # Barclays
    ("Barclays", "Investment Banking Summer Analyst", "Summer", 2023, "2023-08-01", "2023-11-30"),
    ("Barclays", "Investment Banking Summer Analyst", "Summer", 2024, "2024-08-01", "2024-11-30"),
    ("Barclays", "Investment Banking Summer Analyst", "Summer", 2025, "2025-08-01", "2025-12-01"),
    # HSBC
    ("HSBC", "Global Banking Summer Intern", "Summer", 2023, "2023-08-15", "2023-11-15"),
    ("HSBC", "Global Banking Summer Intern", "Summer", 2024, "2024-08-15", "2024-11-20"),
    ("HSBC", "Global Banking Summer Intern", "Summer", 2025, "2025-09-01", "2025-11-30"),
    # Hudson River Trading
    ("Hudson River Trading", "Algorithm Development Intern", "Summer", 2024, "2024-07-01", "2024-12-31"),
    ("Hudson River Trading", "Algorithm Development Intern", "Summer", 2025, "2025-07-01", "2025-12-31"),
    # SIG
    ("SIG (Susquehanna)", "Quantitative Trading Intern", "Summer", 2024, "2024-08-01", "2024-12-01"),
    ("SIG (Susquehanna)", "Quantitative Trading Intern", "Summer", 2025, "2025-08-01", "2025-12-01"),
    # Optiver
    ("Optiver", "Quantitative Trading Intern", "Summer", 2024, "2024-06-01", "2024-10-01"),
    ("Optiver", "Quantitative Trading Intern", "Summer", 2025, "2025-06-01", "2025-10-01"),
    # Rothschild & Co
    ("Rothschild & Co", "Summer Analyst", "Summer", 2024, "2024-09-01", "2024-12-31"),
    ("Rothschild & Co", "Summer Analyst", "Summer", 2025, "2025-09-01", "2025-12-31"),
    # D.E. Shaw
    ("D.E. Shaw & Co.", "Quantitative Analyst Intern", "Summer", 2024, "2024-07-01", "2024-12-31"),
    ("D.E. Shaw & Co.", "Quantitative Analyst Intern", "Summer", 2025, "2025-07-01", "2025-12-31"),
    # G-Research
    ("G-Research", "Quantitative Research Intern", "Summer", 2024, "2024-09-01", "2024-12-31"),
    ("G-Research", "Quantitative Research Intern", "Summer", 2025, "2025-09-01", "2025-12-31"),
    # XTX Markets
    ("XTX Markets", "Quantitative Research Intern", "Summer", 2024, "2024-09-15", "2024-12-31"),
    ("XTX Markets", "Quantitative Research Intern", "Summer", 2025, "2025-09-15", "2025-12-31"),
    # Bridgewater
    ("Bridgewater Associates", "Investment Associate Intern", "Summer", 2024, "2024-07-01", "2024-10-31"),
    ("Bridgewater Associates", "Investment Associate Intern", "Summer", 2025, "2025-07-01", "2025-10-31"),
    # DRW
    ("DRW", "Quantitative Trading Intern", "Summer", 2024, "2024-08-01", "2024-12-01"),
    ("DRW", "Quantitative Trading Intern", "Summer", 2025, "2025-08-01", "2025-12-01"),
    # Schroders
    ("Schroders", "Investment Intern", "Summer", 2024, "2024-09-01", "2024-12-15"),
    ("Schroders", "Investment Intern", "Summer", 2025, "2025-09-01", "2025-12-15"),
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()

    # Clear existing data
    for table in ["subscriptions", "subscribers", "daily_recommendations", "scrape_logs",
                   "intern_programs", "historical_openings", "companies"]:
        cursor.execute(f"DELETE FROM {table}")

    # Insert companies
    company_ids = {}
    for c in COMPANIES:
        cursor.execute(
            "INSERT INTO companies (name, region, category, description, website, careers_url, is_featured) VALUES (?,?,?,?,?,?,?)",
            c
        )
        company_ids[c[0]] = cursor.lastrowid

    # Insert historical openings
    for h in HISTORICAL:
        cid = company_ids.get(h[0])
        if cid:
            cursor.execute(
                "INSERT INTO historical_openings (company_id, program_name, season, year, open_date, close_date, source) VALUES (?,?,?,?,?,?,?)",
                (cid, h[1], h[2], h[3], h[4], h[5], "manual_curation")
            )

    conn.commit()
    conn.close()
    print(f"Seeded {len(COMPANIES)} companies and {len(HISTORICAL)} historical records.")


if __name__ == "__main__":
    from database import init_db
    init_db()
    seed()