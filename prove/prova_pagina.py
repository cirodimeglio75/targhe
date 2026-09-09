#!/usr/bin/env python3
"""Il banco della pagina: fa partire il server vero col fornitore finto.

    python3 prove/prova_pagina.py

Controlla le tre cose che, sbagliate, si vedono da fuori: che la pagina
mostri quel che il cervello ha trovato, che la STESSA rotta risponda in
JSON alle schermate native (senno' nascono due verita' da tenere
allineate), e che un campo avvelenato dal fornitore finisca a schermo come
testo e non come programma.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI))
sys.path.insert(0, str(QUI / "strumenti"))

import finto_openapi                                     # noqa: E402

PORTA_FINTA = 8700 + (os.getpid() % 90)
PORTA = PORTA_FINTA + 100
os.environ["BASE_VEICOLI"] = "http://127.0.0.1:%d" % PORTA_FINTA
os.environ["TOKEN_VEICOLI"] = "finto"

import server                                            # noqa: E402

GUASTI = []


def deve(condizione, cosa):
    print(("  ok  " if condizione else "  NO  ") + cosa)
    if not condizione:
        GUASTI.append(cosa)


def chiedi(strada, json_grazie=False):
    r = urllib.request.Request("http://127.0.0.1:%d%s" % (PORTA, strada))
    if json_grazie:
        r.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=10) as risposta:
            return risposta.status, risposta.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    finto = ThreadingHTTPServer(("127.0.0.1", PORTA_FINTA), finto_openapi.H)
    threading.Thread(target=finto.serve_forever, daemon=True).start()

    dove = Path("/tmp/prova-pagina-%d" % os.getpid())
    (dove / "memoria").mkdir(parents=True, exist_ok=True)
    casa = ThreadingHTTPServer(("127.0.0.1", PORTA), server.Porta)
    casa.dati = dove
    casa.memoria = dove / "memoria"
    threading.Thread(target=casa.serve_forever, daemon=True).start()
    time.sleep(0.3)

    print("\nla pagina")
    codice, corpo = chiedi("/")
    deve(codice == 200 and "Scrivi una targa" in corpo,
         "la pagina d'ingresso si apre")
    codice, corpo = chiedi("/?targa=CX118GD")
    deve(codice == 200, "la ricerca risponde")
    deve("KIA" in corpo and "CARNIVAL" in corpo, "marca e modello a schermo")
    deve("106 kW" in corpo and "2.902 cc" in corpo,
         "il motore a schermo, coi numeri scritti in italiano")
    deve("2005" in corpo and "Anno" in corpo and "Data" not in corpo,
         "dell'immatricolazione si mostra l'anno, e la riga si chiama Anno")
    deve("Generali Italia" in corpo, "la polizza a schermo")
    deve(">NO<" in corpo and "primo anno" in corpo.lower(),
         "i neopatentati: 106 kW, e si dice di no")
    codice, corpo = chiedi("/targa/CX118GD")
    deve(codice == 200 and "CARNIVAL" in corpo,
         "l'indirizzo da condividere porta alla stessa scheda")

    print("\nla massa, chiesta a chi guarda")
    codice, corpo = chiedi("/?targa=DD222DD")
    deve("riga G" in corpo and "name=massa" in corpo,
         "quando manca la massa, la pagina la chiede invece di arrendersi")
    codice, corpo = chiedi("/?targa=DD222DD&massa=1100")
    deve(">SI'<" in corpo and "46,4" in corpo,
         "scritta la massa, la risposta si chiude e si vede il conto")
    codice, corpo = chiedi("/?targa=DD222DD&massa=ciao")
    deve(codice == 200 and "riga G" in corpo,
         "una massa scritta a caso non rompe niente: vale come non detta")

    print("\nle schermate native (stessa rotta, vestito diverso)")
    codice, corpo = chiedi("/targa/CX118GD", json_grazie=True)
    dentro = json.loads(corpo)
    deve(codice == 200 and dentro.get("marca") == "KIA",
         "la stessa rotta risponde in JSON")
    deve(dentro["neopatentati"]["si_puo"] is False and dentro["patente"] == "B",
         "nel JSON c'e' tutto quel che c'e' nella pagina")
    codice, corpo = chiedi("/?targa=ZZ999ZZ", json_grazie=True)
    deve(codice == 404 and "non risulta" in json.loads(corpo)["errore"],
         "la targa che non risulta e' un 404 anche per il nativo")

    print("\nquando il fornitore manda spazzatura")
    codice, corpo = chiedi("/?targa=AA000AA")
    deve(codice == 200, "la scheda esce lo stesso")
    deve("<script>alert(1)</script>" not in corpo,
         "lo script del fornitore NON entra nella pagina")
    deve("&lt;script&gt;" in corpo, "ci entra come testo, che e' quel che e'")
    deve('onmouseover="alert(2)"' not in corpo,
         "nemmeno le virgolette scappano da un attributo")

    print("\nquando va storto")
    codice, corpo = chiedi("/?targa=ciao")
    deve(codice == 400 and "targa italiana" in corpo,
         "una targa senza forma si spiega, e non costa una chiamata")
    codice, corpo = chiedi("/?targa=ZZ999ZZ")
    deve(codice == 404 and "non risulta" in corpo,
         "la targa che non risulta e' un 404, con la frase giusta")
    os.environ["VEICOLI_ROTTO"] = "402"
    codice, corpo = chiedi("/?targa=DD111DD")
    deve(codice == 502 and "credito" in corpo.lower(),
         "il guasto nostro e' un 502, non un errore addossato a chi chiede")
    os.environ["VEICOLI_ROTTO"] = ""
    codice, corpo = chiedi("/non-esiste")
    deve(codice == 404, "una pagina che non c'e' e' un 404")

    print("\nla salute")
    codice, corpo = chiedi("/salute")
    deve(codice == 200 and json.loads(corpo)["configurato"] is True,
         "il monitor sa se il servizio puo' lavorare")

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
