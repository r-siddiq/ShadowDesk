
import asyncio
import os
import sys
import time
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:18501"
CREDENTIALS = {"username": "admin", "password": "shadowdesk"}

async def validate_ui():
    async with async_playwright() as p:
        # Launch headed browser
        print("Launching headed browser...")
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Login Page
        print("Validating Login Page...")
        await page.goto(BASE_URL)
        
        # Wait for the login form elements
        await page.wait_for_selector("input[placeholder='Username']", timeout=30000)
        await page.fill("input[placeholder='Username']", CREDENTIALS["username"])
        await page.fill("input[placeholder='Password']", CREDENTIALS["password"])
        
        print("Submitting login form...")
        await page.click("text=▶ AUTHENTICATE")

        # Verify redirect to Dashboard
        try:
            await page.wait_for_selector("text=Dashboard", timeout=20000)
            print("Login successful, redirected to Dashboard.")
        except Exception as e:
            print(f"Login failed or redirect did not happen: {e}")
            # Keep browser open for a bit to see error
            await asyncio.sleep(10)
            await browser.close()
            return

        # 2. Dashboard Page
        print("Validating Dashboard Page...")
        await page.wait_for_selector("text=Portfolio Value", timeout=10000)
        print("Dashboard loaded successfully.")

        # 3. Signals Page
        print("Navigating to Signals Page...")
        try:
            # Using a more flexible selector for sidebar links
            await page.click("text=Signals", timeout=10000)
            await page.wait_for_selector("text=Signals", timeout=10000)
            print("Signals page loaded.")
        except Exception as e:
            print(f"Failed to navigate to Signals: {e}")

        # 4. Trade Execution Page
        print("Navigating to Trade Execution Page...")
        try:
            await page.click("text=Trade Execution", timeout=10000)
            await page.wait_for_selector("text=Orders", timeout=10000)
            print("Trade Execution page loaded.")
        except Exception as e:
            print(f"Failed to navigate to Trade Execution: {e}")

        # 5. Analytics Page
        print("Navigating to Analytics Page...")
        try:
            await page.click("text=Analytics", timeout=10000)
            await page.wait_for_selector("text=Performance", timeout=10000)
            print("Analytics page loaded.")
        except Exception as e:
            print(f"Failed to navigate to Analytics: {e}")

        # 6. Settings Page
        print("Navigating to Settings Page...")
        try:
            await page.click("text=Settings", timeout=10000)
            await page.wait_for_selector("text=Risk", timeout=10000)
            print("Settings page loaded.")
        except Exception as e:
            print(f"Failed to navigate to Settings: {e}")

        print("Validation sequence complete. Browser will remain open for 10 minutes.")
        # Keep open for visual validation
        await asyncio.sleep(600) 
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(validate_ui())
    except Exception as e:
        print(f"Error during execution: {e}")
