#!/usr/bin/env python3
"""Il banco delle pratiche: i documenti che si caricano.

    python3 prove/prova_pratiche.py

Qui dentro passano documenti d'identita', quindi i controlli non sono sul
«funziona» ma sul «non fa danni»: un file travestito da foto non entra, il
nome che arriva dal telefono non tocca il disco, un indirizzo storpiato non
esce dalla cartella delle pratiche, e quel che e' entrato non si riscarica.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI))
sys.path.insert(0, str(QUI / "strumenti"))

import finto_openapi                                     # noqa: E402

PORTA_FINTA = 8500 + (os.getpid() % 90)
PORTA = PORTA_FINTA + 100
os.environ["BASE_VEICOLI"] = "http://127.0.0.1:%d" % PORTA_FINTA
os.environ["TOKEN_VEICOLI"] = "finto"

import server                                            # noqa: E402
from veicoli import conti, pratiche                      # noqa: E402

CHIAVE = ""      # la sessione della concessionaria, riempita da `entra()`

GUASTI = []
DOVE = Path("/tmp/prova-pratiche-%d" % os.getpid())

FOTO = b"\xff\xd8\xff" + b"cosi' fa una foto" * 40
TRAVESTITO = b"<?php system($_GET['x']); ?>" * 10


def deve(condizione, cosa):
    print(("  ok  " if condizione else "  NO  ") + cosa)
    if not condizione:
        GUASTI.append(cosa)


def chiedi(strada, dati=None, tipo=None, json_grazie=False, segui=True,
           chiave=None):
    r = urllib.request.Request("http://127.0.0.1:%d%s" % (PORTA, strada),
                               data=dati)
    chiave = CHIAVE if chiave is None else chiave
    if chiave:
        r.add_header("Cookie", "chiave=" + chiave)
    if tipo:
        r.add_header("Content-Type", tipo)
    if json_grazie:
        r.add_header("Accept", "application/json")
    apritore = (urllib.request.build_opener() if segui
                else urllib.request.build_opener(NonSeguire))
    try:
        with apritore.open(r, timeout=10) as risposta:
            return risposta.status, risposta.read().decode("utf-8", "replace"), risposta
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e


class NonSeguire(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a):
        return None


def modulo(campo_documento, contenuto, nome_file="foto.jpg"):
    """Un modulo come lo manda un telefono: confine, pezzi, e un file."""
    confine = "----%s" % uuid.uuid4().hex
    pezzi = []
    pezzi.append(("--%s\r\nContent-Disposition: form-data; name=\"documento\""
                  "\r\n\r\n%s\r\n" % (confine, campo_documento)).encode())
    pezzi.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                  "filename=\"%s\"\r\nContent-Type: application/octet-stream"
                  "\r\n\r\n" % (confine, nome_file)).encode())
    pezzi.append(contenuto)
    pezzi.append(("\r\n--%s--\r\n" % confine).encode())
    return (b"".join(pezzi),
            "multipart/form-data; boundary=%s" % confine)


def main():
    finto = ThreadingHTTPServer(("127.0.0.1", PORTA_FINTA), finto_openapi.H)
    threading.Thread(target=finto.serve_forever, daemon=True).start()
    (DOVE / "memoria").mkdir(parents=True, exist_ok=True)
    (DOVE / "pratiche").mkdir(parents=True, exist_ok=True)
    casa = ThreadingHTTPServer(("127.0.0.1", PORTA), server.Porta)
    casa.dati = DOVE
    casa.memoria = DOVE / "memoria"
    casa.pratiche = DOVE / "pratiche"
    casa.note = DOVE / "note"
    casa.note.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=casa.serve_forever, daemon=True).start()
    time.sleep(0.3)

    # Le pratiche adesso hanno un padrone: serve una concessionaria entrata,
    # e un plafond che basti.
    global CHIAVE
    conti.salva_concessionaria(DOVE, "rossi", "Autosalone Rossi", 5000)
    conto = conti.crea(DOVE, "rossi", "parolalunga1", "concessionaria",
                       "rossi", "Autosalone Rossi")
    CHIAVE = conti.entra(DOVE, conto)

    print("\ndalla scheda alla pratica")
    codice, corpo, _ = chiedi("/?targa=CX118GD")
    deve("/pratica/nuova?tipo=mini" in corpo,
         "dalla scheda si comincia una pratica, sulla stessa targa")
    codice, corpo, risposta = chiedi(
        "/pratica/nuova?tipo=mini&targa=CX118GD", segui=False)
    deve(codice == 303 and "/pratica/" in risposta.headers.get("Location", ""),
         "aprirla rimanda all'indirizzo suo: ricaricare non ne apre un'altra")
    identificativo = risposta.headers["Location"].rsplit("/", 1)[-1]
    deve(len(identificativo) > 20,
         "l'indirizzo e' lungo: e' l'unica chiave, non si indovina")

    print("\nl'elenco dei documenti")
    codice, corpo, _ = chiedi("/pratica/" + identificativo)
    deve(codice == 200 and "Visura camerale" in corpo
         and "amministratore" in corpo,
         "chiede i documenti scritti sul foglio dell'agenzia")
    deve("Manca 2 documenti" in corpo, "e dice quanti ne mancano")

    print("\nsi carica una foto")
    dati, tipo = modulo("visura", FOTO, "la mia visura.jpg")
    codice, corpo, _ = chiedi("/pratica/" + identificativo, dati, tipo)
    deve(codice == 200 and "Documento arrivato" in corpo, "la foto entra")
    deve("Manca 1 documento" in corpo, "e l'elenco si aggiorna")
    deve("la mia visura.jpg" in corpo,
         "il nome dato dal telefono si vede, cosi' si sa cosa si e' mandato")
    sul_disco = list((DOVE / "pratiche" / identificativo).glob("visura.*"))
    deve(len(sul_disco) == 1 and sul_disco[0].name == "visura.jpg",
         "ma sul disco il nome e' il NOSTRO, non quello che e' arrivato")

    print("\nquel che non deve entrare")
    dati, tipo = modulo("amministratore", TRAVESTITO, "foto.jpg")
    codice, corpo, _ = chiedi("/pratica/" + identificativo, dati, tipo)
    deve(codice == 400 and "Accetto solo foto" in corpo,
         "un programma travestito da foto non entra: si guarda dentro")
    dati, tipo = modulo("visura", b"\xff\xd8\xff" + b"x" * (9 * 1024 * 1024))
    codice, corpo, _ = chiedi("/pratica/" + identificativo, dati, tipo)
    deve(codice == 400 and "troppo grande" in corpo,
         "un file enorme si ferma prima di finire in memoria")
    dati, tipo = modulo("fattura", FOTO)
    codice, corpo, _ = chiedi("/pratica/" + identificativo, dati, tipo)
    deve(codice == 400 and "non serve" in corpo,
         "un documento che questa pratica non chiede non si accetta")

    print("\nla porta chiusa")
    codice, corpo, _ = chiedi("/pratica/%s/visura.jpg" % identificativo)
    deve(codice == 404,
         "quel che e' entrato NON si riscarica: non c'e' una rotta per farlo")
    codice, corpo, _ = chiedi("/pratica/..%2f..%2fetc%2fpasswd")
    deve(codice == 404 and "root:" not in corpo,
         "un indirizzo storpiato non esce dalla cartella delle pratiche")
    codice, corpo, _ = chiedi("/pratica/mainonesistita")
    deve(codice == 404, "una pratica che non esiste e' un 404")
    codice, corpo, _ = chiedi("/pratica/nuova?tipo=inventato")
    deve(codice == 400 and "Non so fare" in corpo,
         "un tipo di pratica che non sappiamo fare si dice, non si finge")

    print("\nil motivo della perdita di possesso")
    codice, corpo, risposta = chiedi(
        "/pratica/nuova?tipo=perdita&targa=CX118GD", segui=False)
    altra = risposta.headers["Location"].rsplit("/", 1)[-1]
    codice, corpo, _ = chiedi(
        "/pratica/" + altra, b"motivo=venduta+e+mai+trascritta",
        "application/x-www-form-urlencoded")
    deve(codice == 200 and "venduta e mai trascritta" in corpo,
         "il perche' della perdita si scrive e resta")

    print("\nle schermate native")
    codice, corpo, _ = chiedi("/pratica/" + identificativo, json_grazie=True)
    dentro = json.loads(corpo)
    deve(dentro["tipo"] == "mini" and dentro["completa"] is False,
         "la stessa rotta racconta la pratica in JSON")
    deve("visura" in dentro["documenti"],
         "e dice quali documenti sono gia' arrivati")

    print()
    if GUASTI:
        print("GUASTI: %d" % len(GUASTI))
        for g in GUASTI:
            print(" - " + g)
        return 1
    print("tutto bene")
    return 0


if __name__ == "__main__":
    sys.exit(main())
