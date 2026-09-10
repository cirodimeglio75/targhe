"""La pagina: una targa da scrivere, e la scheda che ne esce.

Regola d'oro presa da Ops!: **stessa faccia su web e nativo**. Questa
pagina e' la verita' di come sono fatte le schede; le schermate Android e
iPhone, quando ci saranno, chiedono le stesse rotte con
`Accept: application/json` e mostrano le stesse righe nello stesso ordine.
Un'API parallela sarebbe una seconda verita' da tenere allineata.

Due cose che qui dentro non si negoziano:

- **tutto quel che arriva dal fornitore passa da `html.escape`.** E' testo
  di terzi che finisce in una pagina: e' la definizione del buco piu'
  vecchio del web, e non c'e' nessun motivo per fidarsi di un campo
  «marca» piu' che di un modulo compilato da uno sconosciuto.
- **le righe vuote non si mostrano.** Un fornitore che non manda la massa
  non deve produrre una riga «Massa: —»: una scheda mezza vuota sembra un
  guasto nostro, mentre una scheda corta sembra semplicemente corta.
"""

import re
from typing import Any, Dict, List, Optional

from .telaio import _e, numero, telaio

MESI = ("gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic")

def data(valore: Any) -> str:
    """«2005-06-28» diventa «28 giu 2005». Chi legge e' italiano.

    Quel che non ha la forma di una data si lascia com'e': meglio mostrare
    la stringa del fornitore che inventarne una sbagliata."""
    testo = str(valore or "").strip()
    pezzi = re.match(r"^(\d{4})-(\d{2})-(\d{2})", testo)
    if not pezzi:
        return testo
    anno, mese, giorno = pezzi.groups()
    numero = int(mese)
    if not 1 <= numero <= 12:
        return testo
    return "%d %s %s" % (int(giorno), MESI[numero - 1], anno)


def _cerca(targa: str = "") -> str:
    return ("<form action=/cerca method=get>"
            "<label class=targa>"
            "<span class=banda>I<span>ITA</span></span>"
            "<input name=targa value='%s' placeholder='AB123CD' "
            "autocapitalize=characters autocomplete=off spellcheck=false "
            "autofocus></label>"
            "<button>Cerca</button></form>" % _e(targa))


def ricerca(messaggio: str = "", targa: str = "",
            conto: Dict[str, Any] = None) -> str:
    """La pagina d'ingresso. `messaggio` e' il perche', quando c'e'."""
    dentro = ["<h1>Cerca una targa</h1>",
              "<p class=sottotitolo>Dati del veicolo, assicurazione, prezzo "
              "del passaggio — e da qui si comincia una pratica.</p>",
              _cerca(targa)]
    if messaggio:
        dentro.insert(2, "<div class='avviso male'>%s</div>" % _e(messaggio))
    return telaio("Cerca una targa", "".join(dentro), conto, "/cerca")


def _righe(voci: List[tuple]) -> str:
    """Le righe che hanno un valore. Le altre non esistono."""
    fuori = []
    for che, quanto in voci:
        if quanto in (None, "", "None"):
            continue
        fuori.append("<div class=riga><span class=che>%s</span>"
                     "<span class=quanto>%s</span></div>"
                     % (_e(che), _e(quanto)))
    return "".join(fuori)


def _blocco(titolo: str, voci: List[tuple]) -> str:
    righe = _righe(voci)
    if not righe:
        return ""
    return ("<div class=carta><p class=gruppo>%s</p>%s</div>"
            % (_e(titolo), righe))


# Le pratiche che sappiamo fare, come le chiama una persona. Manca il
# passaggio fra due privati, che e' il caso piu' comune: i documenti che
# vuole non sono sul foglio dell'agenzia, e non si indovinano — vanno
# chiesti, e allora si aggiunge una riga qui.
PRATICHE = (("mini", "Mini passaggio"),
            ("societa-persona", "Da società a privato"),
            ("perdita", "Perdita di possesso"),
            ("immatricolazione", "Immatricolazione"))


def _pratiche(targa: str) -> str:
    """I collegamenti per cominciare una pratica su questa targa."""
    voci = ["<a href='/pratica/nuova?tipo=%s&targa=%s'>%s</a>"
            % (_e(chiave), _e(targa), _e(nome)) for chiave, nome in PRATICHE]
    return ("<p class=nota-riga>Vuoi farla con noi? %s</p>"
            % " · ".join(voci))


def scheda(d: Dict[str, Any], conto: Dict[str, Any] = None) -> str:
    """La scheda di un veicolo, dai nomi che torna `veicoli.scheda`."""
    nome = " ".join(str(x) for x in (d.get("marca"), d.get("modello")) if x)
    fuori = [_cerca(d.get("targa", "")),
             "<div class=carta>",
             "<p class=titolone>%s</p>" % (_e(nome) or "Veicolo"),
             "<p class=sotto>%s%s</p>" % (
                 _e(d.get("allestimento") or ""),
                 (" · " if d.get("allestimento") else "") + _e(d.get("targa", ""))),
             "</div>"]

    # Di immatricolazione il fornitore manda solo l'ANNO: la riga si chiama
    # «Anno» e non «Data» apposta — chiamarla «Data» prometterebbe un
    # giorno che non abbiamo.
    fuori.append(_blocco("Immatricolazione", [
        ("Anno", d.get("anno")),
        ("Telaio", d.get("telaio")),
        ("Porte", d.get("porte")),
    ]))
    fuori.append(_blocco("Motore", [
        ("Alimentazione", d.get("alimentazione")),
        ("Cilindrata", numero(d.get("cilindrata"), "cc")),
        ("Potenza", numero(d.get("kw"), "kW")),
        ("Cavalli", numero(d.get("cavalli"), "cv")),
        ("Cavalli fiscali", d.get("fiscali")),
        ("Massa", numero(d.get("massa"), "kg")),
    ]))

    ass = d.get("assicurazione") or {}
    if ass.get("errore"):
        # Meta' schermata e' meglio di una schermata di errore su un dato
        # che abbiamo gia' pagato: si dice cosa manca, e il resto resta.
        fuori.append("<div class=carta><p class=gruppo>Assicurazione</p>"
                     "<div class=riga><span class=che>%s</span></div></div>"
                     % _e(ass["errore"]))
    else:
        stato = ass.get("assicurato")
        fuori.append(_blocco("Assicurazione", [
            ("Copertura", "Risulta assicurato" if stato is True
             else ("Non risulta assicurato" if stato is False else None)),
            ("Compagnia", ass.get("compagnia")),
            ("Scadenza", data(ass.get("scadenza_polizza"))),
        ]))

    neo = d.get("neopatentati") or {}
    if neo.get("perche"):
        segno = {True: "<span class=si>SI'</span>",
                 False: "<span class=no>NO</span>"}.get(neo.get("si_puo"),
                                                        "<span>?</span>")
        # Quando manca solo la massa, la si chiede a chi guarda invece di
        # arrendersi: sta sul libretto, e con quella la risposta si chiude.
        # Il numero resta di chi lo scrive — viaggia nell'indirizzo e
        # nient'altro, non si salva accanto alla targa.
        chiedila = ("<form action=/cerca method=get class=massa>"
                    "<input type=hidden name=targa value='%s'>"
                    "<input name=massa inputmode=numeric placeholder='kg'>"
                    "<button>Calcola</button></form>"
                    % _e(d.get("targa", ""))) if neo.get("serve_massa") else ""
        fuori.append("<div class=carta><p class=gruppo>Neopatentati</p>"
                     "<div class=riga><span class=che>Primo anno di patente B"
                     "</span><span class=quanto>%s</span></div>"
                     "<div class=riga><span class=che>%s</span></div>%s%s</div>"
                     % (segno, _e(neo["perche"]), chiedila,
                        _righe([("kW per tonnellata",
                                 numero(neo.get("kw_per_tonnellata"))),
                                ("Patente necessaria", d.get("patente"))])))

    pass_ = d.get("passaggio") or {}
    if pass_.get("euro"):
        fuori.append("<div class=carta><p class=gruppo>Passaggio di "
                     "proprietà</p>"
                     "<div class=riga><span class=che>Prezzo</span>"
                     "<span class=quanto>%s €</span></div>"
                     "<div class=riga><span class=che>%s</span></div>"
                     "%s</div>"
                     % (_e(numero(pass_["euro"])), _e(pass_.get("perche", "")),
                        _pratiche(d.get("targa", ""))))
    elif pass_.get("perche"):
        # Senza numero si dice il perche' e basta: un prezzo inventato in
        # una schermata e' una promessa che poi qualcuno deve mantenere
        # allo sportello.
        fuori.append("<div class=carta><p class=gruppo>Passaggio di "
                     "proprietà</p><div class=riga><span class=che>%s</span>"
                     "</div></div>" % _e(pass_["perche"]))

    fuori.append("<p class=nota><a href='/area'>Torna alle tue pratiche</a>"
                 "</p>")

    if d.get("dalla_memoria"):
        # Detto, non nascosto: chi guarda deve sapere che sta leggendo una
        # risposta di ieri, e come si chiede quella di oggi.
        fuori.append("<p class=nota>Dati già in memoria, non richiesti "
                     "adesso al fornitore. Per rifare la domanda: "
                     "<a href='/cerca?targa=%s&fresco=1'>chiedi di nuovo</a>.</p>"
                     % _e(d.get("targa", "")))
    return telaio("%s — Targhe" % (nome or d.get("targa", "")),
                  "".join(fuori), conto, "/cerca")
