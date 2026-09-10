#!/usr/bin/env python3
"""Targhe: il server.

    python3 server.py                 # http://127.0.0.1:8073
    python3 server.py --finto         # col fornitore finto: non spende niente

Due rotte e basta:

    GET /?targa=AB123CD      la pagina, o la scheda
    GET /?targa=AB123CD&massa=1400   la stessa, col conto dei neopatentati
    GET /targa/AB123CD       la stessa scheda
    GET /pratica/nuova?tipo=mini&targa=AB123CD   apre una pratica
    GET /pratica/<id>        i documenti che servono, e dove si caricano
    POST /pratica/<id>       ci arriva un documento, o un messaggio
    GET /entra, /esci        chi sei
    GET /area                le tue pratiche, o quelle di tutti, o i conti

La seconda esiste per gli indirizzi da condividere. **Tutte e due
rispondono in JSON a chi manda `Accept: application/json`**: e' la regola
di Ops! («stesse rotte del web, vestito diverso»), e serve alle schermate
native che verranno — un'API parallela sarebbe una seconda verita' da
tenere allineata.

Non espone niente a internet di suo: ascolta su 127.0.0.1 e vuole un
reverse proxy davanti, che faccia HTTPS. E **non ha una pagina per
incollare il token**: finche' non c'e' un'amministrazione con
un'identita' dietro, una pagina del genere sarebbe un modulo che regala
le nostre credenziali a chiunque arrivi alla porta. Il token si mette
nell'ambiente (`TOKEN_VEICOLI`), o si salva col programma.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
from email.parser import BytesParser
from email.policy import default as politica
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

# L'ora del prodotto e' l'ora d'ITALIA, fissata prima che qualunque modulo
# guardi l'orologio — la stessa cicatrice di Ops!, dove le ore uscivano
# indietro di due. Si guarda il VALORE e non la presenza: un TZ vuoto
# (capita nelle unita' systemd) vorrebbe dire UTC, cioe' il difetto che
# torna in silenzio.
if not os.environ.get("TZ"):
    os.environ["TZ"] = "Europe/Rome"
time.tzset()

from pagine import area as veste_area        # noqa: E402
from pagine import pratica as veste_pratica  # noqa: E402
from pagine import scheda as veste           # noqa: E402
from veicoli import (cliente, conteggio, conti, fatture, orologio,  # noqa: E402
                     posta, pratiche)


# Quanto corpo si accetta in una volta. Il documento singolo ha il suo
# tetto in `pratiche.PESO_MASSIMO`; questo e' il tetto della busta, e serve
# a non tenere in memoria quel che qualcuno manda per gioco.
BUSTA_MASSIMA = 12 * 1024 * 1024


class Porta(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Targhe"

    def log_message(self, forma, *argomenti):
        # Una riga per richiesta, con l'ora d'Italia. Le targhe cercate NON
        # si scrivono nel registro: e' un dato personale indiretto, e un
        # registro pieno di targhe e' un archivio che nessuno ha chiesto.
        print("%s %s %s" % (time.strftime("%H:%M:%S"),
                            self.command, self.path.split("?")[0]),
              flush=True)

    # ------------------------------------------------------------ risposte

    # ------------------------------------------------------------- chi c'e'

    def _chiave(self) -> str:
        """La chiave di sessione dal biscotto. Niente libreria: un biscotto
        e' `nome=valore; altro=valore`, e leggerlo a mano evita di dover
        spiegare un modulo intero a chi legge questa riga."""
        for pezzo in (self.headers.get("Cookie") or "").split(";"):
            nome, _, valore = pezzo.strip().partition("=")
            if nome == "chiave":
                return valore.strip()
        return ""

    def _conto(self):
        return conti.chi(self.server.dati, self._chiave())

    def _da_fuori(self) -> bool:
        """Se questa POST arriva da un'altra casa.

        Il biscotto e' `SameSite=Lax`, che gia' non parte per le richieste
        di terzi; questo e' il secondo giro di chiave: un `Origin` che non
        e' il nostro non entra. Le due cose insieme sono la difesa contro
        il modulo nascosto in un'altra pagina che fa fare a chi e' entrato
        quello che non voleva fare.
        """
        origine = self.headers.get("Origin")
        if not origine:
            return False
        casa = self.headers.get("Host", "")
        return not (origine.endswith("//" + casa)
                    or origine.endswith("://" + casa))

    def _vuole_json(self) -> bool:
        """Se chi chiama vuole i dati e non la pagina: e' l'app nativa."""
        return "application/json" in (self.headers.get("Accept") or "")

    def _manda(self, codice: int, tipo: str, corpo: bytes) -> None:
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # La pagina non carica niente da fuori e non ne ha bisogno: dirlo
        # qui vuol dire che un campo storpiato del fornitore non puo'
        # diventare uno script nemmeno se un giorno sfugge a `html.escape`.
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; "
                         "form-action 'self'")
        self.end_headers()
        self.wfile.write(corpo)

    def _biscotto(self, chiave: str, spegni: bool = False) -> str:
        pezzi = ["chiave=%s" % (chiave if not spegni else ""),
                 "Path=/", "HttpOnly", "SameSite=Lax",
                 "Max-Age=%d" % (0 if spegni else conti.DURATA)]
        # `Secure` solo se davanti c'e' HTTPS: metterlo sempre spegnerebbe
        # l'accesso sul banco, che gira in chiaro su 127.0.0.1.
        if (self.headers.get("X-Forwarded-Proto") or "").lower() == "https":
            pezzi.append("Secure")
        return "; ".join(pezzi)

    def _rimanda(self, dove: str, biscotto: str = "") -> None:
        self.send_response(303)
        self.send_header("Location", dove)
        if biscotto:
            self.send_header("Set-Cookie", biscotto)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _pagina(self, testo: str, codice: int = 200) -> None:
        self._manda(codice, "text/html; charset=utf-8", testo.encode("utf-8"))

    def _json(self, roba: Any, codice: int = 200) -> None:
        self._manda(codice, "application/json; charset=utf-8",
                    json.dumps(roba, ensure_ascii=False).encode("utf-8"))

    # -------------------------------------------------------------- rotte

    def do_GET(self):
        pezzi = urllib.parse.urlsplit(self.path)
        campi = urllib.parse.parse_qs(pezzi.query)
        strada = pezzi.path

        if strada == "/salute":
            # Per il monitor: dice se il servizio puo' lavorare, senza
            # spendere una chiamata per scoprirlo.
            return self._json({"in_piedi": True,
                               "configurato": cliente.configurato(self.server.dati),
                               "token_da": cliente.da_dove(self.server.dati)})

        if strada == "/entra":
            return self._pagina(veste_area.entra())
        if strada == "/esci":
            conti.esci(self.server.dati, self._chiave())
            return self._rimanda("/entra", self._biscotto("", spegni=True))
        if strada == "/area":
            return self._area()
        if strada == "/estratto.pdf":
            conto = self._conto()
            if not conto or conto.get("ruolo") != "concessionaria":
                return self._pagina(veste_area.entra(
                    "Entra come concessionaria per l'estratto conto."), 401)
            quale = conto.get("concessionaria", "")
            dentro = conti.concessionaria(self.server.dati, quale)
            dato = conteggio.estratto(
                quale, dentro.get("nome", quale),
                conteggio.da_saldare(self.server.note, quale))
            return self._carta(dato, "estratto-conto.pdf")

        if strada.startswith("/fattura/") and strada.endswith(".pdf"):
            quale = strada[len("/fattura/"):-len(".pdf")]
            try:
                conto = self._conto()
                fattura = fatture.leggi(self.server.fatture, quale)
                suo = (conto or {}).get("ruolo") == "concessionaria" and \
                    conto.get("concessionaria") == fattura.get("concessionaria")
                if not conto or not (conto.get("ruolo") == "amministrazione"
                                     or suo):
                    raise fatture.FatturaRifiutata("Questa fattura non esiste.")
                return self._carta(fatture.carta(self.server.fatture, quale),
                                   "fattura-%s.pdf"
                                   % fattura.get("numero", "").replace("/", "-"))
            except fatture.FatturaRifiutata as e:
                if self._vuole_json():
                    return self._json({"errore": e.utente}, 404)
                return self._pagina(veste_area.entra(e.utente), 404)

        if strada.startswith("/nota/") and strada.endswith(".pdf"):
            try:
                return self._nota_in_pdf(
                    strada[len("/nota/"):-len(".pdf")])
            except conteggio.ConteggioRifiutato as e:
                if self._vuole_json():
                    return self._json({"errore": e.utente}, 404)
                return self._pagina(veste_area.entra(e.utente), 404)

        if strada == "/pratica/nuova":
            tipo = (campi.get("tipo") or [""])[0]
            targa = (campi.get("targa") or [""])[0].upper()
            conto = self._conto()
            if not conto or conto.get("ruolo") != "concessionaria":
                # Le pratiche le apre una concessionaria, perche' una
                # pratica consuma un plafond, e il plafond ha un nome.
                if self._vuole_json():
                    return self._json({"errore": "Entra come "
                                       "concessionaria."}, 401)
                return self._pagina(veste_area.entra(
                    "Per aprire una pratica entra come concessionaria."), 401)
            try:
                # Il prezzo si prende dalla scheda gia' cercata: e' in
                # memoria, quindi non costa una seconda chiamata. Se la
                # targa non e' mai stata cercata, la pratica parte senza
                # prezzo e il conteggio lo mettera' l'agenzia.
                prezzo, kw = 0.0, None
                try:
                    dati_veicolo = cliente.scheda(
                        targa, dati=self.server.dati,
                        cartella=self.server.memoria,
                        con_assicurazione=False)
                    kw = dati_veicolo.get("kw")
                    prezzo = (dati_veicolo.get("passaggio") or {}).get("euro") or 0.0
                except cliente.VeicoloRifiutato:
                    pass
                conteggio.puo_aprire(self.server.dati, self.server.pratiche,
                                     conto["concessionaria"], prezzo)
                identificativo = pratiche.apri(self.server.pratiche, tipo,
                                               targa,
                                               conto["concessionaria"],
                                               prezzo, kw)
            except (pratiche.PraticaRifiutata,
                    conteggio.ConteggioRifiutato) as e:
                if self._vuole_json():
                    return self._json({"errore": e.utente}, 400)
                return self._pagina(veste.ricerca(e.utente, targa), 400)
            if self._vuole_json():
                return self._json({"id": identificativo}, 201)
            # Si rimanda alla pratica: cosi' l'indirizzo nella barra e' gia'
            # quello da tenere, e un ricarica non apre una pratica nuova.
            self.send_response(303)
            self.send_header("Location", "/pratica/" + identificativo)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if strada.startswith("/pratica/"):
            resto = strada[len("/pratica/"):].strip("/")
            if "/" in resto:
                # /pratica/<id>/documento/<chiave>: il file vero.
                pezzi = resto.split("/")
                try:
                    if len(pezzi) != 3 or pezzi[1] != "documento":
                        raise pratiche.PraticaRifiutata("Non esiste.")
                    return self._documento(pezzi[0], pezzi[2])
                except pratiche.PraticaRifiutata as e:
                    if self._vuole_json():
                        return self._json({"errore": e.utente}, 404)
                    return self._pagina(veste.ricerca(e.utente), 404)
            try:
                return self._pratica(resto)
            except pratiche.PraticaRifiutata as e:
                if self._vuole_json():
                    return self._json({"errore": e.utente}, 404)
                return self._pagina(veste.ricerca(e.utente), 404)

        targa = ""
        if strada.startswith("/targa/"):
            targa = urllib.parse.unquote(strada[len("/targa/"):])
        elif strada == "/":
            targa = (campi.get("targa") or [""])[0]
        else:
            if self._vuole_json():
                return self._json({"errore": "non esiste"}, 404)
            return self._pagina(veste.ricerca("Questa pagina non esiste."), 404)

        if not targa.strip():
            if self._vuole_json():
                return self._json({"errore": "manca la targa"}, 400)
            return self._pagina(veste.ricerca())

        fresco = (campi.get("fresco") or ["0"])[0] == "1"
        # La massa la scrive chi guarda, dal libretto: il fornitore non la
        # manda e senza non si chiude il conto dei neopatentati. Una massa
        # storpiata non deve far esplodere niente — vale come «non detta».
        try:
            massa = float((campi.get("massa") or ["0"])[0].replace(",", "."))
        except ValueError:
            massa = 0.0
        try:
            dati = cliente.scheda(targa, dati=self.server.dati,
                                  cartella=self.server.memoria, fresco=fresco,
                                  massa=massa or None)
        except cliente.VeicoloRifiutato as e:
            # Il codice HTTP segue il senso: una targa che non risulta e'
            # un 404, un credito finito e' un 502 (il guasto e' nostro, non
            # di chi chiede). Le schermate native ci si appoggiano.
            codice = 404 if e.codice == 404 else (400 if not e.codice else 502)
            if self._vuole_json():
                return self._json({"errore": e.utente}, codice)
            return self._pagina(veste.ricerca(e.utente, targa), codice)

        if self._vuole_json():
            return self._json(dati)
        return self._pagina(veste.scheda(dati))

    # ---------------------------------------------------------- le pratiche

    def _corpo(self) -> bytes:
        """Il corpo della richiesta, con un tetto. Oltre il tetto si taglia:
        leggere quel che il mittente dichiara senza un limite e' il modo
        classico di far finire la memoria a un server."""
        quanto = int(self.headers.get("Content-Length") or 0)
        if quanto <= 0:
            return b""
        if quanto > BUSTA_MASSIMA:
            raise pratiche.PraticaRifiutata(
                "Il file è troppo grande: al massimo %d MB."
                % (pratiche.PESO_MASSIMO // (1024 * 1024)))
        return self.rfile.read(quanto)

    def _pezzi_del_modulo(self, corpo: bytes) -> Dict[str, Any]:
        """Il modulo caricato dal telefono, smontato nei suoi pezzi.

        Il multipart lo legge la libreria della posta elettronica, che e'
        la stessa grammatica e la sa da trent'anni: scrivere a mano un
        lettore di confini e' il posto dove ci si taglia."""
        tipo = self.headers.get("Content-Type", "")
        if not tipo.startswith("multipart/form-data"):
            # Un modulo semplice: campo=valore, senza file.
            campi = urllib.parse.parse_qs(corpo.decode("utf-8", "replace"))
            return {k: v[0] for k, v in campi.items()}
        testa = ("Content-Type: %s\r\nMIME-Version: 1.0\r\n\r\n"
                 % tipo).encode("utf-8")
        messaggio = BytesParser(policy=politica).parsebytes(testa + corpo)
        fuori: Dict[str, Any] = {}
        for pezzo in messaggio.iter_parts():
            nome = pezzo.get_param("name", header="content-disposition")
            if not nome:
                continue
            dato = pezzo.get_payload(decode=True) or b""
            file_dato = pezzo.get_filename()
            if file_dato is not None:
                fuori[nome] = dato
                fuori[nome + "__nome"] = file_dato
            else:
                fuori[nome] = dato.decode("utf-8", "replace")
        return fuori

    def _pratica(self, identificativo: str, messaggio: str = "",
                 codice: int = 200) -> None:
        p = pratiche.leggi(self.server.pratiche, identificativo)
        conto = self._conto()
        if not pratiche.puo_vedere(p, conto):
            # Stessa risposta di una pratica che non esiste: dire «esiste ma
            # non e' tua» racconta a uno sconosciuto che quella pratica c'e'.
            raise pratiche.PraticaRifiutata("Questa pratica non esiste.")
        if self._vuole_json():
            return self._json(p, codice)
        return self._pagina(
            veste_pratica.pratica(p, pratiche.TIPI[p["tipo"]], messaggio,
                                  conto, pratiche.DOCUMENTI_AGENZIA),
            codice)

    def do_POST(self):
        strada = urllib.parse.urlsplit(self.path).path
        if self._da_fuori():
            return self._manda(403, "text/plain; charset=utf-8",
                               "modulo mandato da un'altra pagina"
                               .encode("utf-8"))
        try:
            if strada == "/entra":
                return self._fai_entrare()
            if strada.startswith("/area/"):
                return self._azione_area(strada)
        except (conti.ContoRifiutato, conteggio.ConteggioRifiutato) as e:
            return self._area(e.utente)

        if not strada.startswith("/pratica/"):
            return self._manda(404, "text/plain; charset=utf-8", b"non esiste")
        identificativo = strada[len("/pratica/"):].strip("/")
        try:
            conto = self._conto()
            if not conto:
                raise pratiche.PraticaRifiutata("Entra per lavorare su una "
                                                "pratica.")
            p = pratiche.leggi(self.server.pratiche, identificativo)
            if not pratiche.puo_vedere(p, conto):
                raise pratiche.PraticaRifiutata("Questa pratica non esiste.")
            pezzi = self._pezzi_del_modulo(self._corpo())
            if "messaggio" in pezzi:
                pratiche.messaggio(self.server.pratiche, identificativo,
                                   conto, str(pezzi["messaggio"]))
                return self._pratica(identificativo)
            if "chiudi" in pezzi:
                if conto.get("ruolo") != "agenzia":
                    raise pratiche.PraticaRifiutata(
                        "Solo l'agenzia può chiudere una pratica.")
                pratiche.chiudi(self.server.pratiche, identificativo)
                return self._pratica(identificativo, "Pratica chiusa.")
            quale_documento = str(pezzi.get("documento") or "")
            se_agenzia = quale_documento in {c for c, _
                                             in pratiche.DOCUMENTI_AGENZIA}
            if se_agenzia and conto.get("ruolo") != "agenzia":
                raise pratiche.PraticaRifiutata(
                    "Questi documenti li carica l'agenzia.")
            if not se_agenzia and conto.get("ruolo") == "agenzia":
                raise pratiche.PraticaRifiutata(
                    "I documenti della concessionaria li carica lei.")
            if "motivo" in pezzi:
                pratiche.scrivi_motivo(self.server.pratiche, identificativo,
                                       str(pezzi["motivo"]))
                return self._pratica(identificativo, "Motivo salvato.")
            quale = quale_documento
            dato = pezzi.get("file") or b""
            if not isinstance(dato, bytes):
                dato = b""
            pratiche.aggiungi(self.server.pratiche, identificativo, quale,
                              dato, str(pezzi.get("file__nome") or ""))
        except pratiche.PraticaRifiutata as e:
            if self._vuole_json():
                return self._json({"errore": e.utente}, 400)
            try:
                return self._pratica(identificativo, e.utente, 400)
            except pratiche.PraticaRifiutata:
                return self._pagina(veste.ricerca(e.utente), 404)
        return self._pratica(identificativo, "Documento arrivato.")

    def _nota_in_pdf(self, identificativo: str) -> None:
        """Il PDF di una nota, a chi ha titolo di leggerlo.

        L'amministrazione tutte; una concessionaria **solo le sue**. Come
        per le pratiche, a chi non ha titolo si risponde «non esiste».
        """
        conto = self._conto()
        nota = conteggio.leggi(self.server.note, identificativo)
        suo = (conto or {}).get("ruolo") == "concessionaria" and \
            conto.get("concessionaria") == nota.get("concessionaria")
        if not conto or not (conto.get("ruolo") in ("agenzia",
                                                    "amministrazione") or suo):
            raise conteggio.ConteggioRifiutato("Questa nota non esiste.")
        return self._carta(conteggio.carta(self.server.note, identificativo),
                           "nota-%s.pdf" % nota.get("settimana", "saldo"))

    def _carta(self, dato: bytes, nome: str) -> None:
        """Un PDF a chi ha gia' avuto il permesso di riceverlo.

        I permessi li ha controllati chi chiama: questa funzione veste e
        basta. `sandbox` e `nosniff` valgono anche per un documento che
        abbiamo fabbricato noi — costano niente, e il giorno che il PDF
        arriva da qualcun altro la difesa e' gia' li'."""
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(dato)))
        self.send_header("Content-Disposition",
                         "inline; filename=\"%s\"" % nome)
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; sandbox")
        self.end_headers()
        self.wfile.write(dato)

    def _documento(self, identificativo: str, chiave: str) -> None:
        """Un documento caricato, rimandato a chi ha il diritto di vederlo.

        L'agenzia deve poter LEGGERE la visura, senno' non puo' lavorarla:
        e' il motivo per cui questa rotta esiste. Le difese, tutte insieme:
        si passa da `puo_vedere`, quindi una concessionaria non arriva ai
        documenti di un'altra; il tipo e' quello che abbiamo stabilito noi
        guardando i byte; `nosniff` impedisce al browser di indovinarne un
        altro; e la regola dei contenuti spegne qualunque cosa il file
        provasse a eseguire.
        """
        pratica = pratiche.leggi(self.server.pratiche, identificativo)
        if not pratiche.puo_vedere(pratica, self._conto()):
            raise pratiche.PraticaRifiutata("Questo documento non c'è.")
        dato, roba, nome = pratiche.documento(self.server.pratiche,
                                              identificativo, chiave)
        tipi = {"jpg": "image/jpeg", "png": "image/png", "pdf": "application/pdf",
                "heic": "image/heic"}
        self.send_response(200)
        self.send_header("Content-Type", tipi.get(roba,
                                                  "application/octet-stream"))
        self.send_header("Content-Length", str(len(dato)))
        self.send_header("Content-Disposition",
                         "inline; filename=\"%s.%s\"" % (chiave, roba))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; sandbox")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(dato)

    # ----------------------------------------------------------- le aree

    def _fai_entrare(self) -> None:
        pezzi = self._pezzi_del_modulo(self._corpo())
        conto = conti.prova(self.server.dati, str(pezzi.get("utente") or ""),
                            str(pezzi.get("parola") or ""))
        if not conto:
            # Una frase sola per tutti i casi: dire quale dei due era
            # sbagliato regala meta' della risposta a chi tenta.
            return self._pagina(veste_area.entra(
                "Nome utente o parola d'ordine non giusti."), 401)
        chiave = conti.entra(self.server.dati, conto)
        return self._rimanda("/area", self._biscotto(chiave))

    def _area(self, messaggio: str = "") -> None:
        conto = self._conto()
        if not conto:
            return self._pagina(veste_area.entra(messaggio), 401)
        ruolo = conto.get("ruolo")
        if ruolo == "agenzia":
            return self._pagina(veste_area.agenzia(
                pratiche.per_concessionaria(self.server.pratiche),
                conti.concessionarie(self.server.dati)))
        if ruolo == "amministrazione":
            plafond = [conteggio.quanto_resta(self.server.dati,
                                              self.server.pratiche, c)
                       for c in sorted(conti.concessionarie(self.server.dati))]
            pronte = {}
            for c in conti.concessionarie(self.server.dati):
                finite = pratiche.elenco(self.server.pratiche, c, "finita")
                if finite:
                    pronte[c] = round(sum(float(p.get("prezzo") or 0)
                                          for p in finite), 2)
            return self._pagina(veste_area.amministrazione(
                plafond, conteggio.note(self.server.note), pronte, messaggio,
                fatture.fisco(self.server.dati),
                fatture.pronto(self.server.dati),
                fatture.elenco(self.server.fatture)))
        suo = conto.get("concessionaria", "")
        return self._pagina(veste_area.concessionaria(
            pratiche.elenco(self.server.pratiche, suo),
            conteggio.quanto_resta(self.server.dati, self.server.pratiche, suo),
            conteggio.note(self.server.note, suo),
            fatture.elenco(self.server.fatture, suo)))

    def _azione_area(self, strada: str) -> None:
        conto = self._conto()
        if not conto or conto.get("ruolo") != "amministrazione":
            # Il plafond e le note li muove solo l'amministrazione. Non e'
            # una questione di schermate nascoste: la rotta stessa dice di no.
            return self._pagina(veste_area.entra(
                "Serve l'amministrazione per questo."), 403)
        pezzi = self._pezzi_del_modulo(self._corpo())
        if strada == "/area/plafond":
            quale = str(pezzi.get("concessionaria") or "")
            gia = conti.concessionaria(self.server.dati, quale)
            try:
                quanto = float(str(pezzi.get("plafond") or "0")
                               .replace(".", "").replace(",", "."))
            except ValueError:
                return self._area("Il plafond dev'essere un numero.")
            conti.salva_concessionaria(self.server.dati, quale,
                                       gia.get("nome", quale), quanto,
                                       str(pezzi.get("posta") or ""))
            return self._area("Plafond aggiornato.")
        if strada == "/area/nota":
            quale = str(pezzi.get("concessionaria") or "")
            dentro = conti.concessionaria(self.server.dati, quale)
            nota = conteggio.emetti(self.server.note, self.server.pratiche,
                                    quale, dentro.get("nome", quale))
            # Il PDF c'e' comunque: la posta e' il modo di farlo arrivare,
            # non il posto dove vive. Se non parte, la nota resta nell'area
            # della concessionaria e lo si dice, invece di far finta.
            detto = "Nota emessa: %.2f €." % nota["totale"]
            try:
                partita = posta.manda(
                    dentro.get("posta", ""),
                    "Nota di saldo — settimana %s" % nota["settimana"],
                    "In allegato la nota di saldo della settimana %s, "
                    "di %.2f €.\n\nDa saldare entro lunedì %s.\n"
                    % (nota["settimana"], nota["totale"],
                       conteggio.entro_quando(nota["quando"])),
                    conteggio.carta(self.server.note, nota["id"]),
                    "nota-%s.pdf" % nota["settimana"])
                detto += (" Mandata per posta a %s." % dentro.get("posta")
                          if partita else "")
            except posta.PostaRifiutata as e:
                detto += " " + e.utente
            return self._area(detto)
        if strada == "/area/saldo":
            conteggio.segna_saldata(self.server.note, self.server.pratiche,
                                    str(pezzi.get("nota") or ""))
            return self._area("Saldo registrato: il plafond è tornato libero.")
        if strada == "/area/fisco":
            fatture.salva_fisco(self.server.dati,
                                {k: v for k, v in pezzi.items()
                                 if isinstance(v, str)})
            guasto = fatture.pronto(self.server.dati)
            return self._area(guasto or "Dati fiscali salvati.")
        if strada == "/area/conto":
            quale = str(pezzi.get("concessionaria") or "").strip().lower()
            if quale:
                conti.salva_concessionaria(
                    self.server.dati, quale,
                    str(pezzi.get("nome") or quale),
                    conti.concessionaria(self.server.dati,
                                         quale).get("plafond", 0),
                    str(pezzi.get("posta") or ""))
            conti.crea(self.server.dati, str(pezzi.get("utente") or ""),
                       str(pezzi.get("parola") or ""),
                       str(pezzi.get("ruolo") or "concessionaria"),
                       quale, str(pezzi.get("nome") or ""))
            return self._area("Conto creato.")
        return self._area()

    def do_HEAD(self):
        self.do_GET()


def _fai_battere(dati: Path, pratiche_dove: Path, note_dove: Path,
                 fatture_dove: Path) -> None:
    """Il filo che tiene l'ora: un giro all'ora, per sempre.

    Un'ora e' il passo giusto per due appuntamenti che guardano il giorno
    della settimana: piu' fitto non serve a niente, e piu' rado rischia di
    saltare la finestra del sabato mattina se il server viene riavviato.

    Il giro non deve MAI far cadere il filo: un guasto dentro un giro si
    scrive e si aspetta il prossimo. Un orologio che si ferma alla prima
    posta rifiutata e' un orologio che nessuno si accorge che e' fermo.
    """
    def battito():
        while True:
            try:
                fatto = orologio.giro(dati, pratiche_dove, note_dove,
                                      fatture_dove)
                if any(fatto.values()):
                    print("%s orologio: %s"
                          % (time.strftime("%H:%M:%S"),
                             json.dumps(fatto, ensure_ascii=False)),
                          flush=True)
            except Exception as e:                      # noqa: BLE001
                print("%s orologio, guasto: %s"
                      % (time.strftime("%H:%M:%S"), e), flush=True)
            time.sleep(3600)

    filo = threading.Thread(target=battito, daemon=True)
    filo.start()


def main() -> int:
    ragioni = argparse.ArgumentParser(description="Targhe")
    ragioni.add_argument("--porta", type=int, default=8073)
    ragioni.add_argument("--dati", default="dati",
                         help="dove sta il token salvato")
    ragioni.add_argument("--memoria", default="dati/memoria",
                         help="dove si ricordano le risposte")
    ragioni.add_argument("--pratiche", default="dati/pratiche",
                         help="dove stanno le pratiche e i documenti")
    ragioni.add_argument("--note", default="dati/note",
                         help="dove stanno le note di saldo")
    ragioni.add_argument("--fatture", default="dati/fatture",
                         help="dove stanno le fatture")
    ragioni.add_argument("--giro", action="store_true",
                         help="fa UN giro dell'orologio e chiude: per la "
                              "prova a mano, o per un cron esterno")
    ragioni.add_argument("--senza-orologio", action="store_true",
                         help="non far girare l'orologio (per il banco)")
    ragioni.add_argument("--finto", action="store_true",
                         help="parla col fornitore finto: non spende niente")
    detto = ragioni.parse_args()

    if detto.finto:
        # Il banco in una riga: fa partire il finto qui dentro, cosi' non
        # servono due terminali per vedere la pagina funzionare.
        import threading
        sys.path.insert(0, str(Path(__file__).resolve().parent / "strumenti"))
        import finto_openapi
        porta_finta = detto.porta + 1
        finto = ThreadingHTTPServer(("127.0.0.1", porta_finta),
                                    finto_openapi.H)
        threading.Thread(target=finto.serve_forever, daemon=True).start()
        os.environ["BASE_VEICOLI"] = "http://127.0.0.1:%d" % porta_finta
        os.environ.setdefault("TOKEN_VEICOLI", "finto")
        print("fornitore FINTO su :%d — non si spende niente" % porta_finta,
              flush=True)

    dati = Path(detto.dati)
    dati.mkdir(parents=True, exist_ok=True)
    memoria = Path(detto.memoria)
    memoria.mkdir(parents=True, exist_ok=True)
    # I documenti d'identita' non stanno con tutto il resto, e la cartella
    # la legge solo chi fa girare il programma.
    pratiche_dove = Path(detto.pratiche)
    pratiche_dove.mkdir(parents=True, exist_ok=True)
    os.chmod(pratiche_dove, 0o700)

    server = ThreadingHTTPServer(("127.0.0.1", detto.porta), Porta)
    server.dati = dati
    server.memoria = memoria
    server.pratiche = pratiche_dove
    note_dove = Path(detto.note)
    note_dove.mkdir(parents=True, exist_ok=True)
    os.chmod(note_dove, 0o700)
    server.note = note_dove
    fatture_dove = Path(detto.fatture)
    fatture_dove.mkdir(parents=True, exist_ok=True)
    os.chmod(fatture_dove, 0o700)
    server.fatture = fatture_dove

    if detto.giro:
        # Un giro solo e poi si chiude: serve a provarlo a mano, e a chi
        # preferisce farlo battere da un cron di sistema invece che dal
        # filo qui dentro.
        fatto = orologio.giro(dati, pratiche_dove, note_dove, fatture_dove)
        print(json.dumps(fatto, ensure_ascii=False, indent=2))
        return 0
    if not conti.conti(dati):
        # Il primo conto non si puo' creare da dentro: senza
        # amministrazione non c'e' nessuno che possa farne una.
        print("Nessun conto. Il primo si fa cosi':\n"
              "  python3 strumenti/primo_conto.py %s\n"
              "(chiede tutto lui, e la parola d'ordine non si vede)"
              % dati, flush=True)
    if not cliente.configurato(dati):
        print("ATTENZIONE: nessun token. Ogni ricerca fallirà con una "
              "frase che lo spiega. Si mette in TOKEN_VEICOLI, oppure si "
              "prova con --finto.", flush=True)
    if not detto.senza_orologio:
        _fai_battere(dati, pratiche_dove, note_dove, fatture_dove)
    print("Targhe su http://127.0.0.1:%d" % detto.porta, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nchiuso", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
