import re
from pathlib import Path
from ebooklib import epub
from .models import Novel


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def build_manga_epub(novel: Novel, base_output_dir: Path) -> Path:
    safe_title = sanitize_filename(novel.title)
    novel_dir = base_output_dir / safe_title
    novel_dir.mkdir(parents=True, exist_ok=True)
    output_path = novel_dir / f"{safe_title}_Manga.epub"

    book = epub.EpubBook()
    book.set_identifier(f"manga-{safe_title.lower()}")
    book.set_title(novel.title)
    book.set_language("pt")
    book.add_author(novel.author)

    # Define como Fixed Layout (Melhora renderização de imagens no Kindle)
    book.add_metadata(
        None, "meta", "fixed-layout", {"name": "fixed-layout", "content": "true"}
    )
    book.add_metadata(None, "meta", "comic", {"name": "book-type", "content": "comic"})

    spine = []

    # Estilo Fullscreen para imagens
    style = """
        @page { margin: 0; padding: 0; }
        body { margin: 0; padding: 0; text-align: center; background-color: #000; height: 100vh; width: 100vw; }
        div.fs { width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; }
        img { max-height: 100%; max-width: 100%; object-fit: contain; }
    """
    css_item = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css", content=style
    )
    book.add_item(css_item)

    print(f"[Builder] Montando EPUB com {len(novel.chapters)} capítulos...")

    page_count = 1
    for chap in novel.chapters:
        # Se content não for lista, pula (segurança)
        if not isinstance(chap.content, list):
            continue

        for img_bytes in chap.content:
            # 1. Adiciona a imagem ao EPUB
            img_name = f"image_{page_count:05d}.jpg"
            img_item = epub.EpubItem(
                uid=f"img_{page_count}",
                file_name=f"images/{img_name}",
                media_type="image/jpeg",
                content=img_bytes,
            )
            book.add_item(img_item)

            # 2. Cria a página XHTML que exibe a imagem
            page_name = f"page_{page_count:05d}.xhtml"
            c_page = epub.EpubHtml(title=f"Page {page_count}", file_name=page_name)
            c_page.content = f"""
                <html>
                <head><link rel="stylesheet" href="style.css" type="text/css"/></head>
                <body>
                    <div class="fs">
                        <img src="images/{img_name}" alt="page"/>
                    </div>
                </body>
                </html>
            """
            c_page.add_item(css_item)
            book.add_item(c_page)
            spine.append(c_page)

            page_count += 1

    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), book)
    print(f"[Builder] Mangá EPUB gerado: {output_path}")
    return output_path
