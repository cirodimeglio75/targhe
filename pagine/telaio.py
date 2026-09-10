"""Il telaio comune: lo stile, la barra in alto, i pezzi che si ripetono.

Sta qui e non dentro una pagina per la stessa ragione per cui in Ops! c'e'
`telaio_messaggi.py`: **il telaio non guarda nessuno**. Le pagine importano
da lui; lui non importa pagine. Senza questa regola nasce un giro chiuso e
Python lo rifiuta.

Sul come e' fatto, una cosa sola vale la pena spiegarla. Questa non e' una
pagina da telefono: e' un banco di lavoro, e chi la usa ci sta davanti
tutto il giorno su uno schermo largo. Quindi **il contenuto respira fino a
1120 pixel**, le righe stanno in tabella — che e' come si legge un elenco
di pratiche — e sul telefono la tabella scorre di lato invece di
sbriciolarsi. La prima versione era una colonna stretta stirata su un
monitor da 27 pollici, ed era il difetto piu' visibile del programma.
"""

import html
import time
from typing import Any, Dict, List, Optional, Sequence

STILE = """
:root { color-scheme: light dark;
  --fondo:#eef1f6; --carta:#fff; --inchiostro:#141821; --tenue:#657085;
  --riga:#e2e7f0; --blu:#1b47c4; --blu-tenue:#eaf0ff; --verde:#177245;
  --verde-tenue:#e6f5ec; --giallo:#8a5a00; --giallo-tenue:#fdf2dc;
  --rosso:#b3261e; --rosso-tenue:#fdeceb; --barra:#0f1830; }
@media (prefers-color-scheme: dark) { :root {
  --fondo:#0c0f16; --carta:#151a24; --inchiostro:#e8eaf0; --tenue:#98a2b6;
  --riga:#242b39; --blu:#7aa2ff; --blu-tenue:#182338; --verde:#5bd08d;
  --verde-tenue:#12251a; --giallo:#e0b155; --giallo-tenue:#2a2213;
  --rosso:#ff8a80; --rosso-tenue:#2a1614; --barra:#080b12; } }
* { box-sizing:border-box }
body { margin:0; background:var(--fondo); color:var(--inchiostro);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
  "Helvetica Neue",sans-serif; }
a { color:var(--blu) }

/* la barra in alto */
.barra { background:var(--barra); color:#fff; padding:0 20px }
.barra .dentro { max-width:1120px; margin:0 auto; display:flex;
  align-items:center; gap:16px; min-height:56px; flex-wrap:wrap }
.barra .marchio { font-weight:700; letter-spacing:.2px; font-size:16px;
  color:#fff; text-decoration:none }
.barra .marchio span { color:#8fa8ff }
.barra nav { display:flex; gap:14px; margin-left:8px; flex-wrap:wrap }
.barra nav a { color:#c9d2e6; text-decoration:none; font-size:14px;
  padding:6px 0; border-bottom:2px solid transparent }
.barra nav a:hover { color:#fff }
.barra nav a.qui { color:#fff; border-bottom-color:#5b7cff }
.barra .chi { margin-left:auto; display:flex; align-items:center; gap:12px;
  font-size:13px; color:#c9d2e6 }
.barra .chi b { color:#fff; font-weight:600 }
.barra .chi a { color:#c9d2e6 }

/* il foglio */
.dentro { max-width:1120px; margin:0 auto; padding:0 20px }
main.dentro { padding-block:24px 64px }
h1 { font-size:22px; margin:0 0 4px; letter-spacing:-.2px }
.sottotitolo { color:var(--tenue); margin:0 0 20px; font-size:14px }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:.9px;
  color:var(--tenue); margin:0 0 10px; font-weight:700 }

.carta { background:var(--carta); border:1px solid var(--riga);
  border-radius:14px; padding:18px 20px; margin-bottom:18px;
  box-shadow:0 1px 2px rgba(16,24,40,.04) }
.carta.stretta { padding:0; overflow:hidden }
.carta.stretta h2 { padding:16px 20px 0 }

/* i numeri in cima */
.numeri { display:grid; gap:14px; margin-bottom:20px;
  grid-template-columns:repeat(auto-fit,minmax(190px,1fr)) }
.numero { background:var(--carta); border:1px solid var(--riga);
  border-radius:14px; padding:16px 18px }
.numero .che { color:var(--tenue); font-size:12px; text-transform:uppercase;
  letter-spacing:.7px; font-weight:700 }
.numero .quanto { font-size:26px; font-weight:700; letter-spacing:-.6px;
  margin-top:4px }
.numero .sotto { color:var(--tenue); font-size:12px; margin-top:2px }
.numero.attenzione .quanto { color:var(--rosso) }
.numero.bene .quanto { color:var(--verde) }

/* le tabelle: e' cosi' che si legge un elenco di pratiche */
.scorre { overflow-x:auto }
table { width:100%; border-collapse:collapse; font-size:14px }
th { text-align:left; font-size:11px; text-transform:uppercase;
  letter-spacing:.8px; color:var(--tenue); font-weight:700;
  padding:10px 20px; border-bottom:1px solid var(--riga); white-space:nowrap }
td { padding:12px 20px; border-bottom:1px solid var(--riga);
  vertical-align:middle }
tr:last-child td { border-bottom:0 }
tbody tr:hover { background:var(--blu-tenue) }
td.destra, th.destra { text-align:right; white-space:nowrap }
td a { text-decoration:none; font-weight:600 }
td .targa { font:700 14px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:1px }
td .piccolo { color:var(--tenue); font-size:12.5px }

/* i bollini di stato */
.bollo { display:inline-block; font-size:12px; font-weight:700;
  padding:3px 10px; border-radius:999px; white-space:nowrap;
  background:var(--riga); color:var(--tenue) }
.bollo.attesa { background:var(--giallo-tenue); color:var(--giallo) }
.bollo.lavoro { background:var(--blu-tenue); color:var(--blu) }
.bollo.fatto { background:var(--verde-tenue); color:var(--verde) }
.bollo.male { background:var(--rosso-tenue); color:var(--rosso) }

/* moduli e tasti */
form { display:flex; gap:10px; flex-wrap:wrap; align-items:center;
  margin:0 }
form.dritto { flex-direction:column; align-items:stretch; max-width:420px }
/* Su schermo largo i moduli lunghi stanno su due colonne: una colonna
   sola di dodici campi e' un modulo che nessuno finisce. */
@media (min-width:760px) {
  form.dritto.largo { display:grid; max-width:none;
    grid-template-columns:repeat(3,1fr); align-items:start }
  form.dritto.largo button { grid-column:1/-1; justify-self:start;
    padding-inline:28px }
}
/* Dentro una tabella i moduli non vanno a capo: farebbero righe alte il
   doppio e la tabella smetterebbe di essere una tabella. */
td form { flex-wrap:nowrap; justify-content:flex-end }
td input { padding:7px 9px; font-size:14px }
td button { padding:7px 12px; font-size:14px }
input, select { border:1px solid var(--riga); border-radius:9px;
  padding:10px 12px; font-size:15px; background:var(--fondo);
  color:var(--inchiostro); min-width:0 }
input:focus, select:focus { outline:2px solid var(--blu);
  outline-offset:-1px }
button { border:0; border-radius:9px; background:var(--blu); color:#fff;
  padding:10px 18px; font-size:15px; font-weight:600; cursor:pointer }
button:hover { filter:brightness(1.08) }
button.piano { background:var(--riga); color:var(--inchiostro) }

.avviso { background:var(--blu-tenue); border:1px solid var(--riga);
  border-left:3px solid var(--blu); border-radius:10px; padding:12px 16px;
  margin-bottom:18px; font-size:14px }
.avviso.male { background:var(--rosso-tenue); border-left-color:var(--rosso) }
.nota { color:var(--tenue); font-size:13px; margin-top:22px }

/* --- la scheda di un veicolo e la pratica: coppie «che / quanto» --- */
.gruppo { font-size:11px; font-weight:700; letter-spacing:.9px;
  color:var(--tenue); text-transform:uppercase; margin:0 0 10px }
.riga { display:flex; justify-content:space-between; gap:20px;
  padding:9px 0; border-bottom:1px solid var(--riga) }
.riga:last-child { border-bottom:0 }
.riga .che { color:var(--tenue); font-size:14px }
.riga .quanto { font-weight:600; text-align:right; overflow-wrap:anywhere }
.titolone { font-size:20px; font-weight:700; margin:0 0 2px;
  letter-spacing:-.3px }
.sotto { color:var(--tenue); font-size:14px; margin:0 }
.nota-riga { color:var(--tenue); font-size:13px; margin:2px 0 10px }

/* la targa, disegnata come una targa */
.targa { display:inline-flex; align-items:stretch; min-width:0;
  border:2px solid var(--inchiostro); border-radius:8px; overflow:hidden;
  background:#fff; max-width:320px; flex:1 1 220px }
.banda { background:#039; color:#fff; width:26px; display:flex;
  flex-direction:column; align-items:center; justify-content:center;
  font-size:11px; font-weight:700; padding:6px 0 }
.banda span { font-size:9px; letter-spacing:.5px }
input[name=targa] { flex:1; min-width:0; border:0; border-radius:0;
  padding:11px 10px; font:700 22px/1 ui-monospace,SFMono-Regular,Menlo,
  monospace; letter-spacing:3px; text-transform:uppercase; color:#111;
  background:#fff }

/* i moduli dentro le schede: caricare un documento, scrivere un motivo */
form.massa, form.carica { margin:10px 0 4px }
form.massa input, form.carica input[name=motivo],
form.carica input[name=messaggio] { flex:1 1 220px }
form.carica input[type=file] { flex:1 1 240px; font-size:14px;
  border:1px dashed var(--riga); background:transparent; padding:8px }

/* la conversazione dentro la pratica */
.messaggio { padding:11px 0; border-bottom:1px solid var(--riga) }
.messaggio:last-of-type { border-bottom:0 }
.messaggio .chi { font-weight:700; font-size:13px }
.messaggio .quando { color:var(--tenue); font-size:12px; margin-left:6px }
.messaggio p { margin:3px 0 0; overflow-wrap:anywhere }
.vuoto { color:var(--tenue); font-size:14px; padding:18px 20px }
.si { color:var(--verde); font-weight:700 }
.no { color:var(--rosso); font-weight:700 }
"""

# Come si chiama uno stato quando lo legge una persona, e di che colore e'.
STATI = {"aperta": ("in preparazione", "attesa"),
         "consegnata": ("da lavorare", "lavoro"),
         "finita": ("finita", "fatto"),
         "saldata": ("saldata", "")}


def _e(s: Any) -> str:
    """Testo di terzi dentro una pagina: sempre da qui, mai diretto."""
    return html.escape("" if s is None else str(s), quote=True)


def numero(valore: Any, unita: str = "") -> Optional[str]:
    """2902 diventa «2.902»: il punto delle migliaia si scrive."""
    if valore in (None, ""):
        return None
    try:
        quanto = float(str(valore).replace(",", "."))
    except ValueError:
        return "%s %s" % (valore, unita) if unita else str(valore)
    scritto = ("{:,.0f}".format(quanto) if quanto == int(quanto)
               else "{:,.1f}".format(quanto))
    # In italiano il punto separa le migliaia e la virgola i decimali.
    scritto = scritto.replace(",", "@").replace(".", ",").replace("@", ".")
    return ("%s %s" % (scritto, unita)) if unita else scritto


def soldi(valore: Any) -> str:
    quanto = float(valore or 0)
    scritto = "{:,.2f}".format(quanto)
    return scritto.replace(",", "@").replace(".", ",").replace("@", ".") + " €"


def data(quando: Any, con_ora: bool = False) -> str:
    try:
        forma = "%d/%m/%Y %H:%M" if con_ora else "%d/%m/%Y"
        return time.strftime(forma, time.localtime(float(quando)))
    except (TypeError, ValueError):
        return ""


def bollo(stato: str) -> str:
    parola, colore = STATI.get(stato, (stato or "", ""))
    return "<span class='bollo %s'>%s</span>" % (colore, _e(parola))


def numeri(voci: Sequence) -> str:
    """La riga dei numeri in cima: («che», «quanto», «sotto», «segno»)."""
    fuori = []
    for voce in voci:
        che, quanto = voce[0], voce[1]
        sotto = voce[2] if len(voce) > 2 else ""
        segno = voce[3] if len(voce) > 3 else ""
        fuori.append("<div class='numero %s'><div class=che>%s</div>"
                     "<div class=quanto>%s</div>%s</div>"
                     % (_e(segno), _e(che), _e(quanto),
                        ("<div class=sotto>%s</div>" % _e(sotto)) if sotto
                        else ""))
    return "<div class=numeri>%s</div>" % "".join(fuori)


def tabella(colonne: Sequence, righe: Sequence, vuoto: str = "") -> str:
    """Una tabella. `colonne` sono («titolo», destra?); le righe arrivano
    gia' vestite, perche' dentro ci sono collegamenti e bollini."""
    if not righe:
        return "<p class=vuoto>%s</p>" % (vuoto or "Niente da mostrare.")
    testa = "".join("<th%s>%s</th>" % (" class=destra" if len(c) > 1 and c[1]
                                       else "", _e(c[0])) for c in colonne)
    return ("<div class=scorre><table><thead><tr>%s</tr></thead><tbody>%s"
            "</tbody></table></div>" % (testa, "".join(righe)))


def telaio(titolo: str, dentro: str, conto: Optional[Dict[str, Any]] = None,
           qui: str = "") -> str:
    """La pagina intera, con la barra in alto se c'e' qualcuno dentro."""
    barra = ""
    if conto:
        voci = [("/area", "Le pratiche")]
        if conto.get("ruolo") == "concessionaria":
            voci.append(("/cerca", "Cerca una targa"))
        collegamenti = "".join(
            "<a href='%s'%s>%s</a>"
            % (_e(dove), " class=qui" if dove == qui else "", _e(nome))
            for dove, nome in voci)
        barra = ("<header class=barra><div class=dentro>"
                 "<a class=marchio href='/'>Pratiche<span>.</span></a>"
                 "<nav>%s</nav>"
                 "<div class=chi><b>%s</b> · %s · <a href='/esci'>esci</a>"
                 "</div></div></header>"
                 % (collegamenti, _e(conto.get("nome") or conto.get("utente")),
                    _e(conto.get("ruolo", ""))))
    return ("<!doctype html><html lang=it><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style>"
            "<body>%s<main class=dentro>%s</main>"
            % (_e(titolo), STILE, barra, dentro))
