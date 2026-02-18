import asyncio
import httpx
# import shutil
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from src.libs.stealth import stealth_async
from src.models import Novel, Chapter
from src import settings


class MangaScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.client = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.client = httpx.AsyncClient(
            headers=settings.MANGA_HEADERS, follow_redirects=True, timeout=20.0
        )
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()

    def _get_chapter_dir(self, index: int) -> Path:
        """Define o caminho da pasta para cada capítulo."""
        # Ex: novels_output/Jujutsu Kaisen/chapters/chap_001
        safe_title = (
            settings.NOVEL_TITLE.strip()
        )  # Remove caracteres perigosos se necessário
        return settings.OUTPUT_BASE_DIR / safe_title / "chapters" / f"chap_{index:03d}"

    def _save_images_to_disk(self, chapter_dir: Path, images: list[bytes]):
        """Salva as imagens baixadas no disco para cache."""
        chapter_dir.mkdir(parents=True, exist_ok=True)
        for i, img_bytes in enumerate(images, start=1):
            file_path = chapter_dir / f"image_{i:04d}.jpg"
            file_path.write_bytes(img_bytes)

    def _load_images_from_disk(self, chapter_dir: Path) -> list[bytes]:
        """Carrega imagens do disco se já existirem (resume)."""
        images = []
        # Pega todos os arquivos jpg/jpeg/png e ordena pelo nome (importante!)
        files = sorted(chapter_dir.glob("*.*"))
        for f in files:
            if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                images.append(f.read_bytes())
        return images

    async def _download_image(self, url: str, sem: asyncio.Semaphore) -> bytes | None:
        async with sem:
            try:
                resp = await self.client.get(url)
                if resp.status_code == 200:
                    return resp.content
            except Exception as e:
                print(f"    [!] Erro img: {e}")
            return None

    async def extract_chapter_images(self, url: str, index: int) -> Chapter | None:
        # 1. VERIFICAÇÃO DE CACHE (Resume Logic)
        chapter_dir = self._get_chapter_dir(index)

        # Se a pasta existe e tem arquivos, assumimos que já foi baixado
        if chapter_dir.exists() and any(chapter_dir.iterdir()):
            print(f" -> [Cache] Cap {index:03d} já existe no disco. Carregando...")
            cached_images = self._load_images_from_disk(chapter_dir)
            if cached_images:
                return Chapter(
                    title=f"Capítulo {index}",
                    content=cached_images,
                    url=url,
                    index=index,
                )
            # Se a pasta existe mas está vazia (erro anterior), continua para baixar de novo...

        # 2. DOWNLOAD (Se não estiver no cache)
        print(f" -> [Download] Cap {index:03d}: {url}")

        page = await self.context.new_page()
        await stealth_async(page)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Scroll para lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            img_urls = []
            # Seletores abrangentes para garantir que pegamos as imagens
            for img in soup.select(
                "div[id*='reader'] img, .reading-content img, img[class*='page-image']"
            ):
                src = img.get("src") or img.get("data-src")
                if src:
                    src = src.strip()
                    if src.startswith("http"):
                        img_urls.append(src)

            img_urls = list(dict.fromkeys(img_urls))

            if not img_urls:
                print("    [!] Nenhuma imagem encontrada na página.")
                return None

            print(f"    -> Baixando {len(img_urls)} imagens...")

            sem = asyncio.Semaphore(5)
            tasks = [self._download_image(u, sem) for u in img_urls]
            images = await asyncio.gather(*tasks)
            valid_images = [img for img in images if img]

            if valid_images:
                # 3. SALVAR NO DISCO (Para não perder se o script parar depois)
                self._save_images_to_disk(chapter_dir, valid_images)

            return Chapter(
                title=f"Capítulo {index}",
                content=valid_images,
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

        # Filtro de SLUG para garantir que é o mangá certo
        path_parts = urlparse(settings.MANGA_INDEX_URL).path.strip("/").split("/")
        manga_slug = path_parts[-1] if path_parts[-1] else path_parts[-2]
        print(f"[Filtro] Buscando apenas links contendo: '{manga_slug}'")

        page = await self.context.new_page()
        await page.goto(settings.MANGA_INDEX_URL, wait_until="domcontentloaded")
        await page.evaluate("window.scrollTo(0, 500)")
        await asyncio.sleep(1)

        html = await page.content()
        await page.close()

        soup = BeautifulSoup(html, "html.parser")

        raw_links = []
        for sel in settings.CHAPTER_LINKS_SELECTOR.split(","):
            found = soup.select(sel.strip())
            if found:
                raw_links.extend([link["href"] for link in found if link.get("href")])

        # Filtragem por slug
        filtered_links = []
        for link in raw_links:
            if manga_slug in link:
                filtered_links.append(link)

        unique_links = list(dict.fromkeys(filtered_links))
        unique_links.reverse()  # Ajuste conforme a ordem do site (Decrescente -> Crescente)

        if not unique_links:
            print("[Scraper] Nenhum capítulo encontrado.")
            return novel

        end_idx = end if end else len(unique_links)
        target_links = unique_links[start - 1 : end_idx]

        print(f"[Manga] Processando {len(target_links)} capítulos (Cache + Download).")

        for i, link in enumerate(target_links, start=start):
            if not link.startswith("http"):
                base_domain = "https://mangalivre.to"
                link = (
                    base_domain + link
                    if link.startswith("/")
                    else f"{base_domain}/{link}"
                )

            chapter = await self.extract_chapter_images(link, i)

            # Mesmo se falhar o download, verificamos se tem algo no disco
            # (Caso raro onde o site falha mas tinhamos backup parcial)
            if not chapter:
                # Tenta carregar do disco uma última vez caso o scrape falhe
                chap_dir = self._get_chapter_dir(i)
                if chap_dir.exists() and any(chap_dir.iterdir()):
                    print(
                        f"    [Info] Falha na rede, mas usando versão em disco para Cap {i}."
                    )
                    imgs = self._load_images_from_disk(chap_dir)
                    chapter = Chapter(title=f"Cap {i}", content=imgs, url=link, index=i)

            if chapter and chapter.content:
                novel.chapters.append(chapter)
            else:
                print(f"    [!] Capítulo {i} ignorado (vazio ou erro).")

            # Pequeno delay apenas se foi um download real (opcional, mantive fixo)
            await asyncio.sleep(0.5)

        return novel
