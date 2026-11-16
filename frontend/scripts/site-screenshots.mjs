// Screenshots for the GitHub Pages site, from a running local app (http://localhost:3000).
// Sign in as a demo account with no watchlist or holdings, so no personal data is captured:
//   DEMO_EMAIL=... DEMO_PASSWORD=... node scripts/site-screenshots.mjs
import { chromium } from "@playwright/test"

const BASE = process.env.APP_URL ?? "http://localhost:3000"
const OUT = new URL("../../site/img/", import.meta.url).pathname
// A made-up tradebook for the tax page: real symbols, invented trades
const TRADEBOOK = [
    "symbol,trade_date,trade_type,quantity,price",
    "M&M,2024-01-15,buy,10,1650",
    "INFY,2025-12-01,buy,15,1600",
    "IRFC,2026-06-15,buy,300,150",
    "ITC,2023-07-03,buy,200,450",
    "ITC,2026-07-10,sell,50,420",
].join("\n")

const shots = [
    { name: "markets", path: "/markets" },
    { name: "stock", path: "/research/RELIANCE.NS" },
    { name: "screener", path: "/explorer" },
    { name: "concalls", path: "/concalls" },
    { name: "risk", path: "/risk/RELIANCE.NS" },
    { name: "tax", path: "/tax", upload: true },
]

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: "dark" })
await page.goto(`${BASE}/login`)
await page.fill("#email", process.env.DEMO_EMAIL)
await page.fill("#password", process.env.DEMO_PASSWORD)
await page.click('button[type="submit"]')
await page.waitForURL(u => !u.pathname.startsWith("/login"), { timeout: 20000 })

for (const shot of shots) {
    await page.goto(`${BASE}${shot.path}`)
    await page.waitForLoadState("networkidle", { timeout: 60000 }).catch(() => {})
    if (shot.upload) {
        await page.getByLabel("Tradebook CSV files").setInputFiles({ name: "tradebook.csv", mimeType: "text/csv", buffer: Buffer.from(TRADEBOOK) })
        await page.getByText(/This financial year/).waitFor({ timeout: 60000 })
    }
    await page.waitForTimeout(2500)  // charts animate in
    // Buy / Hold calls on real stocks would be investment advice on a public page: blur just the labels
    await page.evaluate(() => {
        const calls = new Set(["Buy", "Hold", "Avoid", "Weak numbers"])
        document.querySelectorAll('section[aria-label="Verdict"] .text-xl, td span.font-bold').forEach(el => {
            if (el.closest('section[aria-label="Verdict"]') || calls.has(el.textContent?.trim() ?? "")) {
                el.style.filter = "blur(7px)"
            }
        })
    })
    await page.screenshot({ path: `${OUT}${shot.name}.png` })
    console.log("saved", shot.name)
}
await browser.close()
