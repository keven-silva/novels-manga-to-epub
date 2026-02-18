from bs4 import Tag

AD_KEYWORDS = [
    "leia mais em",
    "leia no site",
    "tradução por",
    "traduzido por",
    "visite nosso site",
    "acesse pelo link",
    "clique aqui",
    "novel-br.com",
    "novels-br.com",
    "discord.gg",
    "apoie a tradução",
    "read at",
]

_BASE_AD_SELECTORS = [
    "script",
    "style",
    "iframe",
    ".chapter-nav",
    ".nav-buttons",
    ".ads",
    ".ad",
    ".adsbygoogle",
    ".advertisement",
    ".share-buttons",
    ".popup",
    ".modal",
    ".post-footer",
]


def _has_ad_keyword(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in AD_KEYWORDS)


def clean_html_content(content_el: Tag) -> str:
    """Higieniza o HTML removendo ads e scripts."""
    # 1. Seletores estruturais
    for sel in _BASE_AD_SELECTORS:
        for tag in content_el.select(sel):
            tag.decompose()

    # 2. Palavras-chave em blocos de texto
    for tag in content_el.find_all(["p", "div", "span", "li", "h2", "h3"]):
        if _has_ad_keyword(tag.get_text(" ", strip=True)):
            tag.decompose()

    # 3. Links "fantasmas" (banners)
    for a_tag in content_el.find_all("a", href=True):
        if a_tag["href"].startswith("http") and not a_tag.get_text(strip=True):
            a_tag.decompose()

    # 4. Limpeza de parágrafos vazios
    for tag in content_el.find_all(["p", "div"]):
        # Mantém se tiver imagem, senão remove se estiver vazio
        if not tag.find("img") and not tag.get_text(strip=True):
            tag.decompose()

    return str(content_el)
