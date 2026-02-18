import asyncio
from src import settings
from src.scraper import NovelScraper
from src.manga_scraper import MangaScraper
from src.manga_builder import build_manga_epub
from src.epub_builder import build_epub
from src.mailer import send_to_kindle


async def main():
    print(f"--- INICIANDO --- MODO: {'MANGÁ' if settings.IS_MANGA else 'NOVEL TEXTO'}")

    novel = None

    if settings.IS_MANGA:
        # Modo Mangá
        async with MangaScraper() as scraper:
            # Baixa apenas 1 capítulo para teste inicial (mangás são pesados!)
            novel = await scraper.run(start=1, end=None)
    else:
        # Modo Texto
        async with NovelScraper() as scraper:
            novel = await scraper.run(start=1, end=None)

    if not novel or not novel.chapters:
        print("[Main] Conteúdo vazio. Encerrando.")
        return

    # Escolhe o construtor correto
    if settings.IS_MANGA:
        epub_path = build_manga_epub(novel, settings.OUTPUT_BASE_DIR)
    else:
        epub_path = build_epub(novel, settings.OUTPUT_BASE_DIR)

    # Verifica tamanho antes de enviar (Send-to-Kindle limita a ~50MB)
    file_size_mb = epub_path.stat().st_size / (1024 * 1024)
    print(f"[Arquivo] Tamanho final: {file_size_mb:.2f} MB")

    if file_size_mb > 50:
        print("[!] ATENÇÃO: Arquivo maior que 50MB. O envio por email vai falhar.")
        print("[!] Recomendo passar via cabo USB ou usar 'Send to Kindle for Web'.")
    else:
        send_to_kindle(
            epub_path,
            settings.KINDLE_EMAIL,
            settings.GMAIL_ADDRESS,
            settings.GMAIL_APP_PWD,
        )


if __name__ == "__main__":
    asyncio.run(main())
