import asyncio
import httpx
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from .libs.stealth import stealth_async
from .models import Novel, Chapter
from . import settings


class MangaScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.client = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        # Browser para navegar e pegar os links das imagens
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )

        # Cliente HTTP otimizado para baixar as imagens (mais rápido que o browser)
        self.client = httpx.AsyncClient(
            headers=settings.MANGA_HEADERS, follow_redirects=True, timeout=20.0
        )
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()

    async def _download_image(self, url: str, sem: asyncio.Semaphore) -> bytes | None:
        """Baixa uma única imagem com controle de concorrência."""
        async with sem:
            try:
                resp = await self.client.get(url)
                if resp.status_code == 200:
                    return resp.content
            except Exception as e:
                print(f"    [!] Erro img: {e}")
            return None

    async def extract_chapter_images(self, url: str, index: int) -> Chapter | None:
        """Entra na página do capítulo, coleta URLs e baixa as imagens."""
        print(f" -> Processando Cap {index:03d}: {url}")

        page = await self.context.new_page()
        await stealth_async(page)

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Scroll para garantir lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)  # Espera imagens carregarem

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Coleta URLs das imagens
            img_urls = []
            for img in soup.select(settings.MANGA_IMG_SELECTOR):
                # Tenta src ou data-src (lazy load comum)
                src = img.get("src") or img.get("data-src")
                src = src.strip() if src else None
                
                if src and src.startswith("http"):
                    img_urls.append(src)

            # Remove duplicatas preservando ordem
            img_urls = list(dict.fromkeys(img_urls))

            if not img_urls:
                print("    [!] Nenhuma imagem encontrada.")
                return None

            print(f"    -> Baixando {len(img_urls)} páginas...")

            # Baixa imagens em paralelo (limite de 5 simultâneas para não travar)
            sem = asyncio.Semaphore(5)
            tasks = [self._download_image(u, sem) for u in img_urls]
            images = await asyncio.gather(*tasks)

            # Filtra falhas (None)
            valid_images = [img for img in images if img]

            return Chapter(
                title=f"Capítulo {index}",
                content=valid_images,  # Lista de bytes
                url=url,
                index=index,
            )

        except Exception as e:
            print(f"    [X] Erro crítico no capítulo: {e}")
            return None
        finally:
            await page.close()

    async def run(self, start=1, end=None) -> Novel:
        novel = Novel(
            title=settings.NOVEL_TITLE, author=settings.NOVEL_AUTHOR, is_manga=True
        )

        path_parts = urlparse(settings.MANGA_INDEX_URL).path.strip("/").split("/")
        # Geralmente o slug é a última parte ou penúltima. No caso de /manga/jujutsu-kaisen/, pegamos 'jujutsu-kaisen'
        manga_slug = path_parts[-1] if path_parts[-1] else path_parts[-2]
        print(f"[Filtro] Buscando apenas links contendo: '{manga_slug}'")

        page = await self.context.new_page()
        await page.goto(settings.MANGA_INDEX_URL, wait_until="domcontentloaded")
        html = await page.content()
        await page.close()

        soup = BeautifulSoup(html, "html.parser")

        ra_links = []
        for sel in settings.CHAPTER_LINKS_SELECTOR.split(","):
            found = soup.select(sel.strip())
            if found:
                ra_links = [link["href"] for link in found if link.get("href")]
                break

        filtered_links = []
        for link in ra_links:
            # Só aceita o link se o SLUG do mangá estiver nele
            if manga_slug in link:
                filtered_links.append(link)

        # Remove duplicatas
        unique_links = list(dict.fromkeys(filtered_links))
        # Mangás costumam listar do mais novo pro mais velho, inverter se necessário
        unique_links.reverse()

        if not unique_links:
            print("[Scraper] Nenhum capítulo encontrado.")
            return novel

        end_idx = end if end else len(unique_links)
        target_links = unique_links[start - 1 : end_idx]

        print(f"[Manga] Iniciando download de {len(target_links)} capítulos.")

        for i, link in enumerate(target_links, start=start):
            if not link.startswith("http"):
                link = settings.MANGA_INDEX_URL + link  # Ajuste básico de URL

            chapter = await self.extract_chapter_images(link, i)
            if chapter:
                novel.chapters.append(chapter)

            await asyncio.sleep(2)  # Respeito ao servidor

        return novel
