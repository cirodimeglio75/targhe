"""La pagina della pratica: l'elenco dei documenti, e dove si caricano.

Una lista con le spunte, e sotto ogni riga mancante il tasto per
fotografare. Niente JavaScript: un modulo HTML con `type=file` apre la
fotocamera su tutti i telefoni da dieci anni, e una pagina che carica
documenti d'identita' e' l'ultimo posto dove serve del codice in piu'.

Il nome del file che arriva dal telefono si mostra, e quindi passa da
`html.escape` come tutto il resto: e' testo scritto da chi sta dall'altra
parte, esattamente come un campo del fornitore.
"""

import html
from typing import Any, Dict

from .telaio import _e, bollo, data as _data_telaio, numero, soldi, telaio

PAROLE_STATO = {"aperta": "in preparazione", "consegnata": "da lavorare",
                "finita": "finita", "saldata": "saldata"}


def _data(quando: Any) -> str:
    return _data_telaio(quando, con_ora=True)


def _messaggi(p: Dict[str, Any]) -> str:
    """La conversazione dentro la pratica: e' li' che l'agenzia dice cosa
    non va, e li' che si ritrova il perche' fra sei mesi."""
    voci = []
    for m in p.get("messaggi") or []:
        voci.append("<div class=messaggio><span class=chi>%s</span>"
                    "<span class=quando>%s · %s</span><p>%s</p></div>"
                    % (_e(m.get("chi", "")), _e(m.get("ruolo", "")),
                       _e(_data(m.get("quando"))), _e(m.get("testo", ""))))
    return ("<div class=carta><p class=gruppo>Messaggi</p>%s"
            "<form action='/pratica/%s' method=post class=carica>"
            "<input name=messaggio placeholder='Scrivi qui' maxlength=2000 "
            "required><button>Manda</button></form></div>"
            % ("".join(voci) or "<p class=sotto>Nessun messaggio.</p>",
               _e(p["id"])))


def _lavoro_agenzia(p: Dict[str, Any], documenti_agenzia) -> str:
    """Quel che vede solo l'agenzia: le due carte di fine lavoro."""
    righe = []
    for chiave, titolo in documenti_agenzia:
        righe.append(_riga_documento(p["id"], chiave, titolo,
                                     (p.get("documenti") or {}).get(chiave)))
    tasto = ""
    if p.get("stato") == "consegnata" and all(
            c in (p.get("documenti") or {}) for c, _ in documenti_agenzia):
        tasto = ("<form action='/pratica/%s' method=post class=carica>"
                 "<input type=hidden name=chiudi value=1>"
                 "<button>Chiudi la pratica</button></form>" % _e(p["id"]))
    return ("<div class=carta><p class=gruppo>Lavoro finito</p>%s%s</div>"
            % ("".join(righe), tasto))


def _riga_documento(identificativo: str, chiave: str, titolo: str,
                    caricato: Dict[str, Any]) -> str:
    if caricato:
        nome = caricato.get("nome_dato") or caricato.get("file", "")
        # Il nome del file lo scrive chi carica: esce da `html.escape` come
        # tutto il resto, e nel collegamento c'e' la CHIAVE, non il nome.
        return ("<div class=riga><span class=che>%s</span>"
                "<span class=quanto><a href='/pratica/%s/documento/%s'>"
                "guarda</a></span></div>"
                "<p class=nota-riga><span class=si>✓</span> %s</p>"
                % (_e(titolo), _e(identificativo), _e(chiave), _e(nome)))
    return ("<div class=riga><span class=che>%s</span></div>"
            "<form action='/pratica/%s' method=post "
            "enctype='multipart/form-data' class=carica>"
            "<input type=hidden name=documento value='%s'>"
            "<input type=file name=file accept='image/*,.pdf' required>"
            "<button>Carica</button></form>"
            % (_e(titolo), _e(identificativo), _e(chiave)))


def pratica(p: Dict[str, Any], tipo: Dict[str, Any],
            messaggio: str = "", conto: Dict[str, Any] = None,
            documenti_agenzia=()) -> str:
    conto = conto or {}
    ruolo = conto.get("ruolo", "")
    dentro = ["<h1>%s</h1>" % _e(tipo.get("nome", "Pratica"))]
    sotto = []
    if p.get("targa"):
        sotto.append("Targa %s" % p["targa"])
    if p.get("prezzo"):
        sotto.append("%s €" % numero(p["prezzo"]))
    if ruolo in ("agenzia", "amministrazione") and p.get("concessionaria"):
        sotto.append(p["concessionaria"])
    if sotto:
        dentro.append("<p class=sottotitolo>%s %s</p>"
                      % (_e(" · ".join(sotto)), bollo(p.get("stato", ""))))
    if messaggio:
        dentro.append("<div class=avviso>%s</div>" % _e(messaggio))

    if p.get("completa"):
        dentro.append("<div class=carta><p class=titolone>"
                      "<span class=si>Tutto arrivato</span></p>"
                      "<p class=sotto>Abbiamo i documenti che servono. "
                      "Se manca qualcosa ti chiamiamo.</p></div>")
    else:
        quanti = len(p.get("manca") or [])
        dentro.append("<div class=carta><p class=titolone>Manca %d "
                      "document%s</p><p class=sotto>Fotografali col telefono: "
                      "va bene la foto, non serve lo scanner.</p></div>"
                      % (quanti, "o" if quanti == 1 else "i"))

    righe = []
    for chiave, titolo, _obbligatorio in tipo.get("documenti", []):
        righe.append(_riga_documento(p["id"], chiave, titolo,
                                     (p.get("documenti") or {}).get(chiave)))
    dentro.append("<div class=carta><p class=gruppo>Documenti</p>%s</div>"
                  % "".join(righe))

    if tipo.get("motivo"):
        dentro.append(
            "<div class=carta><p class=gruppo>Motivo</p>"
            "<div class=riga><span class=che>%s</span></div>"
            "<form action='/pratica/%s' method=post class=carica>"
            "<input name=motivo value='%s' placeholder='In due righe' "
            "maxlength=500><button>Salva</button></form></div>"
            % (_e(tipo["motivo"]), _e(p["id"]), _e(p.get("motivo", ""))))

    if ruolo == "agenzia":
        dentro.append(_lavoro_agenzia(p, documenti_agenzia))
    elif p.get("stato") in ("finita", "saldata"):
        dentro.append("<div class=carta><p class=titolone>"
                      "<span class=si>Pratica finita</span></p>"
                      "<p class=sotto>L'agenzia ha caricato il documento e "
                      "la ricevuta.</p></div>")

    dentro.append(_messaggi(p))
    dentro.append("<p class=nota>I documenti si aprono solo da qui, e solo "
                  "a chi ha titolo. <a href='/area'>Torna all'elenco</a></p>")
    return telaio(tipo.get("nome", "Pratica"), "".join(dentro), conto,
                  "/area")
