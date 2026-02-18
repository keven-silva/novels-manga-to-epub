import asyncio
import random
import httpx
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Importação da biblioteca de furtividade
from src.libs.stealth import stealth_async
from src.models import Novel, Chapter
from src.cleaner import clean_html_content
from src import settings


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

    def _get_chapter_dir(self, index: int) -> Path:
        """Define o caminho da pasta para cada capítulo (cache)."""
        # Ex: novels_output/Nome da Novel/chapters/chap_001
        safe_title = settings.NOVEL_TITLE.strip()
        return settings.OUTPUT_BASE_DIR / safe_title / "chapters" / f"chap_{index:03d}"

    def _save_chapter_to_disk(self, chapter_dir: Path, chapter: Chapter):
        """Salva o conteúdo do capítulo (HTML) no disco."""
        chapter_dir.mkdir(parents=True, exist_ok=True)
        # Salva o texto/HTML em um arquivo txt ou html
        file_path = chapter_dir / "content.html"
        # Precisamos salvar o título também para reconstruir depois
        # Uma forma simples é salvar título num arquivo separado ou usar um json
        file_path.write_text(chapter.content, encoding="utf-8")
        (chapter_dir / "title.txt").write_text(chapter.title, encoding="utf-8")
        (chapter_dir / "url.txt").write_text(chapter.url, encoding="utf-8")

    def _load_chapter_from_disk(self, chapter_dir: Path, index: int) -> Chapter | None:
        """Carrega capítulo do disco se existir."""
        content_path = chapter_dir / "content.html"
        title_path = chapter_dir / "title.txt"
        url_path = chapter_dir / "url.txt"

        if content_path.exists() and title_path.exists():
            content = content_path.read_text(encoding="utf-8")
            title = title_path.read_text(encoding="utf-8")
            url = url_path.read_text(encoding="utf-8") if url_path.exists() else ""
            return Chapter(title=title, content=content, url=url, index=index)
        return None

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
        # Primeiro verifica se tem imagem salva localmente na pasta da novel (cache manual)
        safe_title = settings.NOVEL_TITLE.strip()
        local_cache_path = settings.OUTPUT_BASE_DIR / safe_title / "cover.jpg"

        if settings.COVER_MODE == "local":
            path = Path(settings.COVER_FILE_PATH)
            if path.exists():
                return path.read_bytes()
            # Se não achar no path configurado, tenta no cache padrão
            if local_cache_path.exists():
                return local_cache_path.read_bytes()
            return None

        # Verifica cache automático antes de baixar
        if local_cache_path.exists():
            print("[Capa] Usando capa em cache do disco.")
            return local_cache_path.read_bytes()

        print("[Capa] Buscando capa no site...")
        html = await self._fetch_html_with_retry(index_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        img_url = None
        for sel in (
            settings.COVER_SELECTORS
        ):  # Assumindo que você tem COVER_SELECTORS no settings
            # Se não tiver, substitua por uma lista hardcoded ou adicione no settings
            # Ex: settings.COVER_SELECTORS = [".book-cover img", ".novel-cover img"]
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
                    # Salva no cache
                    local_cache_path.parent.mkdir(parents=True, exist_ok=True)
                    local_cache_path.write_bytes(resp.content)
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
        # 1. VERIFICAÇÃO DE CACHE
        chapter_dir = self._get_chapter_dir(index)
        cached_chapter = self._load_chapter_from_disk(chapter_dir, index)

        if cached_chapter:
            print(f" -> [Cache] Cap {index:03d} carregado do disco.")
            return cached_chapter

        # 2. DOWNLOAD (Se não estiver no cache)
        print(f" -> [Download] Cap {index:03d}: {url}")
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
            print(f"    [!] Conteúdo não encontrado para: {url}")
            return None

        clean = clean_html_content(content_el)

        # Cria o objeto capítulo
        chapter = Chapter(title=title, content=clean, url=url, index=index)

        # 3. SALVAR NO DISCO
        self._save_chapter_to_disk(chapter_dir, chapter)

        return chapter

    async def run(self, start=1, end=None) -> Novel:
        novel = Novel(title=settings.NOVEL_TITLE, author=settings.NOVEL_AUTHOR)
        novel.cover_image = await self._get_cover_image(settings.INDEX_URL)

        links = await self.get_chapter_links(settings.INDEX_URL)
        if not links:
            return novel

        end_idx = end if end else len(links)
        target_links = links[start - 1 : end_idx]

        print(
            f"[Scraper] Processando {len(target_links)} capítulos (Cache + Download)..."
        )

        for i, link in enumerate(target_links, start=start):
            # A extração agora gerencia o cache internamente
            chapter = await self.extract_chapter(link, i)

            if chapter:
                novel.chapters.append(chapter)
 

            # Moverei o delay para dentro do loop apenas se NÃO for cache:
            chapter_dir = self._get_chapter_dir(i)

            # Hack rápido: se a pasta do proximo capitulo não existe, sleep.
            next_chap_dir = self._get_chapter_dir(i + 1)
            if not next_chap_dir.exists():
                delay = random.uniform(
                    settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX
                )
                if i % 10 == 0:
                    print("    (Pausa para descanso de 10s...)")
                    delay = 10.0
                await asyncio.sleep(delay)

        return novel
