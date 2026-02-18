import os
from pathlib import Path

# ── DADOS DA NOVEL ────────────────────────────────────────────
NOVEL_TITLE = "Jujutsu Kaisen"
NOVEL_AUTHOR = "Desconhecido"
# INDEX_URL = "https://novels-br.com/novels/sobrevivendo-no-jogo-como-um-barbaro/"
INDEX_URL = "https://illusia.com.br/story/sobrevivendo-no-jogo-como-um-barbaro/"

COVER_MODE = "local" # "local" ou "auto"
# Caminho da imagem se modo="local" (use r"" para evitar erros no Windows)
COVER_FILE_PATH = r"./novels_output/Jujutsu Kaisen/jujutsu-kaisen.jpeg"

# ── SELETORES CSS ─────────────────────────────────────────────
CHAPTER_LINKS_SELECTOR = (
    "a[href*='/viewer/'], "
    "a[href*='capitulo'], a[href*='chapter'], "
    ".chapter-item a, .chapters-list a, .listing-chapters_wrap a"
)

CONTENT_SELECTORS = [
    ".reading-content",
    ".chapter-content",
    ".entry-content",
    "#chapter-content",
    "article .content",
    "div.text-left",
    ".post-content",
]

TITLE_SELECTORS = [
    ".chapter-title",
    "h1.entry-title",
    "h1",
    ".wp-block-heading",
]

# ── CONFIGURAÇÕES TÉCNICAS ────────────────────────────────────
OUTPUT_BASE_DIR = Path("./novels_output")

# Delay entre requisições (segundos) — respeite o servidor!
REQUEST_DELAY_MIN = 2.0
REQUEST_DELAY_MAX = 5.0

# RETRY (Resiliência)
MAX_RETRIES = 3

# Envio para o Kindle (deixe vazio para não enviar)
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL")  # ex: "seunome@kindle.com"
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")  # ex: "seuemail@gmail.com"
GMAIL_APP_PWD = os.getenv("GMAIL_APP_PWD")

# ── MANGÁ / WEBTOON (NOVO) ────────────────────────────────────
IS_MANGA = True  # Alterne para False se for baixar Novel de texto

# URL de exemplo (Mangá)
# Substitua por um link real de mangá (ex: site como mangalivre, etc)
MANGA_INDEX_URL = "https://mangalivre.to/manga/jujutsu-kaisen/"

# Seletor que encontra as IMAGENS dentro do capítulo
# Dica: Procure por tags img dentro de divs de leitura
MANGA_IMG_SELECTOR = "img[src^='blob:'], .viewer-container img, .reading-content img"

# Headers são cruciais para mangás (evita erro 403 Forbidden nas imagens)
MANGA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://mangalivre.to/",  # Muitas CDNs bloqueiam sem referer
}