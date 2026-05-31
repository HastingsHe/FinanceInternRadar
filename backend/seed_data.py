"""
Seed the database with real finance companies across US, UK, CN, EU, HK, AU.
Now seeds job_positions (not intern_programs) with job_type support.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

COMPANIES = [
    # ==================== US ====================
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
    ("BlackRock", "US", "Asset Management",
     "World's largest asset manager with ~$10T AUM.",
     "https://www.blackrock.com", "https://careers.blackrock.com/students", 1),
    ("PIMCO", "US", "Asset Management",
     "Global fixed income investment management firm.",
     "https://www.pimco.com", "https://www.pimco.com/us/en/careers/students/", 0),
    ("Bridgewater Associates", "US", "Hedge Fund",
     "World's largest hedge fund, known for radical transparency culture.",
     "https://www.bridgewater.com", "https://www.bridgewater.com/careers", 1),
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

    # ==================== UK ====================
    ("HSBC", "UK", "Bulge Bracket",
     "One of the world's largest banking and financial services organizations.",
     "https://www.hsbc.com", "https://www.hsbc.com/careers/students-and-graduates", 1),
    ("Barclays", "UK", "Bulge Bracket",
     "British universal bank with strong investment banking division.",
     "https://www.barclays.com", "https://search.jobs.barclays/students-graduates", 1),
    ("Rothschild & Co", "UK", "Boutique",
     "One of the world's largest independent financial advisory groups.",
     "https://www.rothschildandco.com", "https://www.rothschildandco.com/en/careers/students-graduates/", 1),
    ("Schroders", "UK", "Asset Management",
     "Global asset management company with 200+ years of history.",
     "https://www.schroders.com", "https://www.schroders.com/en/careers/early-careers/", 1),
    ("Baillie Gifford", "UK", "Asset Management",
     "Independent investment management firm based in Edinburgh.",
     "https://www.bailliegifford.com", "https://www.bailliegifford.com/en/uk/careers/graduates-and-interns/", 1),
    ("Man Group", "UK", "Hedge Fund",
     "World's largest publicly listed hedge fund company.",
     "https://www.man.com", "https://www.man.com/careers/students", 1),
    ("XTX Markets", "UK", "Prop Trading",
     "Leading quantitative-driven electronic market maker.",
     "https://www.xtxmarkets.com", "https://www.xtxmarkets.com/careers/", 1),
    ("G-Research", "UK", "Quant",
     "Quantitative research and technology firm in London.",
     "https://www.gresearch.com", "https://www.gresearch.com/careers/", 1),

    # ==================== CN (Mainland China) ====================
    ("CITIC Securities (中信证券)", "CN", "Bulge Bracket",
     "China's largest full-service investment bank by assets and revenue.",
     "https://www.cs.ecitic.com", "https://www.cs.ecitic.com/careers/", 1),
    ("CICC (中金公司)", "CN", "Bulge Bracket",
     "China's premier investment bank, first joint-venture IB in China.",
     "https://www.cicc.com", "https://www.cicc.com/careers/", 1),
    ("Huatai Securities (华泰证券)", "CN", "Bulge Bracket",
     "Leading Chinese securities firm with strong tech-driven trading.",
     "https://www.htsc.com.cn", "https://www.htsc.com.cn/careers/", 1),
    ("China Securities (中信建投)", "CN", "Bulge Bracket",
     "Top-tier Chinese investment bank with full-service capabilities.",
     "https://www.csc.com.cn", "https://www.csc.com.cn/careers/", 0),
    ("Guotai Junan (国泰君安)", "CN", "Bulge Bracket",
     "One of China's largest comprehensive securities companies.",
     "https://www.gtja.com", "https://www.gtja.com/careers/", 0),
    ("China Merchants Securities (招商证券)", "CN", "Bulge Bracket",
     "Major Chinese securities firm with strong institutional business.",
     "https://www.cmschina.com", "https://www.cmschina.com/careers/", 0),
    ("Haitong Securities (海通证券)", "CN", "Bulge Bracket",
     "Large Chinese securities firm with international expansion.",
     "https://www.htsec.com", "https://www.htsec.com/careers/", 0),
    ("GF Securities (广发证券)", "CN", "Bulge Bracket",
     "Leading Chinese securities company headquartered in Guangzhou.",
     "https://www.gf.com.cn", "https://www.gf.com.cn/careers/", 0),
    ("Orient Securities (东方证券)", "CN", "Bulge Bracket",
     "Shanghai-based full-service securities firm with strong AM business.",
     "https://www.dfzq.com.cn", "https://www.dfzq.com.cn/careers/", 0),
    ("Industrial Securities (兴业证券)", "CN", "Bulge Bracket",
     "Fujian-based securities firm with growing national presence.",
     "https://www.xyzq.com.cn", "https://www.xyzq.com.cn/careers/", 0),

    # ==================== HK ====================
    ("HSBC Hong Kong (汇丰银行)", "HK", "Bulge Bracket",
     "HSBC's Asia-Pacific hub, dominant in Hong Kong banking.",
     "https://www.hsbc.com.hk", "https://www.hsbc.com.hk/careers/students/", 1),
    ("Standard Chartered Hong Kong (渣打银行)", "HK", "Bulge Bracket",
     "Major international bank with strong Asia footprint.",
     "https://www.sc.com/hk", "https://www.sc.com/hk/careers/students/", 1),
    ("BOCI (中银国际)", "HK", "Bulge Bracket",
     "Bank of China's international investment banking arm in Hong Kong.",
     "https://www.bocigroup.com", "https://www.bocigroup.com/careers/", 1),
    ("Hang Seng Bank (恒生银行)", "HK", "Bulge Bracket",
     "Hong Kong's leading domestic bank, member of HSBC Group.",
     "https://www.hangseng.com", "https://www.hangseng.com/careers/students/", 0),
    ("Bank of East Asia (东亚银行)", "HK", "Bulge Bracket",
     "Hong Kong's largest independent local bank.",
     "https://www.hkbea.com", "https://www.hkbea.com/careers/students/", 0),
    ("HKEX (港交所)", "HK", "Bulge Bracket",
     "Hong Kong Exchanges and Clearing, operator of HK stock exchange.",
     "https://www.hkex.com.hk", "https://www.hkex.com.hk/careers/students/", 1),

    # ==================== EU ====================
    ("Deutsche Bank", "EU", "Bulge Bracket",
     "Germany's largest bank with global investment banking operations.",
     "https://www.db.com", "https://www.db.com/careers/students/", 1),
    ("BNP Paribas", "EU", "Bulge Bracket",
     "France's largest bank, leading European financial services group.",
     "https://www.bnpparibas.com", "https://www.bnpparibas.com/careers/students/", 1),
    ("Societe Generale", "EU", "Bulge Bracket",
     "French multinational investment bank and financial services.",
     "https://www.societegenerale.com", "https://www.societegenerale.com/careers/students/", 1),
    ("UBS", "EU", "Bulge Bracket",
     "Switzerland's largest bank, global wealth management leader.",
     "https://www.ubs.com", "https://www.ubs.com/careers/students/", 1),
    ("Credit Suisse", "EU", "Bulge Bracket",
     "Swiss global investment bank (now part of UBS Group).",
     "https://www.credit-suisse.com", "https://www.credit-suisse.com/careers/students/", 0),
    ("Barclays Europe", "EU", "Bulge Bracket",
     "Barclays' European operations across investment and corporate banking.",
     "https://www.barclays.com", "https://search.jobs.barclays/students-graduates", 0),
    ("HSBC Europe", "EU", "Bulge Bracket",
     "HSBC's continental European banking and markets operations.",
     "https://www.hsbc.com", "https://www.hsbc.com/careers/students-and-graduates", 0),
    ("ING Group", "EU", "Bulge Bracket",
     "Dutch multinational banking and financial services corporation.",
     "https://www.ing.com", "https://www.ing.com/careers/students/", 1),

    # ==================== AU ====================
    ("Macquarie Group", "AU", "Bulge Bracket",
     "Australia's largest investment bank, global infrastructure asset manager.",
     "https://www.macquarie.com", "https://www.macquarie.com/careers/students/", 1),
    ("Commonwealth Bank (CBA)", "AU", "Bulge Bracket",
     "Australia's largest bank by market capitalisation.",
     "https://www.commbank.com.au", "https://www.commbank.com.au/careers/students/", 1),
    ("ANZ", "AU", "Bulge Bracket",
     "Major Australian bank with strong Asia-Pacific presence.",
     "https://www.anz.com.au", "https://www.anz.com.au/careers/students/", 1),
    ("Westpac", "AU", "Bulge Bracket",
     "Australia's oldest bank and one of the Big Four.",
     "https://www.westpac.com.au", "https://www.westpac.com.au/careers/students/", 0),
    ("National Australia Bank (NAB)", "AU", "Bulge Bracket",
     "One of Australia's Big Four banks, strong business banking.",
     "https://www.nab.com.au", "https://www.nab.com.au/careers/students/", 0),
]

# Historical opening dates: (company_name, program, season, year, open_date, close_date)
HISTORICAL = [
    # ── US ──
    ("Goldman Sachs", "Summer Analyst", "Summer", 2023, "2023-07-01", "2023-10-15"),
    ("Goldman Sachs", "Summer Analyst", "Summer", 2024, "2024-07-01", "2024-10-13"),
    ("Goldman Sachs", "Summer Analyst", "Summer", 2025, "2025-07-01", "2025-10-15"),
    ("JPMorgan Chase", "Investment Banking Summer Analyst", "Summer", 2023, "2023-06-01", "2023-09-30"),
    ("JPMorgan Chase", "Investment Banking Summer Analyst", "Summer", 2024, "2024-06-01", "2024-09-30"),
    ("JPMorgan Chase", "Investment Banking Summer Analyst", "Summer", 2025, "2025-06-01", "2025-10-05"),
    ("JPMorgan Chase", "Quant Summer Associate", "Summer", 2024, "2024-07-15", "2024-11-01"),
    ("JPMorgan Chase", "Quant Summer Associate", "Summer", 2025, "2025-07-15", "2025-11-05"),
    ("Morgan Stanley", "Summer Analyst", "Summer", 2023, "2023-06-15", "2023-09-15"),
    ("Morgan Stanley", "Summer Analyst", "Summer", 2024, "2024-06-15", "2024-09-20"),
    ("Morgan Stanley", "Summer Analyst", "Summer", 2025, "2025-07-01", "2025-10-01"),
    ("Jane Street", "Quantitative Trading Intern", "Summer", 2023, "2023-08-01", "2023-12-31"),
    ("Jane Street", "Quantitative Trading Intern", "Summer", 2024, "2024-08-01", "2024-12-31"),
    ("Jane Street", "Quantitative Trading Intern", "Summer", 2025, "2025-08-01", "2025-12-31"),
    ("Jane Street", "Software Engineering Intern", "Summer", 2024, "2024-08-01", "2024-12-31"),
    ("Jane Street", "Software Engineering Intern", "Summer", 2025, "2025-08-01", "2025-12-31"),
    ("BlackRock", "Summer Analyst", "Summer", 2023, "2023-08-15", "2023-12-01"),
    ("BlackRock", "Summer Analyst", "Summer", 2024, "2024-08-15", "2024-12-01"),
    ("BlackRock", "Summer Analyst", "Summer", 2025, "2025-08-15", "2025-12-05"),
    ("Evercore", "Summer Analyst", "Summer", 2023, "2023-04-15", "2023-08-01"),
    ("Evercore", "Summer Analyst", "Summer", 2024, "2024-04-15", "2024-08-01"),
    ("Evercore", "Summer Analyst", "Summer", 2025, "2025-04-15", "2025-08-01"),
    ("Citadel / Citadel Securities", "Quantitative Research Intern", "Summer", 2023, "2023-07-01", "2023-12-31"),
    ("Citadel / Citadel Securities", "Quantitative Research Intern", "Summer", 2024, "2024-07-01", "2024-12-31"),
    ("Citadel / Citadel Securities", "Quantitative Research Intern", "Summer", 2025, "2025-07-15", "2025-12-31"),
    ("Barclays", "Investment Banking Summer Analyst", "Summer", 2023, "2023-08-01", "2023-11-30"),
    ("Barclays", "Investment Banking Summer Analyst", "Summer", 2024, "2024-08-01", "2024-11-30"),
    ("Barclays", "Investment Banking Summer Analyst", "Summer", 2025, "2025-08-01", "2025-12-01"),
    ("HSBC", "Global Banking Summer Intern", "Summer", 2023, "2023-08-15", "2023-11-15"),
    ("HSBC", "Global Banking Summer Intern", "Summer", 2024, "2024-08-15", "2024-11-20"),
    ("HSBC", "Global Banking Summer Intern", "Summer", 2025, "2025-09-01", "2025-11-30"),
    ("Hudson River Trading", "Algorithm Development Intern", "Summer", 2024, "2024-07-01", "2024-12-31"),
    ("Hudson River Trading", "Algorithm Development Intern", "Summer", 2025, "2025-07-01", "2025-12-31"),
    ("SIG (Susquehanna)", "Quantitative Trading Intern", "Summer", 2024, "2024-08-01", "2024-12-01"),
    ("SIG (Susquehanna)", "Quantitative Trading Intern", "Summer", 2025, "2025-08-01", "2025-12-01"),
    ("Optiver", "Quantitative Trading Intern", "Summer", 2024, "2024-06-01", "2024-10-01"),
    ("Optiver", "Quantitative Trading Intern", "Summer", 2025, "2025-06-01", "2025-10-01"),
    ("Rothschild & Co", "Summer Analyst", "Summer", 2024, "2024-09-01", "2024-12-31"),
    ("Rothschild & Co", "Summer Analyst", "Summer", 2025, "2025-09-01", "2025-12-31"),
    ("D.E. Shaw & Co.", "Quantitative Analyst Intern", "Summer", 2024, "2024-07-01", "2024-12-31"),
    ("D.E. Shaw & Co.", "Quantitative Analyst Intern", "Summer", 2025, "2025-07-01", "2025-12-31"),
    ("G-Research", "Quantitative Research Intern", "Summer", 2024, "2024-09-01", "2024-12-31"),
    ("G-Research", "Quantitative Research Intern", "Summer", 2025, "2025-09-01", "2025-12-31"),
    ("XTX Markets", "Quantitative Research Intern", "Summer", 2024, "2024-09-15", "2024-12-31"),
    ("XTX Markets", "Quantitative Research Intern", "Summer", 2025, "2025-09-15", "2025-12-31"),
    ("Bridgewater Associates", "Investment Associate Intern", "Summer", 2024, "2024-07-01", "2024-10-31"),
    ("Bridgewater Associates", "Investment Associate Intern", "Summer", 2025, "2025-07-01", "2025-10-31"),
    ("DRW", "Quantitative Trading Intern", "Summer", 2024, "2024-08-01", "2024-12-01"),
    ("DRW", "Quantitative Trading Intern", "Summer", 2025, "2025-08-01", "2025-12-01"),
    ("Schroders", "Investment Intern", "Summer", 2024, "2024-09-01", "2024-12-15"),
    ("Schroders", "Investment Intern", "Summer", 2025, "2025-09-01", "2025-12-15"),

    # ── CN ──
    ("CITIC Securities (中信证券)", "Summer Intern", "Summer", 2024, "2024-04-01", "2024-06-30"),
    ("CITIC Securities (中信证券)", "Summer Intern", "Summer", 2025, "2025-04-01", "2025-06-30"),
    ("CICC (中金公司)", "Summer Analyst", "Summer", 2024, "2024-03-15", "2024-06-15"),
    ("CICC (中金公司)", "Summer Analyst", "Summer", 2025, "2025-03-15", "2025-06-15"),
    ("CICC (中金公司)", "Graduate Program", "Fall", 2024, "2024-09-01", "2024-11-30"),
    ("Huatai Securities (华泰证券)", "Summer Intern", "Summer", 2024, "2024-04-15", "2024-07-15"),
    ("Huatai Securities (华泰证券)", "Summer Intern", "Summer", 2025, "2025-04-15", "2025-07-15"),
    ("China Securities (中信建投)", "Summer Intern", "Summer", 2024, "2024-04-01", "2024-07-01"),
    ("China Securities (中信建投)", "Summer Intern", "Summer", 2025, "2025-04-01", "2025-07-01"),
    ("Guotai Junan (国泰君安)", "Summer Intern", "Summer", 2024, "2024-05-01", "2024-07-31"),
    ("Guotai Junan (国泰君安)", "Summer Intern", "Summer", 2025, "2025-05-01", "2025-07-31"),
    ("China Merchants Securities (招商证券)", "Summer Intern", "Summer", 2024, "2024-04-15", "2024-07-15"),
    ("China Merchants Securities (招商证券)", "Summer Intern", "Summer", 2025, "2025-04-15", "2025-07-15"),

    # ── HK ──
    ("HSBC Hong Kong (汇丰银行)", "Global Banking Summer Intern", "Summer", 2024, "2024-08-15", "2024-11-30"),
    ("HSBC Hong Kong (汇丰银行)", "Global Banking Summer Intern", "Summer", 2025, "2025-09-01", "2025-11-30"),
    ("Standard Chartered Hong Kong (渣打银行)", "Summer Intern", "Summer", 2024, "2024-09-01", "2024-12-15"),
    ("Standard Chartered Hong Kong (渣打银行)", "Summer Intern", "Summer", 2025, "2025-09-01", "2025-12-15"),
    ("BOCI (中银国际)", "Summer Analyst", "Summer", 2024, "2024-04-01", "2024-06-30"),
    ("BOCI (中银国际)", "Summer Analyst", "Summer", 2025, "2025-04-01", "2025-06-30"),
    ("HKEX (港交所)", "Summer Intern", "Summer", 2024, "2024-03-01", "2024-05-31"),
    ("HKEX (港交所)", "Summer Intern", "Summer", 2025, "2025-03-01", "2025-05-31"),

    # ── EU ──
    ("Deutsche Bank", "Summer Analyst", "Summer", 2024, "2024-07-01", "2024-10-31"),
    ("Deutsche Bank", "Summer Analyst", "Summer", 2025, "2025-07-01", "2025-10-31"),
    ("BNP Paribas", "Summer Intern", "Summer", 2024, "2024-09-01", "2024-12-31"),
    ("BNP Paribas", "Summer Intern", "Summer", 2025, "2025-09-01", "2025-12-31"),
    ("Societe Generale", "Summer Analyst", "Summer", 2024, "2024-09-15", "2024-12-31"),
    ("Societe Generale", "Summer Analyst", "Summer", 2025, "2025-09-15", "2025-12-31"),
    ("UBS", "Summer Analyst", "Summer", 2024, "2024-08-01", "2024-11-30"),
    ("UBS", "Summer Analyst", "Summer", 2025, "2025-08-01", "2025-11-30"),
    ("ING Group", "Summer Intern", "Summer", 2024, "2024-09-01", "2024-12-15"),
    ("ING Group", "Summer Intern", "Summer", 2025, "2025-09-01", "2025-12-15"),

    # ── AU ──
    ("Macquarie Group", "Summer Intern", "Summer", 2024, "2024-02-01", "2024-04-30"),
    ("Macquarie Group", "Summer Intern", "Summer", 2025, "2025-02-01", "2025-04-30"),
    ("Commonwealth Bank (CBA)", "Summer Intern", "Summer", 2024, "2024-03-01", "2024-05-31"),
    ("Commonwealth Bank (CBA)", "Summer Intern", "Summer", 2025, "2025-03-01", "2025-05-31"),
    ("ANZ", "Summer Intern", "Summer", 2024, "2024-03-15", "2024-06-15"),
    ("ANZ", "Summer Intern", "Summer", 2025, "2025-03-15", "2025-06-15"),
]


# Job positions to seed (covering various job_types for new regions)
# (company_name, program_name, role_type, job_type, season, year, predicted_open_date, confidence)
JOB_POSITIONS_SEED = [
    # ── CN Intern ──
    ("CITIC Securities (中信证券)", "Summer Intern - IB", "Investment Banking", "intern", "Summer", 2026, "2026-04-01", 0.85),
    ("CITIC Securities (中信证券)", "Graduate Program - Research", "Research", "graduate", "Fall", 2026, "2026-09-01", 0.70),
    ("CICC (中金公司)", "Summer Analyst - IB", "Investment Banking", "intern", "Summer", 2026, "2026-03-15", 0.88),
    ("CICC (中金公司)", "Management Trainee", "Generalist", "management_trainee", "Fall", 2026, "2026-09-15", 0.72),
    ("Huatai Securities (华泰证券)", "Quant Trading Intern", "Quant", "intern", "Summer", 2026, "2026-04-15", 0.78),
    ("Huatai Securities (华泰证券)", "Full-Time Analyst", "Investment Banking", "full-time", "Fall", 2026, "2026-09-01", 0.65),
    ("China Securities (中信建投)", "Summer Intern - IB", "Investment Banking", "intern", "Summer", 2026, "2026-04-01", 0.82),
    ("China Securities (中信建投)", "Graduate Program - S&T", "Sales & Trading", "graduate", "Fall", 2026, "2026-09-15", 0.68),
    ("Guotai Junan (国泰君安)", "Summer Intern", "Generalist", "intern", "Summer", 2026, "2026-05-01", 0.75),
    ("Guotai Junan (国泰君安)", "Full-Time Associate", "Research", "full-time", "Fall", 2026, "2026-10-01", 0.60),
    ("China Merchants Securities (招商证券)", "Summer Intern", "Investment Banking", "intern", "Summer", 2026, "2026-04-15", 0.77),
    ("China Merchants Securities (招商证券)", "Graduate Program", "Asset Management", "graduate", "Fall", 2026, "2026-10-15", 0.63),
    ("Haitong Securities (海通证券)", "Summer Analyst", "Investment Banking", "intern", "Summer", 2026, "2026-05-01", 0.73),
    ("Haitong Securities (海通证券)", "Management Trainee", "Generalist", "management_trainee", "Fall", 2026, "2026-09-01", 0.62),
    ("GF Securities (广发证券)", "Summer Intern", "Research", "intern", "Summer", 2026, "2026-04-15", 0.74),
    ("GF Securities (广发证券)", "Full-Time Analyst", "Sales & Trading", "full-time", "Fall", 2026, "2026-10-01", 0.61),
    ("Orient Securities (东方证券)", "Summer Intern", "Asset Management", "intern", "Summer", 2026, "2026-05-15", 0.70),
    ("Orient Securities (东方证券)", "Graduate Program", "Investment Banking", "graduate", "Fall", 2026, "2026-10-01", 0.60),
    ("Industrial Securities (兴业证券)", "Summer Intern", "Generalist", "intern", "Summer", 2026, "2026-05-01", 0.71),
    ("Industrial Securities (兴业证券)", "Full-Time Associate", "Research", "full-time", "Fall", 2026, "2026-10-15", 0.58),

    # ── HK Intern / Graduate ──
    ("HSBC Hong Kong (汇丰银行)", "Global Banking Summer Intern", "Investment Banking", "intern", "Summer", 2026, "2026-09-01", 0.82),
    ("HSBC Hong Kong (汇丰银行)", "Graduate Programme - Markets", "Sales & Trading", "graduate", "Full-Year", 2026, "2026-09-15", 0.70),
    ("Standard Chartered Hong Kong (渣打银行)", "Summer Intern - IB", "Investment Banking", "intern", "Summer", 2026, "2026-09-01", 0.78),
    ("Standard Chartered Hong Kong (渣打银行)", "International Graduate Programme", "Generalist", "graduate", "Full-Year", 2026, "2026-09-15", 0.65),
    ("BOCI (中银国际)", "Summer Analyst", "Investment Banking", "intern", "Summer", 2026, "2026-04-01", 0.80),
    ("BOCI (中银国际)", "Graduate Trainee", "Generalist", "management_trainee", "Fall", 2026, "2026-10-01", 0.64),
    ("Hang Seng Bank (恒生银行)", "Summer Intern", "Generalist", "intern", "Summer", 2026, "2026-03-01", 0.74),
    ("Hang Seng Bank (恒生银行)", "Management Trainee Programme", "Generalist", "management_trainee", "Fall", 2026, "2026-10-01", 0.58),
    ("Bank of East Asia (东亚银行)", "Summer Intern", "Generalist", "intern", "Summer", 2026, "2026-04-01", 0.70),
    ("Bank of East Asia (东亚银行)", "Graduate Programme", "Generalist", "graduate", "Fall", 2026, "2026-09-15", 0.56),
    ("HKEX (港交所)", "Summer Intern - Markets", "Sales & Trading", "intern", "Summer", 2026, "2026-03-01", 0.76),
    ("HKEX (港交所)", "Graduate Programme", "Generalist", "graduate", "Fall", 2026, "2026-10-01", 0.60),

    # ── EU Intern / Full-Time ──
    ("Deutsche Bank", "Summer Analyst - IBD", "Investment Banking", "intern", "Summer", 2026, "2026-07-01", 0.84),
    ("Deutsche Bank", "Graduate Programme - FIC", "Sales & Trading", "graduate", "Fall", 2026, "2026-10-01", 0.70),
    ("BNP Paribas", "Summer Intern - Global Markets", "Sales & Trading", "intern", "Summer", 2026, "2026-09-01", 0.80),
    ("BNP Paribas", "Graduate Programme - CIB", "Investment Banking", "graduate", "Fall", 2026, "2026-10-15", 0.68),
    ("Societe Generale", "Summer Analyst", "Investment Banking", "intern", "Summer", 2026, "2026-09-15", 0.76),
    ("Societe Generale", "Full-Time Analyst - Risk", "Risk", "full-time", "Fall", 2026, "2026-10-01", 0.62),
    ("UBS", "Summer Analyst - IBD", "Investment Banking", "intern", "Summer", 2026, "2026-08-01", 0.82),
    ("UBS", "Graduate Talent Program", "Generalist", "graduate", "Fall", 2026, "2026-10-01", 0.70),
    ("Credit Suisse", "Summer Analyst", "Investment Banking", "intern", "Summer", 2026, "2026-08-15", 0.72),
    ("Credit Suisse", "Full-Time Analyst - Quant", "Quant", "full-time", "Fall", 2026, "2026-10-15", 0.58),
    ("Barclays Europe", "Summer Analyst - IBD", "Investment Banking", "intern", "Summer", 2026, "2026-08-01", 0.78),
    ("Barclays Europe", "Graduate Programme", "Generalist", "graduate", "Fall", 2026, "2026-10-01", 0.64),
    ("HSBC Europe", "Summer Intern - Global Banking", "Investment Banking", "intern", "Summer", 2026, "2026-09-01", 0.76),
    ("HSBC Europe", "Graduate Programme - Markets", "Sales & Trading", "graduate", "Fall", 2026, "2026-10-15", 0.62),
    ("ING Group", "Summer Intern - Wholesale Banking", "Investment Banking", "intern", "Summer", 2026, "2026-09-01", 0.74),
    ("ING Group", "International Talent Programme", "Generalist", "management_trainee", "Fall", 2026, "2026-10-01", 0.60),

    # ── AU Intern / Graduate ──
    ("Macquarie Group", "Summer Intern - IBD", "Investment Banking", "intern", "Summer", 2026, "2026-02-01", 0.85),
    ("Macquarie Group", "Graduate Programme - Macquarie Capital", "Investment Banking", "graduate", "Full-Year", 2026, "2026-03-01", 0.72),
    ("Commonwealth Bank (CBA)", "Summer Intern - IB&M", "Investment Banking", "intern", "Summer", 2026, "2026-03-01", 0.78),
    ("Commonwealth Bank (CBA)", "Graduate Programme", "Generalist", "graduate", "Full-Year", 2026, "2026-03-15", 0.68),
    ("ANZ", "Summer Intern - Institutional", "Investment Banking", "intern", "Summer", 2026, "2026-03-15", 0.76),
    ("ANZ", "Graduate Programme - Markets", "Sales & Trading", "graduate", "Full-Year", 2026, "2026-04-01", 0.64),
    ("Westpac", "Summer Intern", "Generalist", "intern", "Summer", 2026, "2026-03-01", 0.72),
    ("Westpac", "Graduate Programme", "Generalist", "graduate", "Full-Year", 2026, "2026-04-01", 0.60),
    ("National Australia Bank (NAB)", "Summer Intern", "Generalist", "intern", "Summer", 2026, "2026-03-01", 0.70),
    ("National Australia Bank (NAB)", "Graduate Programme", "Generalist", "graduate", "Full-Year", 2026, "2026-04-01", 0.58),
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()

    # Clear existing data
    for table in ["subscriptions", "subscribers", "daily_recommendations", "scrape_logs",
                   "scraped_positions", "scraping_sources", "alerts",
                   "job_positions", "historical_openings", "companies"]:
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

    # Insert job_positions seed (for new regions with explicit job_type)
    for jp in JOB_POSITIONS_SEED:
        cid = company_ids.get(jp[0])
        if cid:
            cursor.execute(
                "INSERT INTO job_positions (company_id, program_name, role_type, job_type, season, year, predicted_open_date, confidence, status) "
                "VALUES (?,?,?,?,?,?,?,?,'upcoming')",
                (cid, jp[1], jp[2], jp[3], jp[4], jp[5], jp[6], jp[7])
            )

    # Insert scraping_sources for each company with a careers_url
    region_map = {c[0]: c[1] for c in COMPANIES}
    for name, cid in company_ids.items():
        region = region_map.get(name, "US")
        cursor.execute(
            "INSERT INTO scraping_sources (company_id, source_url, source_type, region, is_active) VALUES (?,?,?,?,1)",
            (cid, "", "careers_page", region)
        )

    conn.commit()
    conn.close()
    nc = len(COMPANIES)
    nh = len(HISTORICAL)
    nj = len(JOB_POSITIONS_SEED)
    print(f"Seeded {nc} companies, {nh} historical records, {nj} job positions.")


if __name__ == "__main__":
    from database import init_db
    init_db()
    seed()
