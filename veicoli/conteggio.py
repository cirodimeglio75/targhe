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
from . import pdf
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
            "posta": dentro.get("posta", ""),
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


# --------------------------------------------------------- il foglio in PDF

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato",
          "domenica")


def _lunedi_dopo(quando: float) -> int:
    """Il momento in cui scade: lunedi' dopo l'emissione, a fine giornata."""
    giorno = time.localtime(quando)
    quanti = (7 - giorno.tm_wday) or 7
    lunedi = time.localtime(quando + quanti * 86400)
    return int(time.mktime((lunedi.tm_year, lunedi.tm_mon, lunedi.tm_mday,
                            23, 59, 59, 0, 0, -1)))


def entro_quando(quando: float) -> str:
    """Il lunedi' entro cui si salda, scritto per esteso.

    Il proprietario: «la concessionaria dovra' saldare entro il lunedi'».
    Il lunedi' e' quello che viene dopo l'emissione — anche se la nota
    esce di lunedi', si intende il successivo: nessuno paga il giorno
    stesso in cui riceve il conto.
    """
    giorno = time.localtime(quando)
    quanti = (7 - giorno.tm_wday) or 7
    return time.strftime("%d/%m/%Y", time.localtime(quando + quanti * 86400))


def _soldi(quanto: float) -> str:
    """«1234.5» diventa «1.234,50 €», come si scrive in italiano."""
    scritto = "{:,.2f}".format(float(quanto or 0))
    return scritto.replace(",", "@").replace(".", ",").replace("@", ".") + " €"


def foglio(nota: Dict[str, Any], nome_concessionaria: str = "") -> bytes:
    """La nota di saldo come documento: un foglio A4 che si stampa.

    Sta qui e non nelle pagine perche' non e' una schermata: e' la carta
    che la concessionaria mette in contabilita', e deve dire da sola tutto
    quel che serve — chi, quando, cosa, quanto, entro quando.
    """
    pezzi = [
        pdf.testo(60, 780, "Nota di saldo", 22, True),
        pdf.testo(60, 758, "Settimana %s" % nota.get("settimana", ""), 11),
        pdf.riga(60, 748, 535, 748),
        pdf.testo(60, 726, nome_concessionaria or nota.get("concessionaria", ""),
                  13, True),
        pdf.testo(60, 710, "Emessa il %s"
                  % time.strftime("%d/%m/%Y",
                                  time.localtime(nota.get("quando", 0))), 10),
        pdf.testo(60, 674, "Pratica", 10, True),
        pdf.testo(200, 674, "Targa", 10, True),
        pdf.testo(430, 674, "Importo", 10, True),
        pdf.riga(60, 666, 535, 666),
    ]
    y = 648
    for voce in nota.get("righe", []):
        nome_tipo = pr.TIPI.get(voce.get("tipo", ""), {}).get(
            "nome", voce.get("tipo", ""))
        pezzi.append(pdf.testo(60, y, nome_tipo[:34], 10))
        pezzi.append(pdf.testo(200, y, voce.get("targa", ""), 10))
        pezzi.append(pdf.testo(430, y, _soldi(voce.get("prezzo", 0)), 10))
        y -= 20
        if y < 140:
            # Oltre il foglio non si scrive: meglio una nota che dice «e
            # altre N» di righe stampate una sopra l'altra.
            restano = len(nota.get("righe", [])) - ((648 - y) // 20)
            if restano > 0:
                pezzi.append(pdf.testo(60, y, "e altre %d pratiche" % restano,
                                       10))
            break
    pezzi.append(pdf.riga(60, y + 8, 535, y + 8))
    pezzi.append(pdf.testo(330, y - 14, "Totale", 13, True))
    pezzi.append(pdf.testo(430, y - 14, _soldi(nota.get("totale", 0)), 13, True))
    pezzi.append(pdf.testo(60, 96, "Da saldare entro lunedì %s."
                           % entro_quando(nota.get("quando", time.time())), 11))
    pezzi.append(pdf.testo(60, 78, "Il saldo libera il plafond per le "
                                   "pratiche della settimana nuova.", 9))
    return pdf.fabbrica([pezzi], "Nota di saldo %s" % nota.get("settimana", ""))


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
           concessionaria: str, nome: str = "",
           adesso: Optional[float] = None) -> Dict[str, Any]:
    """La nota di saldo per una concessionaria: le pratiche finite e il totale.

    Si prendono le pratiche **finite** e non ancora saldate. Quelle ancora
    aperte non entrano: si paga il lavoro fatto, non quello in corso.
    """
    # Solo le pratiche finite che non sono GIA' in una nota: una nota
    # emessa e non ancora pagata lascia la pratica «finita», ed e' giusto
    # (il plafond resta occupato finche' non si salda), ma rimetterla nella
    # nota della settimana dopo vorrebbe dire fatturarla due volte.
    righe = [p for p in pr.elenco(cartella_pratiche, concessionaria, "finita")
             if not p.get("nota")]
    if not righe:
        raise ConteggioRifiutato(
            "Non c'è niente da conteggiare per questa concessionaria.")
    identificativo = "%s-%s-%s" % (settimana(adesso or time.time()),
                                   concessionaria, secrets.token_hex(3))
    # L'ora la porta chi chiama: l'orologio sa quando sta girando, e la
    # settimana scritta sulla nota dev'essere QUELLA, non quella
    # dell'istante in cui il file viene scritto.
    adesso = int(adesso or time.time())
    nota = {"id": identificativo, "concessionaria": concessionaria,
            "settimana": settimana(adesso), "quando": adesso,
            # La scadenza si CONSERVA, non si ricalcola: quella scritta sul
            # PDF che il cliente ha in mano e' questa, e deve restare
            # questa anche se un giorno cambiasse la regola del lunedi'.
            "scadenza": entro_quando(adesso),
            "scade_il": _lunedi_dopo(adesso),
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
    # Il PDF si fabbrica UNA volta, quando la nota nasce, e non si rifa'
    # piu': rigenerarlo a ogni richiesta vorrebbe dire che una modifica al
    # programma cambia una carta gia' mandata a un cliente.
    carta = percorso.with_suffix(".pdf")
    carta.write_bytes(foglio(nota, nome or concessionaria))
    os.chmod(carta, 0o600)
    # Adesso che la nota esiste, le pratiche ci sono dentro e non tornano
    # in quella della settimana prossima.
    for voce in nota["righe"]:
        try:
            pr.segna_in_nota(cartella_pratiche, voce["pratica"],
                             identificativo)
        except pr.PraticaRifiutata:
            continue
    return nota


def carta(cartella_note: Path, identificativo: str) -> bytes:
    """Il PDF di una nota gia' emessa."""
    percorso = _dove(cartella_note, identificativo).with_suffix(".pdf")
    try:
        return percorso.read_bytes()
    except OSError:
        raise ConteggioRifiutato("Il PDF di questa nota non c'è.")


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


def scadute(cartella_note: Path, concessionaria: str = "",
            adesso: Optional[float] = None) -> List[Dict[str, Any]]:
    """Le note non saldate il cui lunedi' e' passato."""
    adesso = adesso or time.time()
    return [n for n in note(cartella_note, concessionaria)
            if not n.get("saldata") and n.get("scade_il", 0) < adesso]


def da_saldare(cartella_note: Path,
               concessionaria: str = "") -> List[Dict[str, Any]]:
    return [n for n in note(cartella_note, concessionaria)
            if not n.get("saldata")]


def estratto(concessionaria: str, nome: str, aperte: List[Dict[str, Any]],
             adesso: Optional[float] = None) -> bytes:
    """L'estratto conto: tutto quel che resta da pagare, su un foglio.

    E' l'allegato del sollecito. Non ripete le pratiche una per una: chi
    riceve un sollecito vuole sapere **quanto** deve e **da quando**, e le
    righe le ha gia' sulle note.
    """
    adesso = adesso or time.time()
    pezzi = [
        pdf.testo(60, 780, "Estratto conto", 22, True),
        pdf.testo(60, 758, "Al %s"
                  % time.strftime("%d/%m/%Y", time.localtime(adesso)), 11),
        pdf.riga(60, 748, 535, 748),
        pdf.testo(60, 726, nome or concessionaria, 13, True),
        pdf.testo(60, 690, "Nota", 10, True),
        pdf.testo(200, 690, "Scadenza", 10, True),
        pdf.testo(330, 690, "Stato", 10, True),
        pdf.testo(440, 690, "Importo", 10, True),
        pdf.riga(60, 682, 535, 682),
    ]
    y = 664
    totale = 0.0
    for nota in aperte:
        scaduta = nota.get("scade_il", 0) < adesso
        totale += float(nota.get("totale") or 0)
        pezzi += [pdf.testo(60, y, "Settimana %s" % nota.get("settimana", ""), 10),
                  pdf.testo(200, y, nota.get("scadenza", ""), 10),
                  pdf.testo(330, y, "SCADUTA" if scaduta else "da saldare",
                            10, scaduta),
                  pdf.testo(440, y, _soldi(nota.get("totale", 0)), 10)]
        y -= 19
        if y < 180:
            break
    pezzi.append(pdf.riga(60, y + 8, 535, y + 8))
    pezzi.append(pdf.testo(330, y - 14, "Totale dovuto", 13, True))
    pezzi.append(pdf.testo(440, y - 14, _soldi(totale), 13, True))
    pezzi.append(pdf.testo(60, 96, "Il saldo libera il plafond: finché "
                                   "resta aperto, le pratiche nuove si "
                                   "fermano.", 10))
    return pdf.fabbrica([pezzi], "Estratto conto %s" % concessionaria)
