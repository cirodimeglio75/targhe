"""Le pratiche: quali documenti servono, e dove finiscono quelli caricati.

I documenti richiesti sono quelli scritti a mano sul foglio dell'agenzia
(9/09/2026), non inventati qui:

  «Per effettuare mini passaggi occorre visura camerale, documento di
   identità dell'amministratore della società. Per effettuare passaggi di
   proprietà da società a persona fisica occorre stessa documentazione, in
   più documento di chi si deve intestare l'auto. La stessa cosa con le
   perdite di possesso. Immatricolazioni auto nuove occorrono stessa
   documentazione in più conformità e fattura, idem anche per i
   motoveicoli.»

**Quel che il foglio NON dice** e' quali documenti servano per un passaggio
fra due privati, che e' il caso piu' comune di tutti. Non e' scritto qui
perche' non lo so: chiedere all'agenzia e aggiungere una voce. Meglio una
voce mancante che una lista di documenti sbagliata, che manda una persona
a fotografare le carte due volte.

## Sulla roba che si carica

Qui dentro passano **documenti d'identita'**. Non sono file: sono dati
personali di chi si fida di noi. Le regole, tutte applicate sotto:

- **il nome del file che arriva non diventa mai un percorso.** Si tiene per
  mostrarlo, si scrive con un nome nostro. E' la prima riga di difesa di
  ogni servizio che accetta caricamenti;
- **si guarda dentro il file, non l'estensione**: i primi byte dicono se e'
  davvero una foto o un PDF. Un `.jpg` che comincia con `<?php` non e' una
  foto, e non entra;
- **l'indirizzo della pratica e' il permesso**, come il numero di telefono
  in Ops!: e' un identificativo lungo e non indovinabile, e chi non ce l'ha
  non arriva alla pratica. Finche' non c'e' un'identita' vera, questa e' la
  protezione — ed e' il motivo per cui i documenti caricati **non si
  riscaricano** da nessuna rotta: entrano e basta;
- **niente giornale con dentro i nomi**: nei registri del server finisce
  l'identificativo della pratica, mai il nome del documento ne' la targa.

Restano da fare, e sono cose da persone e non da codice: informativa,
tempo di conservazione, cancellazione a pratica chiusa. Vanno scritte
prima che questa roba veda un utente vero.
"""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import conti as registro

# Quanto puo' pesare un documento, e quanti se ne possono caricare. Una
# foto di un documento fatta col telefono sta in pochi mega; il tetto serve
# a non farsi riempire il disco da chi si annoia.
PESO_MASSIMO = 8 * 1024 * 1024
QUANTI_AL_MASSIMO = 20

# I primi byte, e cosa sono davvero. HEIC c'e' perche' gli iPhone
# fotografano cosi' di serie: rifiutarlo vorrebbe dire dire di no alla
# meta' dei telefoni senza spiegare perche'.
FIRME = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"%PDF", "pdf"),
)


def che_roba(dato: bytes) -> str:
    """Che cos'e' davvero questo file. Stringa vuota vuol dire «non lo so»."""
    for firma, tipo in FIRME:
        if dato.startswith(firma):
            return tipo
    # HEIC/HEIF: la firma sta al byte 4, dopo la lunghezza della scatola.
    if len(dato) > 12 and dato[4:8] == b"ftyp" and dato[8:12] in (
            b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"heim"):
        return "heic"
    return ""


# Le pratiche che sappiamo fare, e cosa chiedono. `chiave` e' il nome
# tecnico, `titolo` e' quel che legge una persona.
TIPI: Dict[str, Dict[str, Any]] = {
    "mini": {
        "nome": "Mini passaggio",
        "documenti": [
            ("visura", "Visura camerale della società", True),
            ("amministratore", "Documento d'identità dell'amministratore", True),
        ],
    },
    "societa-persona": {
        "nome": "Passaggio da società a persona fisica",
        "documenti": [
            ("visura", "Visura camerale della società", True),
            ("amministratore", "Documento d'identità dell'amministratore", True),
            ("intestatario", "Documento di chi si intesta l'auto", True),
        ],
    },
    "perdita": {
        "nome": "Perdita di possesso",
        "documenti": [
            ("visura", "Visura camerale della società", True),
            ("amministratore", "Documento d'identità dell'amministratore", True),
            ("intestatario", "Documento di chi si intesta il veicolo", True),
        ],
        # Il foglio dice: «da giustificare il motivo della avvenuta perdita».
        "motivo": "Perché il veicolo non è più in possesso",
    },
    "immatricolazione": {
        "nome": "Immatricolazione di un veicolo nuovo",
        "documenti": [
            ("visura", "Visura camerale della società", True),
            ("amministratore", "Documento d'identità dell'amministratore", True),
            ("intestatario", "Documento di chi si intesta il veicolo", True),
            ("conformita", "Certificato di conformità", True),
            ("fattura", "Fattura d'acquisto", True),
        ],
    },
}


# La vita di una pratica, in quattro parole. Sono in fila apposta: si va
# solo avanti, e ogni passo ha un mestiere diverso dietro.
STATI = ("aperta",      # la concessionaria sta caricando i documenti
         "consegnata",  # i documenti ci sono tutti: tocca all'agenzia
         "finita",      # l'agenzia ha caricato il documento e la ricevuta
         "saldata")     # l'amministrazione ha incassato

# I documenti che carica l'AGENZIA a lavoro finito, non la concessionaria.
DOCUMENTI_AGENZIA = (
    ("finale", "Documento della pratica completata"),
    ("ricevuta", "Ricevuta per l'amministrazione"),
)


class PraticaRifiutata(Exception):
    """Con dentro la frase da mostrare: chi carica un documento deve capire
    cosa e' andato storto, non vedere una pagina bianca."""

    def __init__(self, utente: str):
        super().__init__(utente)
        self.utente = utente


def _dove(cartella: Path, identificativo: str) -> Path:
    # L'identificativo lo generiamo noi, ma non ci si fida lo stesso: se un
    # giorno arriva da fuori, questa riga e' l'unica cosa fra un indirizzo
    # storpiato e il resto del disco.
    if not identificativo or not all(c.isalnum() or c in "-_"
                                     for c in identificativo):
        raise PraticaRifiutata("Questa pratica non esiste.")
    return Path(cartella) / identificativo


def apri(cartella: Path, tipo: str, targa: str = "",
         concessionaria: str = "", prezzo: float = 0.0,
         kw: Optional[float] = None) -> str:
    """Comincia una pratica e torna il suo identificativo.

    L'identificativo e' lungo apposta: e' l'unica chiave della pratica, e
    dev'essere impossibile arrivarci per tentativi."""
    if tipo not in TIPI:
        raise PraticaRifiutata("Non so fare questo tipo di pratica.")
    identificativo = secrets.token_urlsafe(18)
    casa = _dove(cartella, identificativo)
    casa.mkdir(parents=True, exist_ok=False)
    os.chmod(casa, 0o700)
    _scrivi(casa, {"id": identificativo, "tipo": tipo, "targa": targa,
                   "concessionaria": concessionaria,
                   "prezzo": round(float(prezzo or 0), 2), "kw": kw,
                   "stato": "aperta", "messaggi": [],
                   "aperta": int(time.time()), "documenti": {}, "motivo": ""})
    return identificativo


def _scrivi(casa: Path, pratica: Dict[str, Any]) -> None:
    provvisorio = casa / "pratica.nuova"
    provvisorio.write_text(json.dumps(pratica, ensure_ascii=False),
                           encoding="utf-8")
    os.chmod(provvisorio, 0o600)
    provvisorio.replace(casa / "pratica.json")


def leggi(cartella: Path, identificativo: str) -> Dict[str, Any]:
    casa = _dove(cartella, identificativo)
    try:
        dentro = json.loads((casa / "pratica.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PraticaRifiutata("Questa pratica non esiste.")
    dentro["manca"] = manca(dentro)
    dentro["completa"] = not dentro["manca"]
    # Lo stato non si conserva a mano: «consegnata» vuol dire «i documenti
    # ci sono tutti», ed e' una cosa che si vede guardando. Conservarlo
    # vorrebbe dire poterlo dimenticare aggiornato.
    if dentro.get("stato") in ("aperta", "consegnata"):
        dentro["stato"] = "consegnata" if dentro["completa"] else "aperta"
    return dentro


def manca(pratica: Dict[str, Any]) -> List[str]:
    """I titoli dei documenti obbligatori non ancora arrivati."""
    tipo = TIPI.get(pratica.get("tipo", ""), {})
    caricati = pratica.get("documenti") or {}
    return [titolo for chiave, titolo, obbligatorio in tipo.get("documenti", [])
            if obbligatorio and chiave not in caricati]


def aggiungi(cartella: Path, identificativo: str, chiave: str,
             dato: bytes, nome_dato: str = "") -> Dict[str, Any]:
    """Mette un documento nella pratica. Torna la pratica aggiornata."""
    pratica = leggi(cartella, identificativo)
    tipo = TIPI[pratica["tipo"]]
    chiavi = {c for c, _, _ in tipo["documenti"]}
    chiavi |= {c for c, _ in DOCUMENTI_AGENZIA}
    if chiave not in chiavi:
        raise PraticaRifiutata("Questo documento non serve per questa pratica.")
    if not dato:
        raise PraticaRifiutata("Il file è arrivato vuoto: riprova.")
    if len(dato) > PESO_MASSIMO:
        raise PraticaRifiutata(
            "Il file è troppo grande: al massimo %d MB."
            % (PESO_MASSIMO // (1024 * 1024)))
    if len(pratica.get("documenti") or {}) >= QUANTI_AL_MASSIMO:
        raise PraticaRifiutata("Troppi documenti in questa pratica.")
    roba = che_roba(dato)
    if not roba:
        raise PraticaRifiutata(
            "Accetto solo foto (JPG, PNG, HEIC) o PDF. Se hai fotografato "
            "il documento col telefono, va bene così com'è.")

    casa = _dove(cartella, identificativo)
    # Il nome lo scegliamo NOI. Quello che arriva dal telefono si tiene solo
    # per mostrarlo, e non tocca il disco.
    percorso = casa / ("%s.%s" % (chiave, roba))
    provvisorio = casa / ("%s.nuovo" % chiave)
    provvisorio.write_bytes(dato)
    os.chmod(provvisorio, 0o600)
    provvisorio.replace(percorso)

    documenti = pratica.get("documenti") or {}
    documenti[chiave] = {"file": percorso.name, "tipo": roba,
                         "peso": len(dato), "quando": int(time.time()),
                         "nome_dato": (nome_dato or "")[:120]}
    pratica["documenti"] = documenti
    pratica.pop("manca", None)
    pratica.pop("completa", None)
    _scrivi(casa, pratica)
    return leggi(cartella, identificativo)


def documento(cartella: Path, identificativo: str,
              chiave: str) -> "tuple[bytes, str, str]":
    """Il contenuto di un documento: i byte, il tipo, e il nome da mostrare.

    **Chi puo' chiederlo lo decide chi chiama**, con `puo_vedere`: questa
    funzione non conosce i mestieri. Il tipo torna da quel che abbiamo
    stabilito NOI guardando i primi byte quando il file e' entrato, non da
    quel che aveva dichiarato il telefono: e' l'unica cosa di cui ci
    possiamo fidare al momento di rimandarlo indietro a un browser.
    """
    pratica = leggi(cartella, identificativo)
    dentro = (pratica.get("documenti") or {}).get(chiave)
    if not dentro:
        raise PraticaRifiutata("Questo documento non c'è.")
    percorso = _dove(cartella, identificativo) / str(dentro.get("file", ""))
    # Il nome viene dal nostro appunto, ma si ricontrolla lo stesso che sia
    # un nome e non un percorso: e' l'ultima riga prima del disco.
    if percorso.parent != _dove(cartella, identificativo):
        raise PraticaRifiutata("Questo documento non c'è.")
    try:
        return (percorso.read_bytes(), str(dentro.get("tipo", "")),
                str(dentro.get("nome_dato") or percorso.name))
    except OSError:
        raise PraticaRifiutata("Questo documento non c'è.")


def scrivi_motivo(cartella: Path, identificativo: str, motivo: str) -> None:
    """Il perché della perdita di possesso: lo chiede il foglio dell'agenzia."""
    pratica = leggi(cartella, identificativo)
    casa = _dove(cartella, identificativo)
    pratica["motivo"] = (motivo or "").strip()[:500]
    pratica.pop("manca", None)
    pratica.pop("completa", None)
    _scrivi(casa, pratica)


# ------------------------------------------------- chi la puo' vedere, e come

def puo_vedere(pratica: Dict[str, Any], conto: Optional[Dict[str, Any]]) -> bool:
    """Se questo conto puo' aprire questa pratica.

    L'agenzia e l'amministrazione vedono tutto, per mestiere. Una
    concessionaria vede **soltanto le sue**: e' la riga che tiene separati i
    clienti fra loro, e non c'e' nessun caso in cui va allentata.
    """
    if not conto:
        return False
    if conto.get("ruolo") in ("agenzia", "amministrazione"):
        return True
    return bool(conto.get("concessionaria")
                and conto["concessionaria"] == pratica.get("concessionaria"))


def elenco(cartella: Path, concessionaria: str = "",
           stato: str = "") -> List[Dict[str, Any]]:
    """Le pratiche, dalla piu' nuova. Senza documenti e senza messaggi:
    e' un elenco, e un elenco non ha bisogno di portarsi dietro tutto."""
    fuori = []
    for casa in sorted(Path(cartella).glob("*/pratica.json")):
        try:
            dentro = json.loads(casa.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dentro, dict):
            continue
        dentro["manca"] = manca(dentro)
        dentro["completa"] = not dentro["manca"]
        if dentro.get("stato") in ("aperta", "consegnata"):
            dentro["stato"] = "consegnata" if dentro["completa"] else "aperta"
        if concessionaria and dentro.get("concessionaria") != concessionaria:
            continue
        if stato and dentro.get("stato") != stato:
            continue
        dentro.pop("messaggi", None)
        fuori.append(dentro)
    return sorted(fuori, key=lambda p: p.get("aperta", 0), reverse=True)


def per_concessionaria(cartella: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Le pratiche raggruppate per concessionaria: e' cosi' che le guarda
    l'agenzia, perche' e' cosi' che poi le fattura."""
    fuori: Dict[str, List[Dict[str, Any]]] = {}
    for pratica in elenco(cartella):
        fuori.setdefault(pratica.get("concessionaria") or "senza nome",
                         []).append(pratica)
    return fuori


# ------------------------------------------------------------- i messaggi

def messaggio(cartella: Path, identificativo: str, conto: Dict[str, Any],
              testo: str) -> Dict[str, Any]:
    """Una riga di conversazione dentro la pratica.

    E' il posto dove l'agenzia dice «questo documento non si legge» e la
    concessionaria risponde. Sta dentro la pratica e non in una chat a
    parte apposta: fra sei mesi, chi riapre la pratica trova li' il perche'
    di quel che e' successo.
    """
    testo = (testo or "").strip()
    if not testo:
        raise PraticaRifiutata("Il messaggio è vuoto.")
    pratica = leggi(cartella, identificativo)
    casa = _dove(cartella, identificativo)
    messaggi = pratica.get("messaggi") or []
    messaggi.append({"chi": conto.get("nome") or conto.get("utente", ""),
                     "ruolo": conto.get("ruolo", ""),
                     "testo": testo[:2000], "quando": int(time.time())})
    pratica["messaggi"] = messaggi[-200:]
    for volatile in ("manca", "completa"):
        pratica.pop(volatile, None)
    _scrivi(casa, pratica)
    return leggi(cartella, identificativo)


# --------------------------------------------- quel che carica l'agenzia

def chiudi(cartella: Path, identificativo: str) -> Dict[str, Any]:
    """La pratica e' finita: c'e' il documento e c'e' la ricevuta.

    Non si chiude a mano con un tasto «fatto»: si chiude quando le due
    carte ci sono davvero. Uno stato che si puo' dichiarare senza le carte
    e' uno stato di cui non ci si puo' fidare al conteggio del sabato.
    """
    pratica = leggi(cartella, identificativo)
    documenti = pratica.get("documenti") or {}
    if not all(c in documenti for c, _ in DOCUMENTI_AGENZIA):
        raise PraticaRifiutata("Per chiudere servono il documento della "
                               "pratica e la ricevuta.")
    casa = _dove(cartella, identificativo)
    pratica["stato"] = "finita"
    pratica["finita_il"] = int(time.time())
    for volatile in ("manca", "completa"):
        pratica.pop(volatile, None)
    _scrivi(casa, pratica)
    return leggi(cartella, identificativo)


def segna_in_nota(cartella: Path, identificativo: str, nota: str) -> None:
    """Questa pratica e' finita in una nota di saldo: non ci finira' piu'.

    Senza questo segno, la nota della settimana dopo riconterebbe le
    pratiche di quella prima — sono ancora «finita», perche' finita vuol
    dire lavorata, non pagata. Il banco l'ha trovato al secondo sabato
    simulato: una concessionaria si sarebbe vista fatturare due volte lo
    stesso lavoro.
    """
    pratica = leggi(cartella, identificativo)
    casa = _dove(cartella, identificativo)
    pratica["nota"] = nota
    for volatile in ("manca", "completa"):
        pratica.pop(volatile, None)
    _scrivi(casa, pratica)


def segna_saldata(cartella: Path, identificativo: str, nota: str) -> None:
    pratica = leggi(cartella, identificativo)
    casa = _dove(cartella, identificativo)
    pratica["stato"] = "saldata"
    pratica["nota"] = nota
    pratica["saldata_il"] = int(time.time())
    for volatile in ("manca", "completa"):
        pratica.pop(volatile, None)
    _scrivi(casa, pratica)
