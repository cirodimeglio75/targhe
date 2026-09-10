"""L'orologio: quel che la piattaforma fa da sola, senza che nessuno prema.

Due appuntamenti, come li ha descritti il proprietario:

- **il sabato mattina** si chiude la settimana: per ogni concessionaria con
  pratiche finite si emette la nota di saldo, si emette la fattura, e
  partono per posta col PDF attaccato;
- **ogni giorno** si guarda chi non ha saldato entro il lunedi', e a chi e'
  in ritardo parte un **sollecito con l'estratto conto** allegato.

Tre regole che tengono in piedi una cosa che gira da sola:

1. **si tiene il registro di quel che si e' gia' fatto.** Un giro che si
   ripete e' una concessionaria che riceve due volte la stessa nota, o due
   fatture per lo stesso credito. Il registro dice: questa settimana l'ho
   gia' chiusa, questo sollecito l'ho gia' mandato ieri;
2. **il sollecito ha un passo**, non e' un rubinetto: uno ogni `PASSO`
   giorni. Chi e' in ritardo lo sa gia'; scrivergli ogni ora fa finire la
   posta nella cartella dello spam, e da li' non esce piu';
3. **un guasto su una concessionaria non ferma le altre.** Si annota e si
   va avanti: se la posta di una e' sbagliata, le altre devono ricevere
   lo stesso la loro nota.

L'ora e' quella d'Italia, fissata dal server. `giro()` prende `adesso` come
argomento apposta: e' cosi' che il banco puo' far finta che sia sabato, o
che sia passato un mese, senza aspettare.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import conteggio, conti, fatture, posta, pratiche

# Ogni quanto si torna a sollecitare la stessa concessionaria.
PASSO = 3 * 86400
# Il sabato, e da che ora in poi si chiude la settimana.
SABATO = 5
ORA = 7


class Registro:
    """Quel che l'orologio ha gia' fatto, su file."""

    def __init__(self, cartella: Path):
        self.percorso = Path(cartella) / "orologio.json"

    def leggi(self) -> Dict[str, Any]:
        try:
            dentro = json.loads(self.percorso.read_text(encoding="utf-8"))
            return dentro if isinstance(dentro, dict) else {}
        except (OSError, ValueError):
            return {}

    def scrivi(self, roba: Dict[str, Any]) -> None:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        provvisorio = self.percorso.with_suffix(".nuovo")
        provvisorio.write_text(json.dumps(roba, ensure_ascii=False),
                               encoding="utf-8")
        os.chmod(provvisorio, 0o600)
        provvisorio.replace(self.percorso)


def _testo_nota(nome: str, nota: Dict[str, Any],
                fattura: Optional[Dict[str, Any]]) -> str:
    righe = ["%s," % (nome or "buongiorno"), "",
             "in allegato la nota di saldo della settimana %s, di %s."
             % (nota.get("settimana", ""),
                conteggio._soldi(nota.get("totale", 0)))]
    if fattura:
        righe.append("Trovi anche la fattura n. %s, di %s."
                     % (fattura.get("numero", ""),
                        conteggio._soldi(fattura.get("conti", {})
                                         .get("totale", 0))))
    righe += ["", "Da saldare entro lunedì %s." % nota.get("scadenza", ""),
              "Il saldo libera il plafond per le pratiche della settimana "
              "nuova.", ""]
    return "\n".join(righe)


def _testo_sollecito(nome: str, aperte: List[Dict[str, Any]],
                     totale: float) -> str:
    quante = len(aperte)
    return "\n".join([
        "%s," % (nome or "buongiorno"), "",
        "risulta%s %d not%s non ancora saldat%s, per %s in tutto."
        % ("no" if quante != 1 else "", quante,
           "e" if quante != 1 else "a", "e" if quante != 1 else "a",
           conteggio._soldi(totale)),
        "In allegato l'estratto conto con le scadenze.", "",
        "Finché resta aperto, il plafond non si libera e le pratiche nuove "
        "si fermano.", ""])


def giro(cartella_dati: Path, cartella_pratiche: Path, cartella_note: Path,
         cartella_fatture: Path, adesso: Optional[float] = None,
         spedizioniere: Optional[Callable] = None) -> Dict[str, Any]:
    """Un giro dell'orologio. Torna quel che ha fatto, per il registro.

    Si puo' chiamare quante volte si vuole: quel che e' gia' stato fatto
    non si rifa'.
    """
    adesso = adesso or time.time()
    quando = time.localtime(adesso)
    registro = Registro(cartella_dati)
    memoria = registro.leggi()
    fatto: Dict[str, Any] = {"note": [], "fatture": [], "solleciti": [],
                             "guasti": []}

    tutte = conti.concessionarie(cartella_dati)

    # ---- il sabato: si chiude la settimana
    questa = conteggio.settimana(adesso)
    if quando.tm_wday == SABATO and quando.tm_hour >= ORA \
            and memoria.get("settimana_chiusa") != questa:
        for quale, dentro in sorted(tutte.items()):
            try:
                finite = pratiche.elenco(cartella_pratiche, quale, "finita")
                if not finite:
                    continue
                nota = conteggio.emetti(cartella_note, cartella_pratiche,
                                        quale, dentro.get("nome", quale),
                                        adesso=adesso)
                fatto["note"].append(nota["id"])
                fattura = None
                try:
                    fattura = fatture.emetti(
                        cartella_fatture, cartella_dati, nota,
                        {"nome": dentro.get("nome", quale),
                         "piva": dentro.get("piva", "")},
                        nota.get("scadenza", ""))
                    fatto["fatture"].append(fattura["numero"])
                except fatture.FatturaRifiutata as e:
                    # La nota parte lo stesso: il credito esiste anche se il
                    # documento fiscale non si puo' ancora fare.
                    fatto["guasti"].append("%s: fattura non emessa — %s"
                                           % (quale, e.utente))
                allegati = [("nota-%s.pdf" % nota["settimana"],
                             conteggio.carta(cartella_note, nota["id"]))]
                if fattura:
                    allegati.append(
                        ("fattura-%s.pdf" % fattura["numero"].replace("/", "-"),
                         fatture.carta(cartella_fatture, fattura["id"])))
                posta.manda(dentro.get("posta", ""),
                            "Nota di saldo — settimana %s" % nota["settimana"],
                            _testo_nota(dentro.get("nome", ""), nota, fattura),
                            allegati=allegati, spedizioniere=spedizioniere)
            except (conteggio.ConteggioRifiutato, posta.PostaRifiutata) as e:
                # Un guasto su una non ferma le altre.
                fatto["guasti"].append("%s: %s" % (quale, getattr(e, "utente", e)))
        memoria["settimana_chiusa"] = questa

    # ---- ogni giorno: chi e' in ritardo
    solleciti = memoria.get("solleciti") or {}
    for quale, dentro in sorted(tutte.items()):
        aperte = conteggio.scadute(cartella_note, quale, adesso)
        if not aperte:
            # Chi ha saldato riparte pulito: se domani ritarda di nuovo, il
            # primo sollecito non deve aspettare il passo del precedente.
            solleciti.pop(quale, None)
            continue
        if adesso - float(solleciti.get(quale, 0)) < PASSO:
            continue
        totale = sum(float(n.get("totale") or 0) for n in aperte)
        try:
            posta.manda(
                dentro.get("posta", ""),
                "Sollecito — %s da saldare" % conteggio._soldi(totale),
                _testo_sollecito(dentro.get("nome", ""), aperte, totale),
                allegati=[("estratto-conto.pdf",
                           conteggio.estratto(quale, dentro.get("nome", ""),
                                              conteggio.da_saldare(
                                                  cartella_note, quale),
                                              adesso))],
                spedizioniere=spedizioniere)
            solleciti[quale] = adesso
            fatto["solleciti"].append(quale)
        except posta.PostaRifiutata as e:
            fatto["guasti"].append("%s: sollecito non partito — %s"
                                   % (quale, e.utente))
    memoria["solleciti"] = solleciti
    memoria["ultimo_giro"] = int(adesso)
    registro.scrivi(memoria)
    return fatto
