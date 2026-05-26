# API Catalog for Strata — Market Sizing Data Sources

Every public API useful for TAM analysis, categorized and evaluated for Strata integration.
Source tiers map to Strata's internal taxonomy: `regulator | first_party | aggregator | analyst | community | onchain | prediction_market | community-modeled`.

Last audited: 2026-05-24.

---

## 1. Government / Regulator Data

These are Strata's backbone — the highest-trust, free, citable primitives. Source tier: `regulator`.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **BLS** (Bureau of Labor Statistics) | https://www.bls.gov/developers/ | OES occupation headcounts, wages by SOC code, employment by industry (NAICS), CPI, PPI, productivity | API key (free, register at bls.gov) | 500 req/day unregistered; 500 req/day with key (series limit 50/call v1, 500/call v2) | `bls` (unofficial), `pandas-datareader` | **critical** |
| **FRED** (St. Louis Fed) | https://fred.stlouisfed.org/docs/api/fred/ | 800k+ macro series: GDP, sector spend, PCE, interest rates, CPI, industrial output, credit, trade balance | API key (free) | Generous — no hard cap published; practical limit ~120 req/min | `fredapi` (pip install fredapi) | **critical** |
| **Census Bureau** | https://api.census.gov/data/ | SUSB (business counts by size/NAICS), CBP (county business patterns), ACS demographics, Economic Census, decennial headcounts | API key (free, instant signup) | All datasets free; key required as of 2024 | `census` (pip install census) | **critical** |
| **SEC EDGAR** | https://efts.sec.gov/LATEST/search-index | 10-K/S-1/10-Q financials (XBRL), full-text search, company filings | No auth for EDGAR public API; `sec-api.io` third-party SDK requires paid key | Public EDGAR endpoints free, 10 req/sec guideline; sec-api.io has free tier (100 req/mo) | `sec-api` (pip install sec-api) for parsed data; raw XBRL via `requests` direct | **critical** |
| **World Bank** | https://data.worldbank.org/about/get-started | WDI: GDP, population, sector value-add, trade, FDI, poverty, infrastructure by country | No auth required | Unlimited (reasonable use) | `wbgapi` (pip install wbgapi), `wbdata` | **critical** |
| **OECD** | https://data.oecd.org/api/ | National accounts, labour markets, trade, health spending, R&D spend, education, productivity across 38 member countries | No auth (SDMX-based API) | Free; rate limiting applied for heavy usage | `pandasdmx`, `oecd` (unofficial wrappers) | **high** |
| **Eurostat** | https://ec.europa.eu/eurostat/web/main/data/web-services | EU sector statistics, national accounts, trade, demographic data for all EU member states | No auth (SDMX 2.1 REST) | Free; no hard rate limit published | `eurostat` (pip install eurostat) | **high** |
| **UN Comtrade** | https://comtradeplus.un.org/ | Bilateral trade flows by HS code, country, year — exports/imports for 200+ countries | Free account required (comtradeplus.un.org); premium tiers for bulk | Free: 100 req/hr, 250 req/day; Comtrade+ subscription removes limits | `comtradeapicall` (pip install comtradeapicall) | **high** |
| **USPTO / PatentsView** | https://patentsview.org/apis/purpose | Patent grants and applications by tech class, inventor, assignee (company), year — innovation intensity proxy | No auth for PatentsView REST; USPTO Open Data also no auth | Free, no hard limit stated | `requests` direct (no official SDK) | **medium** |
| **FDIC BankFind** | https://banks.data.fdic.gov/docs/ | Bank counts, deposits, assets, failures by geography and time — financial services market size | No auth | Free, 10 req/sec guideline | `requests` direct | **medium** |
| **CMS Open Data** | https://developer.cms.gov/ | Medicare/Medicaid claims, healthcare provider data, drug spending, procedure costs — healthcare market sizing | No auth (public datasets); FHIR API for bulk | Free for public datasets | `requests` + FHIR client | **medium** |
| **EIA** (Energy Info Admin) | https://www.eia.gov/opendata/ | Energy production, consumption, prices by fuel type, sector, geography; electricity generation capacity | API key (free, instant) | Free; 5,000 req/hr | `eia-python` (unofficial), `requests` direct | **medium** |
| **USDA NASS QuickStats** | https://quickstats.nass.usda.gov/api/ | Agricultural production, acreage, prices, livestock counts by crop, county, year | API key (free, instant) | Free; 50 req/day per key | `requests` direct | **low** |
| **FAA** | https://api.faa.gov/ | Aircraft registrations, airport activity, safety data — aviation market sizing | No auth (limited endpoints) | Free | `requests` direct | **low** |
| **openFDA** | https://open.fda.gov/apis/ | Drug approvals, device clearances, adverse events, recall enforcement by product category | API key (free) or no key for low volume | No key: 240 req/min, 1000/day; with key: 240 req/min, 120k/day | `requests` direct | **low** |

---

## 2. Prediction Markets

Source tier: `prediction_market`. These provide probabilistic forward-looking signals and implied valuations.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **Polymarket** | https://docs.polymarket.com/ | Market prices (= implied probabilities) on regulatory outcomes, adoption forecasts, company events; volume/liquidity as confidence weight; historical price series | No auth for public market data; L1 API key (CLOB) for trading | Public endpoints fully free; no documented rate limit on read endpoints | `py-clob-client` (official), `requests` direct | **high** |
| **Kalshi** | https://trading-api.kalshi.com/docs/ | Regulated US prediction market contracts on economic indicators, interest rates, regulatory decisions, tech launches | API key (requires account, free) | Free account; rate limits not publicly documented | `kalshi-python` (pip install kalshi-python) | **high** |
| **Metaculus** | https://www.metaculus.com/api/ | Community forecasts on tech adoption, policy, scientific milestones; aggregated community probability and resolution data | No auth for public questions | Free; rate limit not published (practical: ~60 req/min) | `requests` direct (no official SDK) | **medium** |
| **Manifold Markets** | https://docs.manifold.markets/api | Play-money prediction markets — qualitative signal of community opinion on business/tech outcomes; market volume as engagement proxy | No auth for GET; API key for write | 500 req/min per IP | `requests` direct | **low** |

---

## 3. Financial / Company Data

Source tier varies: `first_party` for company filings, `aggregator` for data aggregators.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **SEC EDGAR (XBRL)** | https://data.sec.gov/api/xbrl/ | Structured financials from all public company 10-K/10-Q: revenue by segment, headcount, capex — first-party TAM anchors | No auth | Free; 10 req/sec guideline | `requests` direct; `sec-api` for parsed | **critical** |
| **Crunchbase** | https://data.crunchbase.com/docs/using-the-api | Startup funding rounds, valuations, employee counts, industry categories — venture market sizing | API key (paid — Enterprise or Applications license required; Basic plan: company search only) | No free tier for bulk data; Basic plan allows limited company lookups | `requests` direct | **high** |
| **OpenCorporates** | https://api.opencorporates.com/documentation/API-Reference | Global company registry data (200+ jurisdictions): incorporation dates, officer names, addresses — market density by geography | API key (free for open data projects; commercial use requires paid plan) | Free for open data use; rate limits vary by plan | `requests` direct | **medium** |
| **Alpha Vantage** | https://www.alphavantage.co/documentation/ | Fundamental financials (income statement, balance sheet), earnings, sector performance — public company revenue benchmarks | API key (free tier available) | **25 req/day** free; premium from $50/mo | `alpha-vantage` (pip install alpha-vantage) | **medium** |
| **Nasdaq Data Link** (formerly Quandl) | https://docs.data.nasdaq.com/ | 250+ databases including macro, commodity prices, alternative data — financial market sizing anchors | API key (free tier) | Free for many open datasets; premium datasets billed separately | `nasdaq-data-link` (pip install nasdaq-data-link) | **medium** |
| **yfinance** | https://pypi.org/project/yfinance/ | Stock prices, market cap, P/E, revenue, earnings — comparable company analysis and market benchmarks | No auth (unofficial Yahoo Finance scraper) | Free, but unofficial — fragile; Yahoo may break it | `yfinance` (pip install yfinance) | **low** |
| **PitchBook** | No public API documented | VC deal data, private company valuations | Enterprise sales only | No free tier | None | **low** |

---

## 4. Market Research / Analyst

Source tier: `analyst`. These are cite-only in Strata — no value reproduction, just metadata stubs (per Q26).

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **Statista** | No public API | 1M+ statistics across industries; market size, revenue forecasts | No API; web scraping violates ToS | No free API | None | **low** (cite-only) |
| **IBISWorld** | No public API | Industry reports with market size, growth rates, concentration ratios | No API; institutional subscription only | No free tier | None | **low** (cite-only) |
| **Gartner** | No public API | Magic Quadrant, Hype Cycle, market size forecasts | No API; institutional subscription | No free tier | None | **low** (cite-only) |
| **CB Insights** | No public API | Tech market maps, funding data, industry reports | No API; subscription only | No free tier | None | **low** (cite-only) |
| **Similarweb** | https://developer.similarweb.com/ | Web traffic by domain/industry — proxy for market share, category adoption; monthly visits, engagement | API key (paid; V5 API now live) | No meaningful free tier; demo access only | `requests` direct | **medium** |
| **Semrush** | https://developer.semrush.com/api/ | Keyword search volume by country — demand proxy; organic/paid traffic estimates; competitor traffic | API key (paid subscription) | Limited free queries with account | `semrush` (unofficial wrappers available) | **medium** |
| **Google Trends** | No official API | Relative search volume trends by keyword/geography/time — demand timing and relative interest signal | No official API; unofficial via `pytrends` | Free (unofficial scraper) | `pytrends` (pip install pytrends) — unofficial, may break | **medium** |

---

## 5. Web / AI Search

Source tier: `community` or `aggregator`. Used for discovery, validation, and long-tail sourcing.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **Exa** | https://exa.ai/docs | Neural search across 10B+ URLs — find primary sources, analyst excerpts, company disclosures; high recall on obscure sources | API key (free tier available) | **1,000 req/mo free**; $7/1k req after | `exa-py` (pip install exa-py) | **critical** (already integrated) |
| **Tavily** | https://docs.tavily.com/ | AI-optimized web search with extracted text and citations — good for sourcing obscure market data, regulatory filings | API key (free tier) | **1,000 credits/mo free** (1 credit ≈ 1 search) | `tavily-python` (pip install tavily-python) | **high** |
| **Serper** | https://serper.dev/ | Google SERP results (organic, news, images) via API — fastest and cheapest Google proxy; 1-2s response | API key (credit-based) | **2,500 free credits** on signup | `requests` direct | **high** |
| **Brave Search** | https://brave.com/search/api/ | Independent web index (not Google-dependent); returns full-text, news, images; anti-SEO-spam tuned | API key (credit card required even for free) | **$5 in free credits** (~1,000 requests); then $5/1k req | `requests` direct | **medium** |
| **Perplexity (Sonar)** | https://docs.perplexity.ai/ | LLM with real-time web search — inline citations on every answer; good for "has this number changed?" refresh probes | API key (OpenAI-compatible endpoint) | Pay-per-use; Sonar model ~$1/1k tokens; no permanent free tier | `openai` SDK with Perplexity base URL | **high** |

---

## 6. Social / Community Signals

Source tier: `community`. Signal of developer adoption, consumer demand, B2B tool traction.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **Reddit** | https://www.reddit.com/dev/api/ | Subreddit subscriber counts + growth — market interest proxy; post volume as demand signal | OAuth2 (app credentials, free) | Free; 60 req/min with OAuth | `praw` (pip install praw) | **medium** |
| **GitHub** | https://docs.github.com/en/rest | Repo stars, forks, contributors, commit activity — developer tool adoption proxy; language usage stats | API key optional (token gives 5,000 req/hr vs 60 unauthenticated) | Free; 5,000 req/hr authenticated | `PyGithub` (pip install PyGithub) | **medium** |
| **Stack Exchange / Stack Overflow** | https://api.stackexchange.com/docs | Question/answer counts by tag — technology adoption and developer demand signal; trend data | API key optional (300 req/day unauthenticated; with key: 10,000 req/day) | Free; 300 req/day without key, 10,000/day with key | `stackapi` (pip install stackapi) | **medium** |
| **Twitter/X** | https://developer.twitter.com/en/docs/twitter-api | Tweet volume, hashtag trends, account follower growth — brand/market awareness signal | API key + bearer token (pay-per-use since 2023) | Free tier: read-only, heavily restricted (500 posts/mo write, limited search) | `tweepy` (pip install tweepy) | **low** |
| **ProductHunt** | https://api.producthunt.com/v2/docs | Product launch data, upvote counts by category — new product momentum, tool adoption proxy | OAuth2 (free developer account) | Free; rate limits not published | `requests` direct (GraphQL) | **low** |

---

## 7. Blockchain / Onchain

Source tier: `onchain`. For crypto/DeFi market sizing with on-chain as ground truth.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **Dune Analytics** | https://dune.com/docs/api/ | SQL queries over decoded blockchain data (Ethereum, Solana, Arbitrum, etc.): protocol TVL, DEX volume, wallet counts, token transfers — onchain market sizing | API key (free tier) | Free tier: community plan; 2,500 datapoints/mo; rate limit: 1,000 req/hr per IP | `dune-client` (pip install dune-client) | **high** |
| **DeFi Llama** | https://defillama.com/docs/api | DeFi TVL by protocol/chain, stablecoin supply, DEX volume, bridge flows — no-auth free API covering 3,000+ protocols | No auth | Free; no hard rate limit documented | `requests` direct | **high** |
| **CoinGecko** | https://docs.coingecko.com/reference/introduction | Token prices, market caps, trading volumes, fully diluted valuations, exchange data for 13k+ assets | No auth (Demo); API key for Pro | Demo (no key): ~30 calls/min; Pro tier starts at $129/mo | `pycoingecko` (pip install pycoingecko) | **medium** |
| **Etherscan** | https://docs.etherscan.io/ | Ethereum transaction counts, contract interactions, token holder counts, gas fees — Ethereum market activity | API key (free tier) | Free: 5 req/sec, 100k req/day | `requests` direct | **medium** |

---

## 8. Real Estate / Physical Markets

Source tier: `aggregator`. Mostly pay-walled; limited API access.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **Zillow** (Zestimate/ZHVI) | https://www.zillow.com/research/data/ | Home value index (ZHVI), rental index (ZORI), market heat index — residential real estate market sizing | Bulk CSV download only (API deprecated); limited partner API | Bulk CSVs free; REST API partner-only | `requests` (CSV download) | **medium** |
| **Redfin** | https://www.redfin.com/news/data-center/ | Housing market metrics (median price, days on market, inventory) via CSV download — residential market proxy | No API; CSV bulk download | Free CSV downloads | `pandas` (CSV import) | **low** |
| **CoStar** | No public API | Commercial real estate market data, vacancy rates, rental rates | Enterprise sales only; no public API | No free tier | None | **low** (cite-only) |

---

## 9. Industry-Specific Regulators

Source tier: `regulator`. Deep vertical data for specific sectors.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **NAIC** (Insurance) | https://content.naic.org/cipr-topics/state-insurance-data | Premium written by line of business, insurer market share, loss ratios | Bulk download (no REST API); annual data files | Free downloads | `pandas` (CSV/Excel) | **medium** |
| **FDIC BankFind** | https://banks.data.fdic.gov/docs/ | Bank counts, total deposits, assets by geography, charter type, institution size | No auth | Free; ~10 req/sec | `requests` direct | **medium** |
| **CMS** (Healthcare) | https://developer.cms.gov/ | Medicare spending by procedure/provider/geography, Medicaid enrollment, drug rebate data | No auth for public data | Free | FHIR client + `requests` | **medium** |
| **EIA** (Energy) | https://www.eia.gov/opendata/ | Energy consumption by sector, fuel type, geography; capacity additions; retail electricity prices | Free API key | 5,000 req/hr | `eia-python`, `requests` | **medium** |
| **USDA NASS** | https://quickstats.nass.usda.gov/api/ | Crop production, acreage, livestock inventories, farm counts — agricultural market sizing | Free API key | 50 req/day | `requests` direct | **low** |
| **FAA** | https://api.faa.gov/ | Aircraft registrations, airmen certifications, airport operations — aviation sector sizing | No auth (public endpoints) | Free | `requests` direct | **low** |
| **FCC** | https://opendata.fcc.gov/ | Broadband deployment by census block, ISP market share, spectrum auction data — telecom market sizing | No auth | Free | `requests` direct | **low** |
| **openFDA** | https://open.fda.gov/apis/ | Drug/device approvals by year/category, recall counts, adverse event rates | API key (optional; needed for high volume) | 240 req/min with key | `requests` direct | **low** |

---

## 10. Infrastructure / Cloud

Source tier: `first_party` (vendor self-reported pricing). Useful for cloud market sizing and cost benchmarking.

| API | Docs URL | Data for TAM | Auth | Free Tier | Python SDK | Priority |
|---|---|---|---|---|---|---|
| **AWS Pricing** | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json | Real-time AWS service prices (EC2, RDS, S3, etc.) — cloud market cost benchmarks, FinOps TAM inputs | No auth | Fully free; bulk JSON download | `requests` direct | **medium** |
| **Cloudflare Radar** | https://radar.cloudflare.com/api | Internet traffic trends, routing security, DNS query patterns, BGP data, Layer 3/7 attack volumes — internet infrastructure market proxy | No auth (public API available on all plans) | Free; rate limits not published | `requests` direct | **medium** |

---

## Notes on Missing / Pay-Wall-Only APIs

These were researched but have **no usable free API** for market sizing:

- **PitchBook** — enterprise sales, no API docs published
- **IBISWorld** — no API; institutional subscription only
- **Statista** — no API; web scraping violates ToS
- **Gartner** — no API; analyst subscription only
- **CB Insights** — no public API
- **CoStar** — no public API; enterprise only
- **G2 / Capterra** — no public API (G2 shut down their API; Capterra no documented API)
- **AngelList / Wellfound** — API access deprecated/restricted; no current public API

---

## Recommended Integration Order

Priority ordered by: (1) data volume for Strata primitives, (2) free/no-cost, (3) reliability as regulator/first-party source, (4) Python SDK maturity.

| Rank | API | Why first | Strata source tier |
|---|---|---|---|
| 1 | **FRED** | 800k+ macro series; free; excellent SDK (`fredapi`); covers GDP, CPI, sector spend in one call | `regulator` / `aggregator` |
| 2 | **BLS** | Headcount + wage data by occupation/industry — the core denominator in most TAMs | `regulator` |
| 3 | **SEC EDGAR (XBRL)** | First-party financials for every US public company — revenue by segment, directly citable | `first_party` |
| 4 | **Census Bureau** | SUSB/CBP business counts by NAICS — essential for market-density primitives | `regulator` |
| 5 | **World Bank** | Global GDP and sector data — international TAM anchors; no auth, excellent `wbgapi` SDK | `aggregator` |
| 6 | **Exa** | Already integrated; neural search to discover missing source URLs; covers all categories | (discovery layer) |
| 7 | **DeFi Llama** | No-auth, covers 3k+ DeFi protocols; trivial to integrate; onchain market sizing | `onchain` |
| 8 | **Dune Analytics** | SQL over decoded blockchain — precise onchain market sizing with verifiable queries | `onchain` |
| 9 | **Polymarket** | Prediction market prices as forward-looking primitives; free read API; regulation/tech outcome probabilities | `prediction_market` |
| 10 | **Kalshi** | Regulated US prediction market; economic indicator contracts (inflation, rates) | `prediction_market` |
| 11 | **UN Comtrade** | Bilateral trade flows by HS code — essential for sizing international trade markets | `regulator` |
| 12 | **EIA** | Energy production/consumption data; free; 5k req/hr; covers all fuel types + electricity | `regulator` |
| 13 | **Tavily** | AI search with inline citations — second search layer for sourcing + refresh probes | (discovery layer) |
| 14 | **GitHub** | Dev tool adoption proxy; free 5k req/hr; stars/forks as market-penetration signal | `community` |
| 15 | **OECD** | International economic stats for 38 countries — fills gaps in World Bank coverage | `aggregator` |

---

## Appendix: Python SDK Quick Reference

```
# Government / Regulator
pip install fredapi          # FRED
pip install census           # Census Bureau
pip install wbgapi           # World Bank
pip install comtradeapicall  # UN Comtrade
pip install sec-api          # SEC EDGAR (third-party parsed)

# Financial
pip install yfinance         # Yahoo Finance (unofficial)
pip install alpha-vantage    # Alpha Vantage

# Search / AI
pip install exa-py           # Exa neural search
pip install tavily-python    # Tavily AI search

# Prediction Markets
pip install kalshi-python    # Kalshi

# Blockchain
pip install dune-client      # Dune Analytics
pip install pycoingecko      # CoinGecko

# Social signals
pip install praw             # Reddit
pip install PyGithub         # GitHub
pip install stackapi         # Stack Exchange
pip install tweepy           # Twitter/X

# Trends (unofficial)
pip install pytrends         # Google Trends (unofficial)
```

---

*All APIs confirmed to exist and be accessible as of 2026-05-24. Rate limits and pricing subject to change — always verify at the linked docs URL before integrating.*
