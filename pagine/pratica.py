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

from .scheda import STILE, _e, numero, telaio


def _riga_documento(identificativo: str, chiave: str, titolo: str,
                    caricato: Dict[str, Any]) -> str:
    if caricato:
        nome = caricato.get("nome_dato") or caricato.get("file", "")
        return ("<div class=riga><span class=che>%s</span>"
                "<span class=quanto><span class=si>✓</span></span></div>"
                "<p class=nota-riga>%s</p>" % (_e(titolo), _e(nome)))
    return ("<div class=riga><span class=che>%s</span></div>"
            "<form action='/pratica/%s' method=post "
            "enctype='multipart/form-data' class=carica>"
            "<input type=hidden name=documento value='%s'>"
            "<input type=file name=file accept='image/*,.pdf' required>"
            "<button>Carica</button></form>"
            % (_e(titolo), _e(identificativo), _e(chiave)))


def pratica(p: Dict[str, Any], tipo: Dict[str, Any],
            messaggio: str = "") -> str:
    dentro = ["<h1>%s</h1>" % _e(tipo.get("nome", "Pratica"))]
    if p.get("targa"):
        dentro.append("<p class=sottotitolo>Targa %s</p>" % _e(p["targa"]))
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

    dentro.append("<p class=nota>Questo indirizzo è la chiave della "
                  "pratica: tienilo, e non darlo a chi non deve vederla. "
                  "I documenti caricati non si riscaricano da qui.</p>")
    return telaio("%s — Targhe" % tipo.get("nome", "Pratica"), "".join(dentro))
