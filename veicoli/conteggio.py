"""Il plafond, il conteggio del sabato, e la nota di saldo.

Il giro, come l'ha descritto il proprietario: l'amministrazione assegna a
ogni concessionaria un **plafond**; le pratiche che l'agenzia ha finito e
che nessuno ha ancora pagato lo consumano; **il sabato mattina** si fa il
conteggio della settimana e parte la **nota di saldo**; la concessionaria
salda **entro il lunedi'** e il plafond torna libero.

Tre cose che questo file fa apposta, e che sono il motivo per cui esiste:

- **l'esposizione si CALCOLA, non si tiene.** E' la somma delle pratiche
  non ancora saldate, letta dalle pratiche ogni volta. Un contatore da
  aggiornare a mano e' un contatore che un giorno sbaglia, e quel giorno
  qualcuno lavora gratis o si vede rifiutare una pratica che poteva fare;
- **il plafond si controlla PRIMA di aprire la pratica**, non dopo. Dopo
  vuol dire che qualcuno ha gia' fotografato i documenti;
- **la nota di saldo e' un documento fermo.** Una volta emessa elenca
  quelle pratiche li' e quel totale li': se il sabato dopo si ricontasse
  tutto da capo, una pratica arrivata nel frattempo cambierebbe una nota
  gia' mandata a un cliente.
"""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import conti as registro
from . import pratiche as pr


class ConteggioRifiutato(Exception):
    def __init__(self, utente: str):
        super().__init__(utente)
        self.utente = utente


def esposizione(cartella_pratiche: Path, concessionaria: str) -> float:
    """Quanto ha in ballo una concessionaria: tutto quel che non e' saldato.

    Conta anche le pratiche ancora aperte, non solo quelle finite: il
    plafond serve a sapere quanto lavoro si sta prendendo in carico, e una
    pratica aperta e' lavoro che qualcuno sta gia' facendo.
    """
    totale = 0.0
    for pratica in pr.elenco(cartella_pratiche, concessionaria):
        if pratica.get("stato") != "saldata":
            totale += float(pratica.get("prezzo") or 0)
    return round(totale, 2)


def quanto_resta(cartella_conti: Path, cartella_pratiche: Path,
                 concessionaria: str) -> Dict[str, Any]:
    dentro = registro.concessionaria(cartella_conti, concessionaria)
    plafond = float(dentro.get("plafond") or 0)
    usato = esposizione(cartella_pratiche, concessionaria)
    return {"concessionaria": concessionaria,
            "nome": dentro.get("nome", concessionaria),
            "plafond": plafond, "usato": usato,
            "resta": round(plafond - usato, 2)}


def puo_aprire(cartella_conti: Path, cartella_pratiche: Path,
               concessionaria: str, prezzo: float) -> None:
    """Solleva se questa pratica sfonda il plafond. Silenzio vuol dire si'."""
    conto = quanto_resta(cartella_conti, cartella_pratiche, concessionaria)
    if conto["plafond"] <= 0:
        raise ConteggioRifiutato(
            "Questa concessionaria non ha ancora un plafond assegnato: "
            "chiedi all'amministrazione.")
    if float(prezzo or 0) > conto["resta"]:
        raise ConteggioRifiutato(
            "Il plafond non basta per questa pratica: restano %.2f € su "
            "%.2f €. Salda la nota per liberarlo."
            % (conto["resta"], conto["plafond"]))


# ------------------------------------------------------- la nota di saldo

def _dove(cartella_note: Path, identificativo: str) -> Path:
    if not identificativo or not all(c.isalnum() or c in "-_"
                                     for c in identificativo):
        raise ConteggioRifiutato("Questa nota non esiste.")
    return Path(cartella_note) / (identificativo + ".json")


def settimana(quando: Optional[float] = None) -> str:
    """La settimana come la scrive il calendario: «2026-37».

    `%G-%V` e non `%Y-%W`: la settimana ISO sta col suo anno anche a
    cavallo di Capodanno, dove il vecchio modo fa nascere una «settimana
    00» che non esiste in nessun calendario appeso al muro."""
    return time.strftime("%G-%V", time.localtime(quando or time.time()))


def emetti(cartella_note: Path, cartella_pratiche: Path,
           concessionaria: str) -> Dict[str, Any]:
    """La nota di saldo per una concessionaria: le pratiche finite e il totale.

    Si prendono le pratiche **finite** e non ancora saldate. Quelle ancora
    aperte non entrano: si paga il lavoro fatto, non quello in corso.
    """
    righe = [p for p in pr.elenco(cartella_pratiche, concessionaria, "finita")]
    if not righe:
        raise ConteggioRifiutato(
            "Non c'è niente da conteggiare per questa concessionaria.")
    identificativo = "%s-%s-%s" % (settimana(), concessionaria,
                                   secrets.token_hex(3))
    nota = {"id": identificativo, "concessionaria": concessionaria,
            "settimana": settimana(), "quando": int(time.time()),
            "saldata": False,
            "righe": [{"pratica": p["id"], "targa": p.get("targa", ""),
                       "tipo": p.get("tipo", ""),
                       "prezzo": float(p.get("prezzo") or 0)} for p in righe],
            "totale": round(sum(float(p.get("prezzo") or 0) for p in righe), 2)}
    Path(cartella_note).mkdir(parents=True, exist_ok=True)
    percorso = _dove(cartella_note, identificativo)
    provvisorio = percorso.with_suffix(".nuova")
    provvisorio.write_text(json.dumps(nota, ensure_ascii=False),
                           encoding="utf-8")
    os.chmod(provvisorio, 0o600)
    provvisorio.replace(percorso)
    return nota


def leggi(cartella_note: Path, identificativo: str) -> Dict[str, Any]:
    try:
        return json.loads(_dove(cartella_note, identificativo)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ConteggioRifiutato("Questa nota non esiste.")


def note(cartella_note: Path, concessionaria: str = "") -> List[Dict[str, Any]]:
    fuori = []
    for percorso in sorted(Path(cartella_note).glob("*.json")):
        try:
            dentro = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if concessionaria and dentro.get("concessionaria") != concessionaria:
            continue
        fuori.append(dentro)
    return sorted(fuori, key=lambda n: n.get("quando", 0), reverse=True)


def segna_saldata(cartella_note: Path, cartella_pratiche: Path,
                  identificativo: str) -> Dict[str, Any]:
    """La concessionaria ha pagato: le pratiche della nota escono dal
    plafond, e il plafond torna libero."""
    nota = leggi(cartella_note, identificativo)
    if nota.get("saldata"):
        raise ConteggioRifiutato("Questa nota risulta già saldata.")
    for riga in nota.get("righe", []):
        try:
            pr.segna_saldata(cartella_pratiche, riga["pratica"],
                             identificativo)
        except pr.PraticaRifiutata:
            continue        # una pratica sparita non blocca l'incasso
    nota["saldata"] = True
    nota["saldata_il"] = int(time.time())
    percorso = _dove(cartella_note, identificativo)
    provvisorio = percorso.with_suffix(".nuova")
    provvisorio.write_text(json.dumps(nota, ensure_ascii=False),
                           encoding="utf-8")
    os.chmod(provvisorio, 0o600)
    provvisorio.replace(percorso)
    return nota
