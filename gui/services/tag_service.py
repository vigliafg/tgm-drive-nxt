"""Servizio per la gestione dei tag pendenti durante upload."""


class PendingTagManager:
    """Gestisce i tag pendenti da applicare ai file dopo l'upload.

    Quando l'utente uploada file con un tag selezionato,
    il tag viene registrato come 'pendente'. Quando Telegram
    notifica la lista file aggiornata, il tag viene applicato.
    """

    def __init__(self):
        self._pending: dict[str, list[str]] = {}

    def add(self, filename: str, tag: str) -> None:
        """Registra un tag pendente per un filename."""
        if tag:
            self._pending.setdefault(filename, []).append(tag)

    def pop(self, filename: str) -> str:
        """Recupera e rimuove il prossimo tag pendente.

        Restituisce stringa vuota se non ci sono tag pendenti.
        """
        tag_list = self._pending.get(filename, [])
        tag = tag_list.pop(0) if tag_list else ""
        if not tag_list:
            self._pending.pop(filename, None)
        return tag
