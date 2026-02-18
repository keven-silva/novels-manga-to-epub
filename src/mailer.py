import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import unicodedata
import re


def normalize_for_email(text: str) -> str:
    """
    Converte 'Ação & Aventura.epub' para 'Acao__Aventura.epub'.
    Remove acentos e garante que o nome do anexo seja 100% compatível com qualquer email.
    """
    # 1. Normaliza unicode (ex: á -> a)
    nfkd_form = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd_form.encode("ASCII", "ignore").decode("ASCII")

    # 2. Substitui espaços e simbolos por underline
    clean_text = re.sub(r"[^a-zA-Z0-9._-]", "_", ascii_text)

    # 3. Remove underlines duplicados para ficar limpo
    return re.sub(r"_+", "_", clean_text)


def send_to_kindle(epub_path: Path, kindle_email: str, gmail_user: str, gmail_pwd: str):
    if not all([kindle_email, gmail_user, gmail_pwd]):
        print("[Email] Credenciais ausentes. Envio pulado.")
        return

    safe_filename = normalize_for_email(epub_path.name)

    print(f"[Email] Preparando envio de: {epub_path.name}")
    print(f"[Email] Nome no anexo (seguro): {safe_filename}")

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = kindle_email
    msg["Subject"] = "convert"  # Necessário para converter PDF, bom manter para EPUB

    # Lendo arquivo em modo binário
    try:
        with open(epub_path, "rb") as f:
            # application/epub+zip é o MIME correto para EPUB
            part = MIMEBase("application", "epub+zip")
            part.set_payload(f.read())

        # Codificação essencial para não corromper binários
        encoders.encode_base64(part)

        # Header seguro. 'filename' sem caracteres especiais ajuda na compatibilidade
        part.add_header(
            "Content-Disposition", f"attachment; filename*=utf-8''{safe_filename}"
        )

        msg.attach(part)

        # Envio SSL (Porta 465)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pwd)
            server.sendmail(gmail_user, kindle_email, msg.as_string())

        print("[Email] Enviado com sucesso para o Kindle!")

    except Exception as e:
        print(f"[Email] Erro crítico ao enviar: {e}")
