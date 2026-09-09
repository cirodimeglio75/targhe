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
    POST /pratica/<id>       ci arriva un documento

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

from pagine import pratica as veste_pratica  # noqa: E402
from pagine import scheda as veste           # noqa: E402
from veicoli import cliente, pratiche        # noqa: E402


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

        if strada == "/pratica/nuova":
            tipo = (campi.get("tipo") or [""])[0]
            targa = (campi.get("targa") or [""])[0].upper()
            try:
                identificativo = pratiche.apri(self.server.pratiche, tipo,
                                               targa)
            except pratiche.PraticaRifiutata as e:
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
            try:
                return self._pratica(strada[len("/pratica/"):].strip("/"))
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
        if self._vuole_json():
            return self._json(p, codice)
        return self._pagina(
            veste_pratica.pratica(p, pratiche.TIPI[p["tipo"]], messaggio),
            codice)

    def do_POST(self):
        strada = urllib.parse.urlsplit(self.path).path
        if not strada.startswith("/pratica/"):
            return self._manda(404, "text/plain; charset=utf-8", b"non esiste")
        identificativo = strada[len("/pratica/"):].strip("/")
        try:
            pezzi = self._pezzi_del_modulo(self._corpo())
            if "motivo" in pezzi:
                pratiche.scrivi_motivo(self.server.pratiche, identificativo,
                                       str(pezzi["motivo"]))
                return self._pratica(identificativo, "Motivo salvato.")
            quale = str(pezzi.get("documento") or "")
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

    def do_HEAD(self):
        self.do_GET()


def main() -> int:
    ragioni = argparse.ArgumentParser(description="Targhe")
    ragioni.add_argument("--porta", type=int, default=8073)
    ragioni.add_argument("--dati", default="dati",
                         help="dove sta il token salvato")
    ragioni.add_argument("--memoria", default="dati/memoria",
                         help="dove si ricordano le risposte")
    ragioni.add_argument("--pratiche", default="dati/pratiche",
                         help="dove stanno le pratiche e i documenti")
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
    if not cliente.configurato(dati):
        print("ATTENZIONE: nessun token. Ogni ricerca fallirà con una "
              "frase che lo spiega. Si mette in TOKEN_VEICOLI, oppure si "
              "prova con --finto.", flush=True)
    print("Targhe su http://127.0.0.1:%d" % detto.porta, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nchiuso", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
