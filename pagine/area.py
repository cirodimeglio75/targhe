"""Le tre aree: chi entra, cosa vede.

La stessa pagina non va bene per tre mestieri diversi:

- **l'agenzia** vuole sapere **quante pratiche ha da lavorare adesso**, e
  poi l'elenco per concessionaria, perche' e' cosi' che poi fattura;
- **la concessionaria** vuole sapere **quanto plafond le resta**, perche'
  e' quello che decide se puo' prendere il lavoro;
- **l'amministrazione** vuole i **soldi in ballo** e chi deve saldare.

Da qui la forma: in cima i numeri che rispondono a quella domanda, sotto le
tabelle. Un elenco di pratiche si legge in tabella, non in una colonna di
schede una sopra l'altra — e chi lo guarda ci sta davanti tutto il giorno.

Tutto quel che si mostra e' scritto da qualcuno: nomi di concessionarie,
messaggi, nomi di file. Passa tutto da `html.escape`, senza eccezioni.
"""

import time
from typing import Any, Dict, List

from veicoli.pratiche import TIPI

from .telaio import (_e, bollo, data, numeri, numero, soldi, tabella,
                     telaio)

PAROLE_STATO = {"aperta": "in preparazione", "consegnata": "da lavorare",
                "finita": "finita", "saldata": "saldata"}


def entra(messaggio: str = "") -> str:
    dentro = ["<div style='max-width:420px;margin:8vh auto 0'>",
              "<h1>Portale pratiche</h1>",
              "<p class=sottotitolo>Passaggi di proprietà, mini passaggi, "
              "perdite di possesso e immatricolazioni. Area riservata a "
              "concessionarie, agenzia e amministrazione.</p>"]
    if messaggio:
        dentro.append("<div class='avviso male'>%s</div>" % _e(messaggio))
    dentro.append(
        "<div class=carta><form action=/entra method=post class=dritto>"
        "<input name=utente placeholder='Nome utente' autocapitalize=none "
        "autocomplete=username required>"
        "<input name=parola type=password placeholder=\"Parola d'ordine\" "
        "autocomplete=current-password required>"
        "<button>Entra</button></form></div></div>")
    return telaio("Portale pratiche", "".join(dentro))


def _nome_tipo(pratica: Dict[str, Any]) -> str:
    # «societa-persona» e' come la chiama il codice, non chi ci lavora.
    return TIPI.get(pratica.get("tipo", ""), {}).get("nome",
                                                     pratica.get("tipo", ""))


def _riga_pratica(p: Dict[str, Any], nomi: Dict[str, Any] = None,
                  con_chi: bool = False) -> str:
    manca = p.get("manca") or []
    dettaglio = _nome_tipo(p)
    if manca:
        dettaglio += " · manca%s %d document%s" % (
            "" if len(manca) == 1 else "no", len(manca),
            "o" if len(manca) == 1 else "i")
    chi = ""
    if con_chi:
        quale = p.get("concessionaria") or ""
        chi = "<td>%s</td>" % _e((nomi or {}).get(quale, {}).get("nome", quale))
    return ("<tr><td><a href='/pratica/%s'><span class=targa>%s</span></a>"
            "<div class=piccolo>%s</div></td>%s<td>%s</td>"
            "<td class=piccolo>%s</td><td class=destra>%s</td></tr>"
            % (_e(p.get("id", "")), _e(p.get("targa") or "—"), _e(dettaglio),
               chi, bollo(p.get("stato", "")), _e(data(p.get("aperta"))),
               _e(soldi(p.get("prezzo", 0)) if p.get("prezzo") else "—")))


# ------------------------------------------------------------- l'agenzia

def agenzia(gruppi: Dict[str, List[Dict[str, Any]]],
            nomi: Dict[str, Any], conto: Dict[str, Any] = None) -> str:
    tutte = [p for voci in gruppi.values() for p in voci]
    da_lavorare = [p for p in tutte if p.get("stato") == "consegnata"]
    in_preparazione = [p for p in tutte if p.get("stato") == "aperta"]
    finite = [p for p in tutte if p.get("stato") == "finita"]

    dentro = ["<h1>Pratiche</h1>",
              "<p class=sottotitolo>Tutte le concessionarie.</p>",
              numeri([
                  ("Da lavorare", len(da_lavorare),
                   "documenti completi, tocca a te",
                   "attenzione" if da_lavorare else ""),
                  ("In preparazione", len(in_preparazione),
                   "la concessionaria sta caricando"),
                  ("Finite, non saldate", len(finite),
                   soldi(sum(float(p.get("prezzo") or 0) for p in finite))),
                  ("Concessionarie", len(gruppi)),
              ])]

    if da_lavorare:
        dentro.append(
            "<div class='carta stretta'><h2>Da lavorare adesso</h2>%s</div>"
            % tabella([("Targa",), ("Concessionaria",), ("Stato",),
                       ("Aperta il",), ("Importo", True)],
                      [_riga_pratica(p, nomi, True) for p in da_lavorare]))

    for chiave in sorted(gruppi):
        pratiche = gruppi[chiave]
        nome = (nomi.get(chiave) or {}).get("nome", chiave)
        quante = sum(1 for p in pratiche if p.get("stato") == "consegnata")
        dentro.append(
            "<div class='carta stretta'><h2>%s%s</h2>%s</div>"
            % (_e(nome),
               (" — %d da lavorare" % quante) if quante else "",
               tabella([("Targa",), ("Stato",), ("Aperta il",),
                        ("Importo", True)],
                       [_riga_pratica(p) for p in pratiche])))
    if not gruppi:
        dentro.append("<div class=carta><p class=vuoto>Non è ancora "
                      "arrivata nessuna pratica.</p></div>")
    return telaio("Pratiche", "".join(dentro), conto, "/area")


# ------------------------------------------------------- la concessionaria

def concessionaria(pratiche: List[Dict[str, Any]], plafond: Dict[str, Any],
                   note: List[Dict[str, Any]],
                   fatture: List[Dict[str, Any]] = (),
                   conto: Dict[str, Any] = None) -> str:
    da_saldare = [n for n in note if not n.get("saldata")]
    dovuto = sum(float(n.get("totale") or 0) for n in da_saldare)
    aperte = [p for p in pratiche if p.get("stato") in ("aperta",
                                                        "consegnata")]
    resta = float(plafond.get("resta") or 0)
    quota = (resta / float(plafond.get("plafond") or 1)) * 100

    dentro = ["<h1>%s</h1>" % _e(plafond.get("nome", "Le tue pratiche")),
              "<p class=sottotitolo>Le tue pratiche e il tuo plafond.</p>",
              numeri([
                  ("Plafond disponibile", soldi(resta),
                   "su %s assegnati" % soldi(plafond.get("plafond", 0)),
                   "attenzione" if quota < 20 else "bene"),
                  ("In ballo", soldi(plafond.get("usato", 0)),
                   "%d pratiche aperte" % len(aperte)),
                  ("Da saldare", soldi(dovuto),
                   ("%d note" % len(da_saldare)) if da_saldare
                   else "niente in sospeso",
                   "attenzione" if dovuto else ""),
              ])]

    if da_saldare:
        righe = ["<tr><td>Settimana %s</td><td>%s</td>"
                 "<td class=destra>%s</td><td class=destra>"
                 "<a href='/nota/%s.pdf'>PDF</a></td></tr>"
                 % (_e(n.get("settimana", "")), _e(n.get("scadenza", "")),
                    _e(soldi(n.get("totale", 0))), _e(n.get("id", "")))
                 for n in da_saldare]
        dentro.append("<div class='carta stretta'><h2>Da saldare</h2>%s</div>"
                      % tabella([("Nota",), ("Entro il",), ("Importo", True),
                                 ("", True)], righe))

    dentro.append(
        "<div class='carta stretta'><h2>Le tue pratiche</h2>%s</div>"
        % tabella([("Targa",), ("Stato",), ("Aperta il",), ("Importo", True)],
                  [_riga_pratica(p) for p in pratiche],
                  "Nessuna pratica. Cerca una targa e comincia da lì."))

    if fatture:
        righe = ["<tr><td>n. %s</td><td>%s</td><td class=destra>%s</td>"
                 "<td class=destra><a href='/fattura/%s.pdf'>PDF</a></td></tr>"
                 % (_e(f.get("numero", "")), _e(data(f.get("quando"))),
                    _e(soldi(f.get("conti", {}).get("totale", 0))),
                    _e(f.get("id", "")))
                 for f in fatture]
        dentro.append("<div class='carta stretta'><h2>Fatture</h2>%s</div>"
                      % tabella([("Numero",), ("Data",), ("Totale", True),
                                 ("", True)], righe))

    coda = ["<a href='/cerca'>Cerca una targa</a>"]
    if da_saldare:
        coda.append("<a href='/estratto.pdf'>estratto conto</a>")
    dentro.append("<p class=nota>%s</p>" % " · ".join(coda))
    return telaio("Le tue pratiche", "".join(dentro), conto, "/area")


# ------------------------------------------------------ l'amministrazione

def amministrazione(conti_plafond: List[Dict[str, Any]],
                    note: List[Dict[str, Any]],
                    da_conteggiare: Dict[str, float],
                    messaggio: str = "",
                    fisco: Dict[str, Any] = None,
                    guasto_fisco: str = "",
                    fatture: List[Dict[str, Any]] = (),
                    conto: Dict[str, Any] = None) -> str:
    fisco = fisco or {}
    esposto = sum(float(c["usato"]) for c in conti_plafond)
    aperte = [n for n in note if not n.get("saldata")]
    scadute = [n for n in aperte
               if n.get("scade_il", 0) < time.time()]
    pronte = sum(da_conteggiare.values())

    dentro = ["<h1>Amministrazione</h1>",
              "<p class=sottotitolo>Plafond, conteggi e fatture.</p>"]
    if messaggio:
        dentro.append("<div class=avviso>%s</div>" % _e(messaggio))
    dentro.append(numeri([
        ("Esposizione", soldi(esposto),
         "su %d concessionarie" % len(conti_plafond)),
        ("Da conteggiare", soldi(pronte),
         "pratiche finite non ancora in nota",
         "bene" if pronte else ""),
        ("Note aperte", soldi(sum(float(n.get("totale") or 0)
                                  for n in aperte)),
         "%d in tutto" % len(aperte)),
        ("Scadute", len(scadute),
         "il lunedì è passato" if scadute else "nessuna",
         "attenzione" if scadute else ""),
    ]))

    if time.localtime().tm_wday == 5:
        dentro.append("<div class=avviso><b>È sabato</b> — giorno del "
                      "conteggio: le note emesse oggi vanno saldate entro "
                      "lunedì. L'orologio le manda da solo dalle 7.</div>")

    righe = []
    for c in conti_plafond:
        quanto_pronto = da_conteggiare.get(c["concessionaria"], 0)
        righe.append(
            "<tr><td><b>%s</b><div class=piccolo>%s</div></td>"
            "<td class=destra>%s</td><td class=destra>%s</td>"
            "<td class=destra>%s</td><td class=destra>%s</td>"
            "<td class=destra>%s</td></tr>"
            % (_e(c["nome"]), _e(c.get("posta") or "senza posta"),
               _e(soldi(c["plafond"])), _e(soldi(c["usato"])),
               _e(soldi(c["resta"])),
               ("<form action=/area/nota method=post>"
                "<input type=hidden name=concessionaria value='%s'>"
                "<button>Emetti %s</button></form>"
                % (_e(c["concessionaria"]), _e(soldi(quanto_pronto))))
               if quanto_pronto else "—",
               "<form action=/area/plafond method=post>"
               "<input type=hidden name=concessionaria value='%s'>"
               "<input name=plafond inputmode=decimal size=6 value='%s'>"
               "<input name=posta type=email size=16 placeholder=posta "
               "value='%s'><button class=piano>Salva</button></form>"
               % (_e(c["concessionaria"]), _e(numero(c["plafond"])),
                  _e(c.get("posta", "")))))
    dentro.append("<div class='carta stretta'><h2>Concessionarie</h2>%s</div>"
                  % tabella([("Concessionaria",), ("Plafond", True),
                             ("In ballo", True), ("Resta", True),
                             ("Conteggio", True), ("", True)],
                            righe, "Nessuna concessionaria."))

    if note:
        voci = []
        for n in note[:30]:
            saldata = n.get("saldata")
            voci.append(
                "<tr><td>%s</td><td>Settimana %s</td><td>%s</td>"
                "<td class=destra>%s</td><td class=destra>"
                "<a href='/nota/%s.pdf'>PDF</a></td><td class=destra>%s</td>"
                "</tr>"
                % (_e(n.get("concessionaria", "")), _e(n.get("settimana", "")),
                   ("<span class='bollo fatto'>saldata</span>" if saldata
                    else ("<span class='bollo male'>scaduta</span>"
                          if n.get("scade_il", 0) < time.time()
                          else "<span class='bollo attesa'>da saldare</span>")),
                   _e(soldi(n.get("totale", 0))), _e(n.get("id", "")),
                   ("—" if saldata else
                    "<form action=/area/saldo method=post>"
                    "<input type=hidden name=nota value='%s'>"
                    "<button class=piano>Segna saldata</button></form>"
                    % _e(n.get("id", "")))))
        dentro.append("<div class='carta stretta'><h2>Note di saldo</h2>%s"
                      "</div>" % tabella([("Concessionaria",), ("Nota",),
                                          ("Stato",), ("Totale", True),
                                          ("", True), ("", True)], voci))

    if fatture:
        voci = ["<tr><td>n. %s</td><td>%s</td><td>%s</td>"
                "<td class=destra>%s</td><td class=destra>"
                "<a href='/fattura/%s.pdf'>PDF</a></td></tr>"
                % (_e(f.get("numero", "")), _e(f.get("concessionaria", "")),
                   _e(data(f.get("quando"))),
                   _e(soldi(f.get("conti", {}).get("totale", 0))),
                   _e(f.get("id", ""))) for f in fatture[:20]]
        dentro.append("<div class='carta stretta'><h2>Fatture</h2>%s</div>"
                      % tabella([("Numero",), ("Concessionaria",), ("Data",),
                                 ("Totale", True), ("", True)], voci))

    # I dati fiscali: senza questi la piattaforma NON emette fatture, e lo
    # dice qui invece di scoprirlo il sabato mattina.
    campi = [("ragione_sociale", "Ragione sociale"), ("piva", "Partita IVA"),
             ("codice_fiscale", "Codice fiscale"), ("indirizzo", "Indirizzo"),
             ("cap", "CAP"), ("citta", "Città"), ("provincia", "Provincia"),
             ("iban", "IBAN"), ("iva", "Aliquota IVA %")]
    moduli = "".join("<input name='%s' placeholder='%s' value='%s'>"
                     % (_e(c), _e(n), _e(fisco.get(c, "")))
                     for c, n in campi)
    compensi = "".join(
        "<input name='compenso_%s' inputmode=decimal "
        "placeholder='Compenso — %s' value='%s'>"
        % (_e(chiave), _e(voce["nome"]),
           _e((fisco.get("compensi") or {}).get(chiave, "")))
        for chiave, voce in TIPI.items())
    dentro.append(
        "<div class=carta><h2>Dati per le fatture</h2>%s"
        "<form action=/area/fisco method=post class='dritto largo'>%s%s"
        "<button>Salva</button></form>"
        "<p class=nota>Il <b>compenso</b> è la parte imponibile: il resto "
        "dell'importo è anticipazione in nome e per conto (art. 15 DPR "
        "633/72), fuori campo IVA. Quanto sia, lo dice il commercialista."
        "</p></div>"
        % (("<div class='avviso male'>%s</div>" % _e(guasto_fisco))
           if guasto_fisco else "", moduli, compensi))

    dentro.append(
        "<div class=carta><h2>Conto nuovo</h2>"
        "<form action=/area/conto method=post class=dritto>"
        "<input name=utente placeholder='Nome utente' autocapitalize=none "
        "required>"
        "<input name=parola type=password placeholder=\"Parola d'ordine "
        "(almeno 8)\" required>"
        "<input name=nome placeholder='Nome da mostrare'>"
        "<input name=concessionaria placeholder='Concessionaria: id breve, "
        "es. rossi'>"
        "<input name=posta type=email placeholder='Posta della "
        "concessionaria'>"
        "<button>Crea concessionaria</button></form>"
        "<p class=nota>Il conto di una concessionaria porta con sé il suo "
        "identificativo: è quello che lega le pratiche al plafond.</p></div>")
    return telaio("Amministrazione", "".join(dentro), conto, "/area")
