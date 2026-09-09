"""La posta: la nota di saldo che arriva alla concessionaria.

Un solo mestiere — mandare un messaggio con un PDF attaccato — e nessuna
libreria in piu': `smtplib` e `email` sono nella scatola di Python da
sempre e le sanno fare tutte e due.

Le regole, come per gli SMS di Ops!:

- **la configurazione viene dall'ambiente**, e se manca il programma non
  esplode: dice che la posta non e' configurata, e la nota resta comunque
  scaricabile dall'area. Meglio una nota che aspetta che un conteggio che
  fallisce a meta';
- **c'e' la prova a vuoto** (`prova=True`): costruisce il messaggio per
  intero e non lo manda. E' il modo di provare che l'allegato e
  l'intestazione sono giusti senza scrivere a un cliente vero;
- **chi spedisce si puo' sostituire** (`spedizioniere`), ed e' cosi' che il
  banco guarda dentro la busta senza toccare nessun server di posta.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Callable, Dict, Optional

ATTESA = 20


class PostaRifiutata(Exception):
    def __init__(self, messaggio: str, utente: str = ""):
        super().__init__(messaggio)
        self.utente = utente or ("Non riesco a mandare la posta in questo "
                                 "momento.")


def da_ambiente() -> Dict[str, str]:
    return {"server": os.environ.get("SERVER_POSTA", "").strip(),
            "porta": os.environ.get("PORTA_POSTA", "587").strip(),
            "utente": os.environ.get("UTENTE_POSTA", "").strip(),
            "parola": os.environ.get("PAROLA_POSTA", "").strip(),
            "da": os.environ.get("DA_POSTA", "").strip()}


def configurata() -> bool:
    """Se si puo' mandare davvero. Le pagine lo chiedono invece di
    scoprirlo fallendo."""
    dentro = da_ambiente()
    return bool(dentro["server"] and dentro["da"])


def componi(a: str, oggetto: str, testo: str, allegato: bytes = b"",
            nome_allegato: str = "") -> EmailMessage:
    dentro = da_ambiente()
    messaggio = EmailMessage()
    messaggio["From"] = dentro["da"] or "targhe@localhost"
    messaggio["To"] = a
    messaggio["Subject"] = oggetto
    messaggio.set_content(testo)
    if allegato:
        messaggio.add_attachment(allegato, maintype="application",
                                 subtype="pdf",
                                 filename=nome_allegato or "nota.pdf")
    return messaggio


def manda(a: str, oggetto: str, testo: str, allegato: bytes = b"",
          nome_allegato: str = "", prova: bool = False,
          spedizioniere: Optional[Callable[[EmailMessage], None]] = None
          ) -> bool:
    """Manda il messaggio. Torna `True` se e' partito davvero.

    `prova` costruisce tutto e non manda: la stessa strada, senza il
    francobollo.
    """
    a = (a or "").strip()
    if not a:
        raise PostaRifiutata("nessun destinatario",
                             "Questa concessionaria non ha un indirizzo di "
                             "posta: aggiungilo per mandarle la nota.")
    messaggio = componi(a, oggetto, testo, allegato, nome_allegato)
    if spedizioniere is not None:
        spedizioniere(messaggio)
        return True
    if prova:
        return False
    dentro = da_ambiente()
    if not configurata():
        raise PostaRifiutata("posta non configurata",
                             "La posta non è configurata su questo server: "
                             "la nota resta scaricabile dall'area.")
    try:
        with smtplib.SMTP(dentro["server"], int(dentro["porta"] or 587),
                          timeout=ATTESA) as filo:
            filo.ehlo()
            if filo.has_extn("starttls"):
                # Le credenziali non viaggiano in chiaro: se il server sa
                # fare STARTTLS lo si usa, e si rifa' ehlo dopo.
                filo.starttls(context=ssl.create_default_context())
                filo.ehlo()
            if dentro["utente"]:
                filo.login(dentro["utente"], dentro["parola"])
            filo.send_message(messaggio)
    except (smtplib.SMTPException, OSError, ValueError) as e:
        raise PostaRifiutata("posta: %s" % e) from e
    return True
