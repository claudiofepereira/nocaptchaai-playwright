from playwright.async_api import (
    async_playwright,
    Playwright,
    Page,
    Browser,
    BrowserContext,
)
import asyncio
import os

from nocaptchaai_playwright.solver import Solver

API_KEY: str = "your-api-key"
API_URL: str = "https://pro.nocaptchaai.com/api/solve"  # Specify API URL (pro or not).


async def main() -> None:
    # Start playwright browser.
    playwright: Playwright = await async_playwright().start()
    browser: Browser = await playwright.chromium.launch(headless=False)
    context: BrowserContext = await browser.new_context(
        locale="en-GB",
        no_viewport=True,
    )
    page: Page = await context.new_page()

    os.environ["API_KEY"] = API_KEY
    os.environ["API_URL"] = API_URL

    captcha_solver = Solver()

    while True:
        await page.goto(
            "https://nopecha.com/demo/hcaptcha",
            wait_until="networkidle",
        )
        await captcha_solver.solve(page)
        await page.wait_for_timeout(1000)


if __name__ == "__main__":
    asyncio.run(main())
