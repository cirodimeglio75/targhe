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

import html
import re
from typing import Any, Dict, List, Optional

MESI = ("gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic")

STILE = """
:root { color-scheme: light dark;
  --fondo:#f4f5f7; --carta:#fff; --inchiostro:#16181d; --tenue:#6b7280;
  --riga:#e5e7eb; --blu:#1d4ed8; --verde:#15803d; --rosso:#b91c1c; }
@media (prefers-color-scheme: dark) { :root {
  --fondo:#0f1115; --carta:#181b21; --inchiostro:#e9eaee; --tenue:#9aa1ad;
  --riga:#2a2e37; --blu:#60a5fa; --verde:#4ade80; --rosso:#f87171; } }
* { box-sizing:border-box }
body { margin:0; padding:24px 16px 64px; background:var(--fondo);
  color:var(--inchiostro); font:16px/1.5 -apple-system,BlinkMacSystemFont,
  "Segoe UI",Roboto,sans-serif; }
.dentro { max-width:640px; margin:0 auto }
h1 { font-size:22px; margin:0 0 4px }
.sottotitolo { color:var(--tenue); margin:0 0 24px; font-size:14px }
form { display:flex; gap:8px; margin-bottom:24px; flex-wrap:wrap }
.targa { flex:1 1 220px; display:flex; align-items:stretch; min-width:0;
  border:2px solid var(--inchiostro); border-radius:8px; overflow:hidden;
  background:#fff }
.banda { background:#003399; color:#fff; width:28px; display:flex;
  flex-direction:column; align-items:center; justify-content:center;
  font-size:11px; font-weight:700; padding:6px 0 }
.banda span { font-size:9px; letter-spacing:.5px }
input[name=targa] { flex:1; min-width:0; border:0; padding:12px 10px;
  font:700 24px/1 monospace; letter-spacing:3px; text-transform:uppercase;
  color:#111; background:#fff }
input[name=targa]:focus { outline:2px solid var(--blu); outline-offset:-2px }
button { border:0; border-radius:8px; background:var(--blu); color:#fff;
  padding:12px 20px; font-size:16px; font-weight:600; cursor:pointer }
.carta { background:var(--carta); border:1px solid var(--riga);
  border-radius:12px; padding:16px; margin-bottom:16px }
.gruppo { font-size:12px; font-weight:700; letter-spacing:.8px;
  color:var(--blu); text-transform:uppercase; margin:0 0 8px }
.riga { display:flex; justify-content:space-between; gap:16px;
  padding:7px 0; border-bottom:1px solid var(--riga) }
.riga:last-child { border-bottom:0 }
.riga .che { color:var(--tenue); font-size:14px }
.riga .quanto { font-weight:600; text-align:right; overflow-wrap:anywhere }
.titolone { font-size:20px; font-weight:700; margin:0 0 2px }
.sotto { color:var(--tenue); font-size:14px; margin:0 }
.si { color:var(--verde); font-weight:700 }
.no { color:var(--rosso); font-weight:700 }
.avviso { background:var(--carta); border:1px solid var(--riga);
  border-left:4px solid var(--rosso); border-radius:8px; padding:12px 16px;
  margin-bottom:16px }
.nota { color:var(--tenue); font-size:13px; margin-top:24px }
form.massa { margin:12px 0 4px; gap:8px }
form.massa input { flex:1; min-width:0; border:1px solid var(--riga);
  border-radius:8px; padding:10px 12px; font-size:16px; background:var(--fondo);
  color:var(--inchiostro) }
form.massa button { padding:10px 16px; font-size:15px }
a { color:var(--blu) }
"""


def _e(s: Any) -> str:
    """Testo di terzi dentro una pagina: sempre da qui, mai diretto."""
    return html.escape("" if s is None else str(s), quote=True)


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


def numero(valore: Any, unita: str = "") -> Optional[str]:
    """2902 diventa «2.902 cc»: il punto delle migliaia si scrive.

    Torna `None` quando non c'e' niente da mostrare, cosi' la riga sparisce
    invece di uscire vuota."""
    if valore in (None, ""):
        return None
    try:
        quanto = float(str(valore).replace(",", "."))
    except ValueError:
        return "%s %s" % (valore, unita) if unita else str(valore)
    scritto = ("{:,.0f}".format(quanto) if quanto == int(quanto)
               else "{:,.1f}".format(quanto))
    # In italiano il punto separa le migliaia e la virgola i decimali:
    # l'inverso dell'inglese, quindi si scambiano in un giro solo.
    scritto = scritto.replace(",", "@").replace(".", ",").replace("@", ".")
    return ("%s %s" % (scritto, unita)) if unita else scritto


def telaio(titolo: str, dentro: str) -> str:
    return ("<!doctype html><html lang=it><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style>"
            "<body><div class=dentro>%s</div>"
            % (_e(titolo), STILE, dentro))


def _cerca(targa: str = "") -> str:
    return ("<form action=/ method=get>"
            "<label class=targa>"
            "<span class=banda>I<span>ITA</span></span>"
            "<input name=targa value='%s' placeholder='AB123CD' "
            "autocapitalize=characters autocomplete=off spellcheck=false "
            "autofocus></label>"
            "<button>Cerca</button></form>" % _e(targa))


def ricerca(messaggio: str = "", targa: str = "") -> str:
    """La pagina d'ingresso. `messaggio` e' il perche', quando c'e'."""
    dentro = ["<h1>Targhe</h1>",
              "<p class=sottotitolo>Scrivi una targa italiana: dati del "
              "veicolo, assicurazione, e chi lo può guidare.</p>",
              _cerca(targa)]
    if messaggio:
        dentro.insert(2, "<div class=avviso>%s</div>" % _e(messaggio))
    return telaio("Targhe", "".join(dentro))


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


def scheda(d: Dict[str, Any]) -> str:
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
        chiedila = ("<form action=/ method=get class=massa>"
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
                     "<div class=riga><span class=che>%s</span></div></div>"
                     % (_e(numero(pass_["euro"])), _e(pass_.get("perche", ""))))
    elif pass_.get("perche"):
        # Senza numero si dice il perche' e basta: un prezzo inventato in
        # una schermata e' una promessa che poi qualcuno deve mantenere
        # allo sportello.
        fuori.append("<div class=carta><p class=gruppo>Passaggio di "
                     "proprietà</p><div class=riga><span class=che>%s</span>"
                     "</div></div>" % _e(pass_["perche"]))

    if d.get("dalla_memoria"):
        # Detto, non nascosto: chi guarda deve sapere che sta leggendo una
        # risposta di ieri, e come si chiede quella di oggi.
        fuori.append("<p class=nota>Dati già in memoria, non richiesti "
                     "adesso al fornitore. Per rifare la domanda: "
                     "<a href='/?targa=%s&fresco=1'>chiedi di nuovo</a>.</p>"
                     % _e(d.get("targa", "")))
    return telaio("%s — Targhe" % (nome or d.get("targa", "")), "".join(fuori))
