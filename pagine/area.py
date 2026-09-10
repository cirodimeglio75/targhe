"""Le tre aree: chi entra, cosa vede.

La stessa pagina non va bene per tre mestieri diversi. L'agenzia vuole
l'elenco per concessionaria, perche' e' cosi' che poi fattura. La
concessionaria vuole le sue pratiche e quanto le resta di plafond, perche'
e' quello che decide se puo' prendere il lavoro. L'amministrazione vuole i
conti.

Tutto quel che si mostra qui e' scritto da qualcuno: nomi di
concessionarie, messaggi, nomi di file. Passa tutto da `html.escape`, senza
eccezioni.
"""

import time
from typing import Any, Dict, List

from veicoli.pratiche import TIPI

from .scheda import _e, numero, telaio


def _data(quando: Any) -> str:
    try:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(float(quando)))
    except (TypeError, ValueError):
        return ""


PAROLE_STATO = {"aperta": "in preparazione", "consegnata": "da lavorare",
                "finita": "finita", "saldata": "saldata"}


def entra(messaggio: str = "") -> str:
    dentro = ["<h1>Entra</h1>",
              "<p class=sottotitolo>Area riservata a concessionarie, "
              "agenzia e amministrazione.</p>"]
    if messaggio:
        dentro.append("<div class=avviso>%s</div>" % _e(messaggio))
    dentro.append(
        "<form action=/entra method=post class=carica>"
        "<input name=utente placeholder='Nome utente' autocapitalize=none "
        "autocomplete=username required>"
        "<input name=parola type=password placeholder=\"Parola d'ordine\" "
        "autocomplete=current-password required>"
        "<button>Entra</button></form>")
    return telaio("Entra — Targhe", "".join(dentro))


def _riga_pratica(p: Dict[str, Any], con_concessionaria: bool = False) -> str:
    stato = PAROLE_STATO.get(p.get("stato", ""), p.get("stato", ""))
    # Il nome tecnico della pratica non si mostra: «societa-persona» e' come
    # la chiama il codice, non come la chiama chi ci lavora.
    nome_tipo = TIPI.get(p.get("tipo", ""), {}).get("nome", p.get("tipo", ""))
    sotto = [_e(nome_tipo), stato]
    if con_concessionaria and p.get("concessionaria"):
        sotto.insert(0, _e(p["concessionaria"]))
    if p.get("manca"):
        sotto.append("manca%s %d document%s"
                     % ("" if len(p["manca"]) == 1 else "no", len(p["manca"]),
                        "o" if len(p["manca"]) == 1 else "i"))
    prezzo = numero(p.get("prezzo")) if p.get("prezzo") else ""
    return ("<a class=voce href='/pratica/%s'>"
            "<span class=voce-testa>%s</span>"
            "<span class=voce-sotto>%s</span>"
            "<span class=voce-prezzo>%s</span></a>"
            % (_e(p.get("id", "")), _e(p.get("targa") or "senza targa"),
               " · ".join(sotto), (prezzo + " €") if prezzo else ""))


def agenzia(gruppi: Dict[str, List[Dict[str, Any]]],
            nomi: Dict[str, Any]) -> str:
    dentro = ["<h1>Pratiche</h1>",
              "<p class=sottotitolo>Tutte le concessionarie. Le più nuove "
              "in alto.</p>"]
    if not gruppi:
        dentro.append("<div class=carta><p class=sotto>Non è ancora "
                      "arrivata nessuna pratica.</p></div>")
    for chiave in sorted(gruppi):
        pratiche = gruppi[chiave]
        da_fare = sum(1 for p in pratiche if p.get("stato") == "consegnata")
        nome = (nomi.get(chiave) or {}).get("nome", chiave)
        dentro.append("<div class=carta><p class=gruppo>%s%s</p>%s</div>"
                      % (_e(nome),
                         (" — %d da lavorare" % da_fare) if da_fare else "",
                         "".join(_riga_pratica(p) for p in pratiche)))
    return telaio("Pratiche — Targhe", "".join(dentro))


def concessionaria(pratiche: List[Dict[str, Any]], plafond: Dict[str, Any],
                   note: List[Dict[str, Any]],
                   fatture: List[Dict[str, Any]] = ()) -> str:
    dentro = ["<h1>%s</h1>" % _e(plafond.get("nome", "Le tue pratiche"))]
    resta = plafond.get("resta", 0)
    dentro.append(
        "<div class=carta><p class=gruppo>Plafond</p>"
        "<div class=riga><span class=che>Ti resta</span>"
        "<span class=quanto>%s €</span></div>"
        "<div class=riga><span class=che>Assegnato</span>"
        "<span class=quanto>%s €</span></div>"
        "<div class=riga><span class=che>In ballo</span>"
        "<span class=quanto>%s €</span></div></div>"
        % (_e(numero(resta)), _e(numero(plafond.get("plafond", 0))),
           _e(numero(plafond.get("usato", 0)))))

    da_saldare = [n for n in note if not n.get("saldata")]
    if da_saldare:
        dentro.append("<div class=carta><p class=gruppo>Da saldare</p>%s</div>"
                      % "".join(
                          "<div class=riga><span class=che>Nota della "
                          "settimana %s</span><span class=quanto>%s € · "
                          "<a href='/nota/%s.pdf'>PDF</a></span></div>"
                          % (_e(n.get("settimana", "")),
                             _e(numero(n.get("totale", 0))), _e(n.get("id", "")))
                          for n in da_saldare))

    if fatture:
        dentro.append(
            "<div class=carta><p class=gruppo>Fatture</p>%s</div>"
            % "".join("<div class=riga><span class=che>n. %s del %s</span>"
                      "<span class=quanto>%s € · <a href='/fattura/%s.pdf'>"
                      "PDF</a></span></div>"
                      % (_e(f.get("numero", "")), _e(_data(f.get("quando"))[:10]),
                         _e(numero(f.get("conti", {}).get("totale", 0))),
                         _e(f.get("id", ""))) for f in fatture))

    dentro.append("<div class=carta><p class=gruppo>Le tue pratiche</p>%s</div>"
                  % ("".join(_riga_pratica(p) for p in pratiche)
                     or "<p class=sotto>Nessuna pratica. Cerca una targa e "
                        "comincia da lì.</p>"))
    coda = ["<a href='/'>Cerca una targa</a>"]
    if da_saldare:
        coda.append("<a href='/estratto.pdf'>estratto conto</a>")
    coda.append("<a href='/esci'>esci</a>")
    dentro.append("<p class=nota>%s</p>" % " · ".join(coda))
    return telaio("Le tue pratiche — Targhe", "".join(dentro))


def amministrazione(conti_plafond: List[Dict[str, Any]],
                    note: List[Dict[str, Any]],
                    da_conteggiare: Dict[str, float],
                    messaggio: str = "",
                    fisco: Dict[str, Any] = None,
                    guasto_fisco: str = "",
                    fatture: List[Dict[str, Any]] = ()) -> str:
    fisco = fisco or {}
    dentro = ["<h1>Amministrazione</h1>"]
    if messaggio:
        dentro.append("<div class=avviso>%s</div>" % _e(messaggio))

    oggi = time.localtime()
    if oggi.tm_wday == 5:
        dentro.append("<div class=carta><p class=titolone>È sabato</p>"
                      "<p class=sotto>Giorno del conteggio: le note emesse "
                      "oggi vanno saldate entro lunedì.</p></div>")

    righe = []
    for c in conti_plafond:
        pronte = da_conteggiare.get(c["concessionaria"], 0)
        righe.append(
            "<div class=riga><span class=che>%s</span>"
            "<span class=quanto>%s € su %s €</span></div>"
            "<form action=/area/plafond method=post class=carica>"
            "<input type=hidden name=concessionaria value='%s'>"
            "<input name=plafond inputmode=decimal placeholder='Plafond €' "
            "value='%s'>"
            "<input name=posta type=email placeholder='Posta per le note' "
            "value='%s'><button>Salva</button></form>"
            % (_e(c["nome"]), _e(numero(c["usato"])),
               _e(numero(c["plafond"])), _e(c["concessionaria"]),
               _e(numero(c["plafond"])), _e(c.get("posta", ""))))
        if pronte:
            righe.append(
                "<form action=/area/nota method=post class=carica>"
                "<input type=hidden name=concessionaria value='%s'>"
                "<button>Emetti nota: %s €</button></form>"
                % (_e(c["concessionaria"]), _e(numero(pronte))))
    dentro.append("<div class=carta><p class=gruppo>Concessionarie</p>%s</div>"
                  % ("".join(righe) or "<p class=sotto>Nessuna "
                     "concessionaria.</p>"))

    if note:
        voci = []
        for n in note:
            if n.get("saldata"):
                voci.append("<div class=riga><span class=che>%s · %s</span>"
                            "<span class=quanto><span class=si>saldata</span>"
                            " · <a href='/nota/%s.pdf'>PDF</a></span></div>"
                            % (_e(n.get("concessionaria", "")),
                               _e(n.get("settimana", "")), _e(n.get("id", ""))))
            else:
                voci.append(
                    "<div class=riga><span class=che>%s · %s</span>"
                    "<span class=quanto>%s € · <a href='/nota/%s.pdf'>PDF</a>"
                    "</span></div>"
                    "<form action=/area/saldo method=post class=carica>"
                    "<input type=hidden name=nota value='%s'>"
                    "<button>Segna saldata</button></form>"
                    % (_e(n.get("concessionaria", "")),
                       _e(n.get("settimana", "")),
                       _e(numero(n.get("totale", 0))), _e(n.get("id", "")),
                       _e(n.get("id", ""))))
        dentro.append("<div class=carta><p class=gruppo>Note di saldo</p>%s"
                      "</div>" % "".join(voci))

    # Un modulo solo: i quattro campi partono insieme o non parte niente.
    # Due moduli affiancati sembrano uno e mandano meta' dei dati.
    if fatture:
        dentro.append(
            "<div class=carta><p class=gruppo>Fatture</p>%s</div>"
            % "".join("<div class=riga><span class=che>n. %s · %s</span>"
                      "<span class=quanto>%s € · <a href='/fattura/%s.pdf'>"
                      "PDF</a></span></div>"
                      % (_e(f.get("numero", "")), _e(f.get("concessionaria", "")),
                         _e(numero(f.get("conti", {}).get("totale", 0))),
                         _e(f.get("id", ""))) for f in fatture[:20]))

    # I dati fiscali: senza questi la piattaforma NON emette fatture, e lo
    # dice qui invece di scoprirlo il sabato mattina.
    campi = [("ragione_sociale", "Ragione sociale"), ("piva", "Partita IVA"),
             ("codice_fiscale", "Codice fiscale"), ("indirizzo", "Indirizzo"),
             ("cap", "CAP"), ("citta", "Città"), ("provincia", "Provincia"),
             ("iban", "IBAN"), ("iva", "Aliquota IVA %")]
    moduli = "".join(
        "<input name='%s' placeholder='%s' value='%s'>"
        % (_e(chiave), _e(nome), _e(fisco.get(chiave, "")))
        for chiave, nome in campi)
    compensi = "".join(
        "<input name='compenso_%s' inputmode=decimal "
        "placeholder='Compenso — %s' value='%s'>"
        % (_e(chiave), _e(voce["nome"]),
           _e((fisco.get("compensi") or {}).get(chiave, "")))
        for chiave, voce in TIPI.items())
    dentro.append(
        "<div class=carta><p class=gruppo>Dati per le fatture</p>%s"
        "<form action=/area/fisco method=post class='carica dritto'>%s%s"
        "<button>Salva</button></form>"
        "<p class=nota-riga>Il <b>compenso</b> è la parte imponibile: il "
        "resto dell'importo è anticipazione in nome e per conto (art. 15 "
        "DPR 633/72), fuori campo IVA. Quanto sia, lo dice il "
        "commercialista.</p></div>"
        % (("<div class=avviso>%s</div>" % _e(guasto_fisco))
           if guasto_fisco else "", moduli, compensi))

    dentro.append(
        "<div class=carta><p class=gruppo>Conto nuovo</p>"
        "<form action=/area/conto method=post class='carica dritto'>"
        "<input name=utente placeholder='Nome utente' autocapitalize=none "
        "required>"
        "<input name=parola type=password placeholder=\"Parola d'ordine "
        "(almeno 8)\" required>"
        "<input name=nome placeholder='Nome da mostrare'>"
        "<input name=concessionaria placeholder='Concessionaria: id breve, "
        "es. rossi'>"
        "<input name=posta type=email placeholder='Posta della "
        "concessionaria'>"
        "<button name=ruolo value=concessionaria>Crea concessionaria</button>"
        "</form>"
        "<p class=nota-riga>Il conto di una concessionaria porta con sé il "
        "suo identificativo: è quello che lega le pratiche al plafond.</p>"
        "</div>")
    dentro.append("<p class=nota><a href='/esci'>esci</a></p>")
    return telaio("Amministrazione — Targhe", "".join(dentro))
