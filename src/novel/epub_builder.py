import re
from pathlib import Path
from ebooklib import epub
from src.models import Novel


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def build_epub(novel: Novel, base_output_dir: Path) -> Path:
    safe_title = sanitize_filename(novel.title)

    # 1. Cria pasta específica para a novel
    novel_dir = base_output_dir / safe_title
    novel_dir.mkdir(parents=True, exist_ok=True)

    output_path = novel_dir / f"{safe_title}.epub"

    book = epub.EpubBook()
    book.set_identifier(f"id-{safe_title.lower().replace(' ', '-')}")
    book.set_title(novel.title)
    book.set_language("pt")
    book.add_author(novel.author)

    # CAPA
    if novel.cover_image:
        # Define a imagem interna do EPUB (usada como thumbnail)
        book.set_cover("cover.jpg", novel.cover_image)

        # Cria uma página HTML explícita para a capa (Para abrir nela ao ler)
        cover_page = epub.EpubHtml(title="Capa", file_name="cover.xhtml", lang="pt")
        cover_page.content = """
        <html>
            <head>
                <style type="text/css">
                    @page { margin: 0; padding: 0; }
                    html, body {
                        margin: 0;
                        padding: 0;
                        height: 100vh; /* Ocupa toda altura da tela */
                        width: 100%;
                        text-align: center;
                        background-color: #000000; /* Fundo preto para evitar bordas brancas */
                        /* Centralização Flexbox */
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        overflow: hidden; /* Evita barras de rolagem */
                    }
                    img {
                        /* Tenta ocupar o máximo de largura e altura possível
                           mantendo a proporção (aspect ratio) */
                        max-width: 100%;
                        max-height: 100vh;
                        height: auto;
                        width: auto;
                        /* Garante que a imagem não estique, mas preencha o espaço */
                        object-fit: contain; 
                    }
                </style>
            </head>
            <body>
                <div> <img src="cover.jpg" alt="Capa" />
                </div>
            </body>
        </html>
        """
        book.add_item(cover_page)
        book.spine.append(cover_page)

    # CSS Padrão
    style = """
        body { font-family: serif; margin: 1em; text-align: justify; }
        h1 { text-align: center; border-bottom: 1px solid #ddd; margin-bottom: 1em; }
        p { margin-bottom: 0.5em; text-indent: 1em; }
        img { max-width: 100%; }
    """
    nav_css = epub.EpubItem(
        uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style
    )
    book.add_item(nav_css)

    # Capítulos
    epub_chapters = []
    for chap in novel.chapters:
        c_item = epub.EpubHtml(
            title=chap.title, file_name=f"chap_{chap.index:04d}.xhtml", lang="pt"
        )
        c_item.content = f"<h1>{chap.title}</h1>{chap.content}"
        c_item.add_item(nav_css)
        book.add_item(c_item)
        epub_chapters.append(c_item)

    book.toc = epub_chapters
    book.spine.extend(["nav"] + epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), book)
    print(f"[EPUB] Arquivo gerado em: {output_path}")
    return output_path
