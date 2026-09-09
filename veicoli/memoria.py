"""La memoria dei risultati: la stessa targa non si paga due volte.

Qui ogni chiamata al fornitore costa venti centesimi, e la stessa targa viene
cercata piu' volte — da chi ci ripensa, da chi ricarica la pagina, da due
persone diverse che guardano la stessa auto usata. Senza memoria, una app del
genere si fa svuotare il portafoglio in un pomeriggio.

Le scadenze sono diverse per tipo di dato, e non e' un dettaglio: i dati
tecnici di un veicolo non cambiano mai (marca, cilindrata, prima
immatricolazione), la polizza cambia ogni anno e va guardata piu' spesso.
Tenere tutto per novanta giorni vorrebbe dire mostrare una polizza scaduta
come valida — cioe' l'unico errore che la gente ci rinfaccerebbe davvero.

Un file per targa e servizio, scritto con la mossa del provvisorio-e-sposta:
due richieste sulla stessa targa nello stesso istante non si rovinano a
vicenda, e un programma ucciso a meta' scrittura non lascia mezzo file.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Quanto vale un risultato, in secondi. Il numero e' una scelta, non una
# legge: se un giorno il fornitore dichiara la freschezza dei suoi dati,
# questi diventano quelli.
SCADENZE = {
    "auto": 90 * 24 * 3600,        # dati di targa: non cambiano
    "moto": 90 * 24 * 3600,
    "assicurazione": 24 * 3600,    # cambia, ed e' quella che si guarda
    "sconosciuta": 7 * 24 * 3600,  # «questa targa non risulta»: vedi sotto
}
# Anche il «non risulta» si ricorda, ed e' la memoria che conta di piu':
# senza, chi cicla targhe a caso ci fa pagare ogni tentativo a vuoto.


def _dove(cartella: Path, servizio: str, targa: str) -> Path:
    return Path(cartella) / ("%s-%s.json" % (servizio, targa))


def leggi(cartella: Optional[Path], servizio: str,
          targa: str) -> Optional[Dict[str, Any]]:
    """Quel che sappiamo gia', se non e' scaduto. `None` vuol dire «chiedi».

    Nessun guasto della memoria deve fermare una ricerca: file rotto,
    cartella sparita o disco pieno si traducono tutti in «non lo so».
    """
    if not cartella:
        return None
    try:
        dentro = json.loads(_dove(cartella, servizio, targa)
                            .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dentro, dict):
        return None
    quando = dentro.get("quando", 0)
    dura = SCADENZE.get(dentro.get("servizio", servizio), 24 * 3600)
    if not isinstance(quando, (int, float)) or time.time() - quando > dura:
        return None
    return dentro


def scrivi(cartella: Optional[Path], servizio: str, targa: str,
           roba: Dict[str, Any]) -> None:
    """Annota il risultato. Se non riesce, pazienza: si ripaghera' la
    chiamata, ma la ricerca dell'utente non deve fallire per un disco."""
    if not cartella:
        return
    appunto = dict(roba)
    appunto["servizio"] = servizio
    appunto["targa"] = targa
    appunto["quando"] = int(time.time())
    percorso = _dove(cartella, servizio, targa)
    provvisorio = percorso.with_suffix(".nuovo.%d" % os.getpid())
    try:
        Path(cartella).mkdir(parents=True, exist_ok=True)
        provvisorio.write_text(json.dumps(appunto, ensure_ascii=False),
                               encoding="utf-8")
        provvisorio.replace(percorso)
    except OSError:
        try:
            provvisorio.unlink()
        except OSError:
            pass


def dimentica(cartella: Optional[Path], servizio: str, targa: str) -> bool:
    """Butta via quel che sappiamo di una targa.

    Serve al tasto «correggi»: quando l'utente dice che il dato e' sbagliato,
    la prima cosa da fare e' non ripetergli la stessa risposta dalla memoria.
    """
    if not cartella:
        return False
    try:
        _dove(cartella, servizio, targa).unlink()
        return True
    except OSError:
        return False
