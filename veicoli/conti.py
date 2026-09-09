"""Chi entra, e cosa puo' vedere.

Finora la chiave di una pratica era il suo indirizzo. Con tre mestieri
diversi — **concessionaria**, **agenzia**, **amministrazione** — quello non
basta piu': l'agenzia deve vedere le pratiche di tutti, la concessionaria
solo le sue, e l'amministrazione i conti. Serve sapere chi c'e' dall'altra
parte, e da qui in poi lo si sa perche' e' entrato.

Le scelte, e il perche':

- **la parola d'ordine si conserva impastata con `scrypt`**, mai in chiaro
  e mai con un riassunto veloce: se un giorno qualcuno legge il file dei
  conti, non deve uscirne una lista di parole d'ordine da provare altrove.
  Ognuna ha il suo sale, cosi' due persone con la stessa parola hanno due
  impronte diverse;
- **il confronto e' a tempo costante** (`compare_digest`): confrontare due
  impronte con `==` racconta, dal tempo che ci mette, quante lettere
  iniziali erano giuste;
- **entrare da' una chiave di sessione, non ripete la parola**. La chiave
  vive in un biscotto `HttpOnly` — cioe' nessuno script della pagina la
  puo' leggere — e scade;
- **chi non e' entrato non vede niente di privato.** La ricerca per targa
  resta aperta a tutti: quella e' la vetrina. Le pratiche no.

Non c'e' registrazione da fuori: i conti li fa l'amministrazione. In un
mestiere dove il credito e' assegnato a mano, chiunque possa aprirsi un
conto da solo e' un buco nel plafond.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

RUOLI = ("concessionaria", "agenzia", "amministrazione")

# Quanto dura una sessione senza toccare niente. Una giornata di lavoro con
# margine: chi apre pratiche la mattina non deve rientrare dopo pranzo.
DURATA = 12 * 3600

# Il costo dell'impasto. Piu' alto costa a noi una volta e a chi prova le
# parole d'ordine un milione di volte.
FATICA = 2 ** 14


class ContoRifiutato(Exception):
    def __init__(self, utente: str):
        super().__init__(utente)
        self.utente = utente


def _leggi(percorso: Path) -> Dict[str, Any]:
    try:
        dentro = json.loads(percorso.read_text(encoding="utf-8"))
        return dentro if isinstance(dentro, dict) else {}
    except (OSError, ValueError):
        return {}


def _scrivi(percorso: Path, roba: Dict[str, Any]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    provvisorio = percorso.with_suffix(".nuovo")
    provvisorio.write_text(json.dumps(roba, ensure_ascii=False),
                           encoding="utf-8")
    os.chmod(provvisorio, 0o600)
    provvisorio.replace(percorso)


def _impasta(parola: str, sale: str) -> str:
    return hashlib.scrypt(parola.encode("utf-8"), salt=bytes.fromhex(sale),
                          n=FATICA, r=8, p=1, dklen=32).hex()


# ----------------------------------------------------------------- i conti

def conti(cartella: Path) -> Dict[str, Any]:
    return _leggi(Path(cartella) / "conti.json")


def crea(cartella: Path, nome_utente: str, parola: str, ruolo: str,
         concessionaria: str = "", nome: str = "") -> Dict[str, Any]:
    """Fa un conto. Lo chiama l'amministrazione, non un modulo pubblico."""
    nome_utente = (nome_utente or "").strip().lower()
    if not nome_utente or len(parola or "") < 8:
        raise ContoRifiutato("Serve un nome e una parola d'ordine di almeno "
                             "8 caratteri.")
    if ruolo not in RUOLI:
        raise ContoRifiutato("Questo ruolo non esiste.")
    if ruolo == "concessionaria" and not concessionaria:
        raise ContoRifiutato("Un conto di concessionaria deve dire quale.")
    tutti = conti(cartella)
    if nome_utente in tutti:
        raise ContoRifiutato("Questo nome è già preso.")
    sale = secrets.token_hex(16)
    tutti[nome_utente] = {"utente": nome_utente, "nome": nome or nome_utente,
                          "ruolo": ruolo, "concessionaria": concessionaria,
                          "sale": sale, "impronta": _impasta(parola, sale),
                          "attivo": True, "quando": int(time.time())}
    _scrivi(Path(cartella) / "conti.json", tutti)
    return tutti[nome_utente]


def cambia_parola(cartella: Path, nome_utente: str, parola: str) -> None:
    tutti = conti(cartella)
    conto = tutti.get((nome_utente or "").strip().lower())
    if not conto:
        raise ContoRifiutato("Questo conto non esiste.")
    if len(parola or "") < 8:
        raise ContoRifiutato("La parola d'ordine deve essere di almeno 8 "
                             "caratteri.")
    conto["sale"] = secrets.token_hex(16)
    conto["impronta"] = _impasta(parola, conto["sale"])
    _scrivi(Path(cartella) / "conti.json", tutti)


def prova(cartella: Path, nome_utente: str,
          parola: str) -> Optional[Dict[str, Any]]:
    """Il conto, se nome e parola tornano. `None` non dice mai quale dei due
    era sbagliato: dirlo regala meta' della risposta a chi tenta."""
    conto = conti(cartella).get((nome_utente or "").strip().lower())
    if not conto or not conto.get("attivo"):
        # Si impasta lo stesso, con un sale finto: senza, il tempo di
        # risposta direbbe quali nomi utente esistono.
        _impasta(parola or "", secrets.token_hex(16))
        return None
    atteso = conto.get("impronta", "")
    if not hmac.compare_digest(_impasta(parola or "", conto["sale"]), atteso):
        return None
    return conto


# ------------------------------------------------------------- le sessioni

def entra(cartella: Path, conto: Dict[str, Any]) -> str:
    chiave = secrets.token_urlsafe(24)
    sessioni = _leggi(Path(cartella) / "sessioni.json")
    adesso = int(time.time())
    # Si fa pulizia mentre si passa: le sessioni scadute non devono
    # accumularsi in un file che cresce per sempre.
    sessioni = {k: v for k, v in sessioni.items()
                if isinstance(v, dict) and adesso - v.get("quando", 0) < DURATA}
    sessioni[chiave] = {"utente": conto["utente"], "quando": adesso}
    _scrivi(Path(cartella) / "sessioni.json", sessioni)
    return chiave


def chi(cartella: Path, chiave: str) -> Optional[Dict[str, Any]]:
    """Chi ha questa chiave, o niente. Non solleva mai: una chiave finta e'
    una risposta normale, non un guasto."""
    if not chiave:
        return None
    sessione = _leggi(Path(cartella) / "sessioni.json").get(chiave)
    if not isinstance(sessione, dict):
        return None
    if int(time.time()) - sessione.get("quando", 0) >= DURATA:
        return None
    conto = conti(cartella).get(sessione.get("utente", ""))
    return conto if conto and conto.get("attivo") else None


def esci(cartella: Path, chiave: str) -> None:
    sessioni = _leggi(Path(cartella) / "sessioni.json")
    if sessioni.pop(chiave, None) is not None:
        _scrivi(Path(cartella) / "sessioni.json", sessioni)


# --------------------------------------------------------- le concessionarie

def concessionarie(cartella: Path) -> Dict[str, Any]:
    return _leggi(Path(cartella) / "concessionarie.json")


def salva_concessionaria(cartella: Path, identificativo: str, nome: str,
                         plafond: float, posta: str = "") -> Dict[str, Any]:
    """Nome e plafond di una concessionaria. Il plafond lo decide
    l'amministrazione, ed e' il tetto di quanto puo' restare da saldare."""
    identificativo = (identificativo or "").strip().lower()
    if not identificativo or not all(c.isalnum() or c in "-_"
                                     for c in identificativo):
        raise ContoRifiutato("L'identificativo della concessionaria può "
                             "avere solo lettere, numeri, - e _.")
    tutte = concessionarie(cartella)
    dentro = tutte.get(identificativo, {})
    dentro.update({"id": identificativo, "nome": nome or identificativo,
                   "plafond": max(0.0, float(plafond or 0))})
    # L'indirizzo si aggiorna solo se ne arriva uno: passare vuoto vuol
    # dire «non lo sto cambiando», non «cancellalo». Cancellare per
    # omissione e' il modo piu' rapido di smettere di mandare le note
    # credendo di aver salvato il plafond.
    if posta.strip():
        dentro["posta"] = posta.strip()
    tutte[identificativo] = dentro
    _scrivi(Path(cartella) / "concessionarie.json", tutte)
    return dentro


def concessionaria(cartella: Path, identificativo: str) -> Dict[str, Any]:
    return concessionarie(cartella).get(identificativo or "", {})
