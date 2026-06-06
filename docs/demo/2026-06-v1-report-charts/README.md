# v1.0 demo evidence — report charts + multi-page PDF (2026-06)

Verification artifacts from the headed Playwright run for the report-charts /
multi-page-PDF work (PR #113, merged to `main`) and the resolver hit-rate fix
(PR #114). Captured outside the repo originally; preserved here.

| File | What it shows |
|------|---------------|
| `demo-1-signed-in.png` | Signed-in app shell after Clerk login |
| `demo-2-curated-tam.png` | A curated (registry) concept TAM result |
| `demo-3-novel-tam.png` | A novel/resolved TAM (resolver path) |
| `demo-4-report-charts.png` | Report page with the three charts |
| `cap-report-charts.png` | Report charts close-up — answered/gaps donut, coverage radar, source-tier donut (all from real report data) |
| `cap-report-print.png` | Full print-layout capture (unclipped shell, chrome hidden) |
| `cap-PROD-report.png` | Same report rendered against the deployed prod backend (Railway) |
| `report.pdf` | Real `page.pdf()` output — 13 pages (was 1 before the fix) |
