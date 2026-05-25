import asyncio
from playwright.async_api import async_playwright
import json
import os

SESSION_FILE = "data/cookies.json"

async def save_cookies(context):
    cookies = await context.cookies()
    with open(SESSION_FILE, "w") as f:
        json.dump(cookies, f)

async def load_cookies(context):
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            cookies = json.load(f)
            await context.add_cookies(cookies)

async def login(username, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://www.facebook.com/")
        await page.fill('input[name="email"]', username)
        await page.fill('input[name="pass"]', password)
        await page.click('button[name="login"]')
        
        # Tunggu navigasi atau deteksi login berhasil
        await page.wait_for_load_state("networkidle")
        
        await save_cookies(context)
        await browser.close()
        print("Login berhasil dan sesi disimpan.")
