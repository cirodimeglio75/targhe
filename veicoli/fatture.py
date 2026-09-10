"""Le fatture: numerazione, importi, e il foglio da mandare.

**Da leggere prima di fidarsi di questo file.** Una fattura e' un documento
fiscale, non una schermata: sbagliarla costa a chi la emette, non a chi la
scrive. Qui c'e' la macchina — numerazione, importi, PDF, archivio — ma
due cose le deve dire una persona, e finche' non le dice il programma si
rifiuta di emettere:

1. **i dati fiscali di chi emette** (ragione sociale, partita IVA,
   indirizzo): stanno in `fisco.json`, si mettono dall'amministrazione, e
   senza non si emette niente;
2. **come si divide l'importo.** Un passaggio di proprieta' non e' tutto
   imponibile: la parte che si paga allo Stato (IPT, emolumenti, imposta di
   bollo) e' un'**anticipazione in nome e per conto** ai sensi dell'art. 15
   del DPR 633/72 e resta **fuori campo IVA**; l'IVA si applica al
   **compenso** dell'agenzia. Quanto sia il compenso lo sa il
   commercialista, non io: si scrive per ogni tipo di pratica, e finche'
   vale zero il programma lo dice e non emette una fattura senza IVA che
   sarebbe sbagliata.

E una terza cosa che questo file **non** fa: la **fattura elettronica**.
In Italia una fattura fra partite IVA passa dal Sistema di Interscambio, in
XML, con la firma e il codice destinatario. Questo PDF e' la fattura come
la legge una persona; per mandarla allo SdI serve un canale — e Openapi,
che e' gia' il nostro fornitore, ne ha uno. E' un pezzo a parte, dichiarato
e non nascosto.

## La numerazione

Progressiva per anno, senza buchi e senza doppioni: e' la cosa che un
controllo guarda per prima. Il contatore sta su un file, si alza sotto
chiave, e un numero preso non si restituisce — se l'emissione fallisce
dopo, resta un numero saltato, che e' un problema piccolo; due fatture con
lo stesso numero e' un problema grosso.
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import pdf
from . import pratiche as pr

# Un lucchetto solo per tutto il programma: il numero di fattura si alza
# uno alla volta, anche se due richieste arrivano nello stesso istante.
_LUCCHETTO = threading.Lock()

IVA_PREDEFINITA = 22.0


class FatturaRifiutata(Exception):
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


# ------------------------------------------------------- i dati di chi emette

def fisco(cartella: Path) -> Dict[str, Any]:
    return _leggi(Path(cartella) / "fisco.json")


def salva_fisco(cartella: Path, dati: Dict[str, Any]) -> Dict[str, Any]:
    dentro = fisco(cartella)
    for chiave in ("ragione_sociale", "piva", "codice_fiscale", "indirizzo",
                   "cap", "citta", "provincia", "iban"):
        if str(dati.get(chiave, "")).strip():
            dentro[chiave] = str(dati[chiave]).strip()
    if str(dati.get("iva", "")).strip():
        dentro["iva"] = float(str(dati["iva"]).replace(",", "."))
    # I compensi per tipo di pratica: quanto, dell'importo, e' compenso
    # dell'agenzia (imponibile). Il resto e' anticipazione, fuori campo.
    compensi = dentro.get("compensi") or {}
    for tipo in pr.TIPI:
        campo = "compenso_" + tipo
        if str(dati.get(campo, "")).strip():
            compensi[tipo] = float(str(dati[campo]).replace(",", "."))
    dentro["compensi"] = compensi
    _scrivi(Path(cartella) / "fisco.json", dentro)
    return dentro


def pronto(cartella: Path) -> str:
    """Stringa vuota se si puo' emettere; se no, il perche', da mostrare."""
    dentro = fisco(cartella)
    manca = [nome for chiave, nome in (
        ("ragione_sociale", "la ragione sociale"), ("piva", "la partita IVA"),
        ("indirizzo", "l'indirizzo"), ("citta", "la città"))
        if not str(dentro.get(chiave, "")).strip()]
    if manca:
        return ("Per emettere fatture mancano %s: si mettono "
                "dall'amministrazione." % ", ".join(manca))
    if not any(float(v or 0) > 0 for v in (dentro.get("compensi") or {}).values()):
        return ("Nessun compenso impostato: senza, la fattura uscirebbe "
                "tutta fuori campo IVA. Va deciso col commercialista quanto "
                "dell'importo è compenso dell'agenzia.")
    return ""


# ------------------------------------------------------------ la numerazione

def _prossimo_numero(cartella: Path, anno: str) -> int:
    percorso = Path(cartella) / "numerazione.json"
    with _LUCCHETTO:
        dentro = _leggi(percorso)
        numero = int(dentro.get(anno, 0)) + 1
        dentro[anno] = numero
        _scrivi(percorso, dentro)
    return numero


# --------------------------------------------------------------- gli importi

def conti_della_nota(nota: Dict[str, Any],
                     compensi: Dict[str, Any],
                     aliquota: float) -> Dict[str, Any]:
    """Come si divide il totale di una nota, riga per riga.

    Per ogni pratica: il compenso e' imponibile e ci si applica l'IVA; quel
    che resta e' anticipazione in nome e per conto, fuori campo. La somma
    dei due piu' l'IVA e' quel che la concessionaria paga davvero — e non
    e' il totale della nota, perche' l'IVA sul compenso si aggiunge.
    """
    imponibile = 0.0
    anticipazioni = 0.0
    righe = []
    for voce in nota.get("righe", []):
        prezzo = float(voce.get("prezzo") or 0)
        compenso = min(float((compensi or {}).get(voce.get("tipo", ""), 0) or 0),
                       prezzo)
        anticipo = round(prezzo - compenso, 2)
        imponibile += compenso
        anticipazioni += anticipo
        righe.append({"targa": voce.get("targa", ""),
                      "tipo": voce.get("tipo", ""),
                      "compenso": round(compenso, 2),
                      "anticipazione": anticipo,
                      "prezzo": prezzo})
    imponibile = round(imponibile, 2)
    anticipazioni = round(anticipazioni, 2)
    iva = round(imponibile * float(aliquota) / 100.0, 2)
    return {"righe": righe, "imponibile": imponibile,
            "anticipazioni": anticipazioni, "aliquota": float(aliquota),
            "iva": iva, "totale": round(imponibile + iva + anticipazioni, 2)}


def _soldi(quanto: float) -> str:
    scritto = "{:,.2f}".format(float(quanto or 0))
    return scritto.replace(",", "@").replace(".", ",").replace("@", ".") + " €"


def foglio(fattura: Dict[str, Any]) -> bytes:
    """La fattura come la legge una persona."""
    chi = fattura.get("emittente", {})
    a = fattura.get("cliente", {})
    conti = fattura.get("conti", {})
    pezzi = [
        pdf.testo(60, 786, chi.get("ragione_sociale", ""), 14, True),
        pdf.testo(60, 770, "%s %s %s %s" % (chi.get("indirizzo", ""),
                                            chi.get("cap", ""),
                                            chi.get("citta", ""),
                                            chi.get("provincia", "")), 9),
        pdf.testo(60, 758, "P. IVA %s" % chi.get("piva", ""), 9),
        pdf.testo(60, 716, "Fattura n. %s del %s"
                  % (fattura.get("numero", ""),
                     time.strftime("%d/%m/%Y",
                                   time.localtime(fattura.get("quando", 0)))),
                  18, True),
        pdf.riga(60, 706, 535, 706),
        pdf.testo(60, 682, "Spett.le", 9),
        pdf.testo(60, 668, a.get("nome", ""), 12, True),
        pdf.testo(60, 654, ("P. IVA %s" % a.get("piva", "")) if a.get("piva")
                  else "partita IVA da inserire", 9),
        pdf.testo(60, 614, "Pratica", 10, True),
        pdf.testo(200, 614, "Targa", 10, True),
        pdf.testo(330, 614, "Compenso", 10, True),
        pdf.testo(440, 614, "Anticipazioni", 10, True),
        pdf.riga(60, 606, 535, 606),
    ]
    y = 590
    for voce in conti.get("righe", []):
        nome_tipo = pr.TIPI.get(voce.get("tipo", ""), {}).get(
            "nome", voce.get("tipo", ""))
        pezzi += [pdf.testo(60, y, nome_tipo[:30], 9),
                  pdf.testo(200, y, voce.get("targa", ""), 9),
                  pdf.testo(330, y, _soldi(voce.get("compenso", 0)), 9),
                  pdf.testo(440, y, _soldi(voce.get("anticipazione", 0)), 9)]
        y -= 17
        if y < 230:
            pezzi.append(pdf.testo(60, y, "…", 9))
            break
    pezzi.append(pdf.riga(60, y + 6, 535, y + 6))
    y -= 8
    for nome, valore, grassetto in (
            ("Imponibile", conti.get("imponibile", 0), False),
            ("IVA %g%%" % conti.get("aliquota", 0), conti.get("iva", 0), False),
            # La dicitura per esteso sta in fondo al foglio: qui dentro
            # finiva sopra l'importo, e una fattura con due numeri
            # sovrapposti non la si manda a nessuno.
            ("Anticipazioni art. 15", conti.get("anticipazioni", 0), False),
            ("Totale documento", conti.get("totale", 0), True)):
        pezzi.append(pdf.testo(230, y, nome, 10, grassetto))
        pezzi.append(pdf.testo(460, y, _soldi(valore), 10, grassetto))
        y -= 18
    pezzi.append(pdf.testo(60, 120, "Da saldare entro %s."
                           % fattura.get("scadenza", ""), 11))
    if chi.get("iban"):
        pezzi.append(pdf.testo(60, 104, "IBAN %s" % chi["iban"], 9))
    pezzi.append(pdf.testo(60, 78, "Le anticipazioni in nome e per conto "
                                   "sono escluse da IVA ai sensi dell'art. "
                                   "15 DPR 633/72.", 8))
    return pdf.fabbrica([pezzi], "Fattura %s" % fattura.get("numero", ""))


# ---------------------------------------------------------------- l'emissione

def emetti(cartella_fatture: Path, cartella_dati: Path, nota: Dict[str, Any],
           cliente: Dict[str, Any], scadenza: str = "") -> Dict[str, Any]:
    """La fattura di una nota di saldo. Una nota, una fattura, e non due."""
    guasto = pronto(cartella_dati)
    if guasto:
        raise FatturaRifiutata(guasto)
    gia = per_nota(cartella_fatture, nota.get("id", ""))
    if gia:
        # Una nota non si fattura due volte: il numero e' gia' stato speso,
        # e due documenti per lo stesso credito sono un guaio contabile.
        return gia
    dentro = fisco(cartella_dati)
    anno = time.strftime("%Y")
    numero = _prossimo_numero(cartella_fatture, anno)
    conti = conti_della_nota(nota, dentro.get("compensi") or {},
                             dentro.get("iva", IVA_PREDEFINITA))
    fattura = {"id": "%s-%04d" % (anno, numero),
               "numero": "%d/%s" % (numero, anno),
               "anno": anno, "progressivo": numero,
               "nota": nota.get("id", ""),
               "concessionaria": nota.get("concessionaria", ""),
               "quando": int(time.time()), "scadenza": scadenza,
               "emittente": dentro, "cliente": cliente, "conti": conti,
               "pagata": False}
    percorso = Path(cartella_fatture) / (fattura["id"] + ".json")
    _scrivi(percorso, fattura)
    carta = percorso.with_suffix(".pdf")
    carta.write_bytes(foglio(fattura))
    os.chmod(carta, 0o600)
    return fattura


def leggi(cartella_fatture: Path, identificativo: str) -> Dict[str, Any]:
    if not identificativo or not all(c.isalnum() or c in "-_"
                                     for c in identificativo):
        raise FatturaRifiutata("Questa fattura non esiste.")
    dentro = _leggi(Path(cartella_fatture) / (identificativo + ".json"))
    if not dentro:
        raise FatturaRifiutata("Questa fattura non esiste.")
    return dentro


def carta(cartella_fatture: Path, identificativo: str) -> bytes:
    leggi(cartella_fatture, identificativo)      # controlla il nome
    try:
        return (Path(cartella_fatture) / (identificativo + ".pdf")).read_bytes()
    except OSError:
        raise FatturaRifiutata("Il PDF di questa fattura non c'è.")


def elenco(cartella_fatture: Path,
           concessionaria: str = "") -> List[Dict[str, Any]]:
    fuori = []
    for percorso in sorted(Path(cartella_fatture).glob("*.json")):
        if percorso.name == "numerazione.json":
            continue
        dentro = _leggi(percorso)
        if not dentro:
            continue
        if concessionaria and dentro.get("concessionaria") != concessionaria:
            continue
        fuori.append(dentro)
    return sorted(fuori, key=lambda f: f.get("quando", 0), reverse=True)


def per_nota(cartella_fatture: Path,
             nota: str) -> Optional[Dict[str, Any]]:
    for fattura in elenco(cartella_fatture):
        if fattura.get("nota") == nota:
            return fattura
    return None


def segna_pagata(cartella_fatture: Path, identificativo: str) -> Dict[str, Any]:
    fattura = leggi(cartella_fatture, identificativo)
    fattura["pagata"] = True
    fattura["pagata_il"] = int(time.time())
    _scrivi(Path(cartella_fatture) / (identificativo + ".json"), fattura)
    return fattura
