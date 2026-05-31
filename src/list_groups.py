import asyncio
from playwright.async_api import async_playwright
import os
import json

SESSION_FILE = "../auth.json"

async def list_groups():
    if not os.path.exists(SESSION_FILE):
        print("Sesi tidak ditemukan. Silakan login terlebih dahulu.")
        return

    async with async_playwright() as p:
        # browser = await p.chromium.launch(headless=True)
        browser = await p.chromium.launch()
        context = await browser.new_context()
        
        # Load cookies
        with open(SESSION_FILE, "r") as f:
            cookies = json.load(f)
            cookies = cookies['cookies']
            await context.add_cookies(cookies)
            
        page = await context.new_page()
        await page.goto("https://www.facebook.com/groups/joins")
        await page.wait_for_load_state("domcontentloaded")

        # Mengincar elemen yang berisi tautan grup di halaman 'joined groups'
        groups = await page.eval_on_selector_all('div[role="listitem"] a[href*="/groups/"]', '''(elements) => {
            return elements
                .map(el => ({ 
                    name: el.innerText.trim(), 
                    url: el.href 
                }))
                .filter(item => item.name && item.url.includes('/groups/') && !item.url.includes('/groups/joined'))
        }''')

        # text_konten = await groups.inner_text()

        print(f"Nama/Teks Grup: {groups}")
        
        # Filter duplikat dan bersihkan
        unique_groups = {g['url']: g['name'] for g in groups}
        
        for url, name in unique_groups.items():
            print(f"Nama: {name}, URL: {url}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(list_groups())
