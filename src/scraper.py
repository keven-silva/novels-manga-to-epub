import asyncio
import random
import httpx
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Importação da biblioteca de furtividade
from .libs.stealth import stealth_async

from .models import Novel, Chapter
from .cleaner import clean_html_content
from . import settings


class NovelScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        # Flags para evitar detecção de automação
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-browser-side-navigation",
            "--disable-features=VizDisplayCompositor",
        ]
        self.browser = await self.playwright.chromium.launch(headless=True, args=args)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
        )

        # Aplica a máscara de furtividade na página
        page = await self.context.new_page()
        await stealth_async(page)
        await page.close()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _fetch_html_with_retry(self, url: str) -> str | None:
        """Tenta baixar o HTML com mecanismo de retry e backoff exponencial."""
        for attempt in range(1, settings.MAX_RETRIES + 1):
            page = await self.context.new_page()
            # Garante stealth em cada nova página
            await stealth_async(page)

            try:
                # Timeout maior para conexões lentas
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # Simula comportamento humano (scroll leve)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                await asyncio.sleep(random.uniform(0.5, 1.5))

                content = await page.content()
                await page.close()
                return content

            except Exception as e:
                print(
                    f"[!] Erro na tentativa {attempt}/{settings.MAX_RETRIES} para {url}: {e}"
                )
                await page.close()
                if attempt < settings.MAX_RETRIES:
                    # Backoff: Espera 10s, depois 20s, depois 30s...
                    wait_time = attempt * 10
                    print(f"    -> Aguardando {wait_time}s para tentar novamente...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"[✗] Falha definitiva em: {url}")
                    return None

    # ── LÓGICA DE CAPA ─────────────────────────────────────────
    async def _get_cover_image(self, index_url: str) -> bytes | None:
        if settings.COVER_MODE == "local":
            path = Path(settings.COVER_FILE_PATH)
            if path.exists():
                return path.read_bytes()
            return None

        print("[Capa] Buscando capa no site...")
        html = await self._fetch_html_with_retry(index_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        img_url = None
        for sel in settings.COVER_SELECTORS:
            if img := soup.select_one(sel):
                img_url = img.get("src") or img.get("data-src")
                if img_url:
                    break

        if not img_url:
            return None

        full_url = urljoin(index_url, img_url)
        try:
            # Tenta baixar a imagem com headers de navegador real
            headers = {"User-Agent": "Mozilla/5.0"}
            async with httpx.AsyncClient(
                headers=headers, follow_redirects=True
            ) as client:
                resp = await client.get(full_url, timeout=15)
                if resp.status_code == 200:
                    return resp.content
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────

    async def get_chapter_links(self, index_url: str) -> list[str]:
        print(f"[Scraper] Analisando índice: {index_url}")
        html = await self._fetch_html_with_retry(index_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        for sel in settings.CHAPTER_LINKS_SELECTOR.split(","):
            found = soup.select(sel.strip())
            if found:
                links = [urljoin(index_url, a["href"]) for a in found if a.get("href")]
                break

        unique = list(dict.fromkeys(links))
        # Se a ordem estiver invertida (Capítulo final primeiro), inverta:
        # unique.reverse()
        print(f"[Scraper] Encontrados {len(unique)} capítulos.")
        return unique

    async def extract_chapter(self, url: str, index: int) -> Chapter | None:
        html = await self._fetch_html_with_retry(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        title = f"Capítulo {index}"
        for sel in settings.TITLE_SELECTORS:
            if el := soup.select_one(sel):
                title = el.get_text(strip=True)
                break

        content_el = None
        for sel in settings.CONTENT_SELECTORS:
            if content_el := soup.select_one(sel):
                break

        if not content_el:
            return None

        clean = clean_html_content(content_el)
        return Chapter(title=title, content=clean, url=url, index=index)

    async def run(self, start=1, end=None) -> Novel:
        novel = Novel(title=settings.NOVEL_TITLE, author=settings.NOVEL_AUTHOR)
        novel.cover_image = await self._get_cover_image(settings.INDEX_URL)

        links = await self.get_chapter_links(settings.INDEX_URL)
        if not links:
            return novel

        end_idx = end if end else len(links)
        target_links = links[start - 1 : end_idx]

        print(
            f"[Scraper] Baixando {len(target_links)} capítulos com atraso humanizado..."
        )

        for i, link in enumerate(target_links, start=start):
            print(f" -> Cap {i:03d}")
            chapter = await self.extract_chapter(link, i)
            if chapter:
                novel.chapters.append(chapter)

            # DELAY ALEATÓRIO E HUMANIZADO
            delay = random.uniform(
                settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX
            )
            # A cada 10 capítulos, faz uma pausa maior (cafezinho do robô)
            if i % 10 == 0:
                print("    (Pausa para descanso de 10s...)")
                delay = 10.0

            await asyncio.sleep(delay)

        return novel
