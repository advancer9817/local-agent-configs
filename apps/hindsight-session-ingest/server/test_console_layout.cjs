// Run with NODE_PATH pointing to a Playwright installation; no production data is written.
const {chromium} = require("playwright-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const source = process.env.CONSOLE_ASSETS || path.join(__dirname, "access_console");
const output = process.env.CONSOLE_SHOTS || "/tmp/hindsight-console-layout";
const now = Date.now() / 1000;
const grant = {bank_id: "mcore-active-snapshot", permission: "write"};
const users = [
  {id: 1, username: "admin", role: "admin", disabled: false, note: "初始管理员", grants: [], active_tokens: 0, last_login: now},
  {id: 2, username: "gcp-local", role: "user", disabled: false, note: "本机 Codex/Claude 客户端",
    grants: [grant], active_tokens: 1, last_login: null},
];
const state = {auth_enabled: true, users, banks: [
  {bank_id: "mcore-active-snapshot", name: "mcore active snapshot comparison", fact_count: 693},
  {bank_id: "学习", name: "学习", fact_count: 0},
], tokens: [{id: 1, user_id: 2, username: "gcp-local", name: "local", prefix: "example", created: now}], audit: []};

async function run() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"]});
  try {
    for (const [width, height] of (process.env.NARROW_ONLY ? [[320, 740]] : [[1920, 920], [1280, 800], [390, 844], [320, 740]])) {
      for (const theme of ["light", "dark"]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/access/**", async route => {
          const pathname = new URL(route.request().url()).pathname;
          if (process.env.LIVE_ASSETS && pathname.startsWith("/access/static/")) return route.continue();
          if (pathname.startsWith("/access/api/")) {
            assert.equal(route.request().method(), "GET", "Layout checks must not change accounts or permissions");
            const data = pathname.endsWith("/me")
              ? {id: 1, username: "admin", role: "admin", csrf: "fixture", auth_enabled: true}
              : state;
            return route.fulfill({json: data});
          }
          const filename = pathname.startsWith("/access/static/") ? path.basename(pathname) : "index.html";
          return route.fulfill({path: path.join(source, filename)});
        });
        await page.goto("http://127.0.0.1:19999/access/");
        await page.waitForSelector("[data-user]");
        await page.evaluate(theme => {
          localStorage.setItem("theme", theme);
          document.documentElement.classList.toggle("dark", theme === "dark");
        }, theme);
        const tag = `${width}-${theme}`;
        const noPageOverflow = async () => {
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
          if (overflow) {
            console.log(await page.evaluate(() => [...document.querySelectorAll("body *")]
              .filter(node => !node.closest(".table-wrap") && node.getBoundingClientRect().right > innerWidth + 1)
              .map(node => [node.tagName, node.className, node.getBoundingClientRect().right]).slice(0, 12)));
            await page.screenshot({path: `${output}/overflow-${tag}.png`, fullPage: true});
          }
          assert.equal(overflow, false, tag + " page overflow");
        };
        await noPageOverflow();
        const button = page.locator('[data-open="2"]');
        await button.scrollIntoViewIfNeeded();
        await page.waitForTimeout(150);
        await button.hover();
        await page.waitForTimeout(100);
        const hover = await page.evaluate(() => {
          const table = document.querySelector(".table-wrap");
          const tip = document.querySelector("#control-tooltip");
          const rect = tip?.getBoundingClientRect();
          return {extraHeight: table.scrollHeight - table.clientHeight, visible: tip && !tip.hidden,
            fits: rect && rect.left >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight};
        });
        assert.equal(hover.extraHeight, 0, tag + " tooltip creates table vertical scrollbar");
        assert.equal(hover.visible, true, tag + " tooltip missing");
        assert.equal(hover.fits, true, tag + " tooltip outside viewport");
        await page.screenshot({path: `${output}/users-${tag}.png`, fullPage: true});
        await button.click();
        await page.waitForSelector(".drawer");
        assert.equal(await page.locator("#control-tooltip").isVisible(), false, "Stale tooltip behind drawer");
        await page.locator("#dr-bank").focus();
        await page.waitForTimeout(100);
        await page.locator("#dr-bank").click();
        await page.waitForSelector("#bank-options:not([hidden])");
        const menuGeometry = await page.evaluate(() => {
          const input = document.querySelector("#dr-bank").getBoundingClientRect();
          const menu = document.querySelector("#bank-options").getBoundingClientRect();
          return {aligned: Math.abs(input.left - menu.left) < 1, sameWidth: Math.abs(input.width - menu.width) < 1,
            fits: menu.left >= 0 && menu.right <= innerWidth && menu.top >= 0 && menu.bottom <= innerHeight,
            aboveOtherControls: getComputedStyle(document.querySelector("#bank-options")).position === "fixed"};
        });
        assert.deepEqual(menuGeometry, {aligned: true, sameWidth: true, fits: true, aboveOtherControls: true}, tag);
        assert.equal(await page.locator("datalist").count(), 0);
        await page.screenshot({path: `${output}/drawer-${tag}.png`});
        await page.locator("#bank-options [role=option]").filter({hasText: "学习"}).click();
        assert.equal(await page.locator("#dr-bank").inputValue(), "学习");
        assert.equal(await page.locator("#dr-bank").getAttribute("aria-expanded"), "false");
        await page.locator("#dr-bank").fill("snapshot comparison");
        assert.equal(await page.locator("#bank-options [role=option]").count(), 1);
        await page.locator("#dr-bank").press("ArrowDown");
        await page.locator("#dr-bank").press("Enter");
        assert.equal(await page.locator("#dr-bank").inputValue(), "mcore-active-snapshot");
        await page.locator("#dr-bank").fill("unlisted-bank-id");
        assert.equal(await page.locator(".bank-empty").isVisible(), true);
        await page.locator("#dr-bank").press("Escape");
        assert.equal(await page.locator("#dr-bank").inputValue(), "unlisted-bank-id");
        assert.equal(await page.locator("#bank-options").isVisible(), false);
        await page.locator("#dr-bank").fill("");
        await page.locator("#dr-bank").press("Tab");
        assert.equal(await page.locator("#bank-options").isVisible(), false);
        await page.locator(".bank-toggle").click();
        assert.equal(await page.locator("#bank-options").isVisible(), true);
        await page.locator("#dr-bank").press("ArrowUp");
        await page.locator("#dr-bank").press("Enter");
        assert.equal(await page.locator("#dr-bank").inputValue(), "学习");
        await page.locator(".bank-toggle").click();
        assert.equal(await page.locator("#bank-options").isVisible(), true);
        await page.locator(".bank-toggle").click();
        assert.equal(await page.locator("#bank-options").isVisible(), false);
        await page.locator(".bank-toggle").click();
        await page.locator("#dr-note").click();
        assert.equal(await page.locator("#bank-options").isVisible(), false);
        const layout = await page.evaluate(() => {
          const body = document.querySelector(".drawer .body");
          const input = document.querySelector("#dr-bank").getBoundingClientRect();
          const actions = document.querySelector(".grant-actions").getBoundingClientRect();
          return {overflow: body.scrollWidth > body.clientWidth, inputFits: input.right <= innerWidth - 10,
            stacked: actions.top >= input.bottom};
        });
        assert.equal(layout.overflow, false, tag + " drawer horizontal overflow");
        assert.equal(layout.inputFits, true, tag + " input clipped");
        assert.equal(layout.stacked, true, tag + " grant form overlaps");
        await noPageOverflow();
        await page.locator(".drawer [data-close-drawer]").click();
        await page.locator('[data-open="1"]').click();
        await page.locator("#dr-own-password").click();
        await page.waitForSelector("#pw-old");
        await page.screenshot({path: `${output}/modal-${tag}.png`});
        await noPageOverflow();
        await page.locator("#overlay [data-close]").first().click();
        await page.locator(".drawer [data-close-drawer]").click();
        await page.locator("#new-user").click();
        await page.locator("#nu-bank").click();
        await page.waitForSelector("#bank-options:not([hidden])");
        await page.screenshot({path: `${output}/new-user-dropdown-${tag}.png`});
        await page.locator("#nu-bank").fill("学习");
        await page.locator("#nu-bank").press("ArrowDown");
        await page.locator("#nu-bank").press("Enter");
        assert.equal(await page.locator("#nu-bank").inputValue(), "学习");
        await page.locator("#overlay [data-close]").first().click();
        assert.equal(await page.locator("#bank-options").isVisible(), false);
        for (const tab of ["banks", "tokens", "settings"]) {
          await page.locator(`[data-tab="${tab}"]`).click();
          await noPageOverflow();
        }
        assert.deepEqual(errors, [], tag + " browser errors");
        console.log("PASS", tag);
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
