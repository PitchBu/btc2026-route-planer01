BTC2026 Route Planer v4.0

เพิ่ม Timeline Chart ของตารางส่วนตัว แยกตามเวที พร้อมตัวเลือก “ยอมพลาดได้กี่นาที” เพื่อประเมินเวลาชนกัน

# BTC2026 Route Planer v3 — unofficial community tool

**สถานะ:** ตัวเว็บและระบบอัปเดตแบบ *scheduled scraping* พร้อมสำหรับนำไปติดตั้ง แต่การอ่านเว็บไซต์จริง **ยังไม่ผ่านการทดสอบบนเซิร์ฟเวอร์ที่เชื่อมต่ออินเทอร์เน็ต**. ต้องรัน workflow และตรวจสอบผลจริงก่อนประชาสัมพันธ์ว่าอัปเดตอัตโนมัติได้

## Architecture

- `index.html` — responsive three-stage planner, offline snapshot fallback, selection stored in localStorage, share/CSV/ICS/print, changes and conflict warnings.
- `data/baseline.json` — historical screenshot-based schedule, 75 entries (2026-11-03).
- `data/schedule.json` — latest *validated published* snapshot. Initially the same fallback with `source: manual-snapshot`.
- `scripts/sync.mjs` — Playwright opens `https://www.bitcointhailand.co/schedule`, clicks Day 1/2 and extracts session listings from three stage columns. Validates completeness, compares stable IDs, writes changes.
- `.github/workflows/sync-schedule.yml` — GitHub Actions scheduler every 15 minutes (best-effort; scheduled jobs may be delayed). The workflow commits JSON *only if the schedule changed* or first successful verification, to avoid excessive Cloudflare Pages builds.

## Deploy (GitHub + Cloudflare Pages)

1. Create a new **public or private GitHub repository**. Upload the *contents* of this folder to the repository root, including `.github/workflows`.
2. GitHub repository → **Settings → Actions → General → Workflow permissions**: enable **Read and write permissions**. Review GitHub Actions security/billing policies.
3. In GitHub → **Actions → Check official BTC2026 schedule → Run workflow**. Inspect the log. A success must say `Validated NN sessions`. Inspect `data/schedule.json`: `source` should be `official-web-page`, `verifiedAt` populated and session count plausible. If scraper fails, snapshot is preserved.
4. Cloudflare → **Workers & Pages → Create → Pages → Connect to Git** → choose repository. Framework preset `None`, build command blank, **output directory `.`** (or `/` per UI). Publish.
5. Open the Pages URL: check status says `ดึงจากหน้าเว็บทางการ` and published timestamp. Select two sessions, reload, check saved selection; verify time conflicts and differences.
6. Test on actual phone. Share the HTTPS URL. If the event organizer changes its HTML structure, update `scripts/sync.mjs`; until fixed the last valid snapshot remains published.

**Important:** This is not an official API and not instantaneous real-time. GitHub Actions may run late or be paused, scraping may fail due to access restrictions, and Cloudflare deployment takes time. The status shows *when the published data was generated*, not when the last background check ran. A run with no changes doesn't re-publish the timestamp. Users should confirm last-minute changes on the official page.

## Scraping and data integrity

- Uses a standard browser against a public page, no authentication or bypass of rate limits. Respect the organizer's terms and robots policy and request permission if needed.
- Expects at least 55 total sessions, 25 on Day 1, 20 on Day 2, three Day 1 stages, and unique items. Any suspicious extraction fails and keeps the last good snapshot.
- Stable numeric IDs matched by title similarity and time/stage to retain user selections through most minor schedule edits. Very substantial title changes may be recorded as a removal/addition, in which case the UI flags the missing original selection and retains it until the user removes it.
- The `changes` array describes differences between the last two **published** snapshots. No push notifications; app checks `/data/schedule.json` every five minutes when visible or when returning to the tab.
- The snapshot is committed into Git history. It can be reviewed and rolled back.

## Local preview

`index.html` can be opened directly for offline planning, but it will show the original baseline. For a local HTTP server (with Node installed):

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000` to test `/data/schedule.json`. A local preview has no scheduled updating unless GitHub Actions is configured.

## Troubleshooting

- `REJECTED scraper output`: source page layout changed, page blocked, or parsing wrong. Inspect the workflow log and update the extraction selectors. Do **not** lower thresholds without verifying every stage/day.
- `workflow not running`: confirm Actions enabled, scheduled workflows use the repository default branch, not a fork's disabled schedule; manually dispatch a run.
- `no live feed`: review deploy build logs and ensure `data/schedule.json` exists at `/data/schedule.json`.
- `changes not showing`: they are compared to the previous committed snapshot and may be empty if there was no meaningful change.
- The standalone HTML file is an **offline demo**, not an independently syncing product.

**Unofficial, independent conference planner.** Source: https://www.bitcointhailand.co/schedule
