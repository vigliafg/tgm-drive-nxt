"""Servizio per estrarre nomi file originali dalle caption Telegram."""

import re


def extract_original_filename(caption: str) -> str:
    """Estrae il nome file originale dalla caption del messaggio Telegram.

    Se la caption sembra un nome file valido (una o più estensioni .ext),
    la usa come original_filename. Supporta doppie estensioni (.tar.gz, .min.js).
    Altrimenti restituisce stringa vuota.
    """
    if not caption or not caption.strip():
        return ""
    caption = caption.strip()
    # Deve assomigliare a un nome file: no newline/slash/backslash,
    # e contenere una o più estensioni valide (1-6 caratteri alfanumerici)
    if '\n' in caption or '/' in caption or '\\' in caption:
        return ""
    # Supporta estensioni multiple: file.tar.gz, jquery.min.js, etc.
    if re.search(r'\.(?:[a-zA-Z0-9]{1,6}\.)*[a-zA-Z0-9]{1,6}$', caption):
        return caption
    return ""
