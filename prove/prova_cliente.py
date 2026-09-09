#!/usr/bin/env python3
"""Il banco: fa girare il cliente contro il finto fornitore e controlla.

Non chiede permesso a nessuno e non costa niente:

    python3 prove/prova_cliente.py

Se stampa «tutto bene» il cliente fa quel che dice di fare. Le cose che
controlla sono quelle che, sbagliate, si pagano: la memoria che non ricorda
(soldi), il «non risulta» che sembra un guasto (recensioni), il token
assente che esplode invece di spiegarsi (assistenza).
"""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI))
sys.path.insert(0, str(QUI / "strumenti"))

import finto_openapi                                    # noqa: E402

PORTA = 8612 + (os.getpid() % 200)
os.environ["BASE_VEICOLI"] = "http://127.0.0.1:%d" % PORTA
os.environ["TOKEN_VEICOLI"] = "finto"

from veicoli import cliente, memoria, patente, targa    # noqa: E402

GUASTI = []


def deve(condizione, cosa):
    print(("  ok  " if condizione else "  NO  ") + cosa)
    if not condizione:
        GUASTI.append(cosa)


def conto():
    with urllib.request.urlopen("http://127.0.0.1:%d/conto" % PORTA) as r:
        return json.loads(r.read().decode())


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORTA), finto_openapi.H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)
    cartella = Path("/tmp/prova-targhe-%d" % os.getpid())
    cartella.mkdir(parents=True, exist_ok=True)

    print("\nla targa")
    deve(targa.valida("cx 118 gd") == "CX118GD", "spazi e minuscole")
    deve(targa.valida("CXI18GD") == "CX118GD", "la I al posto dell'1")
    deve(targa.valida("ciao") == "", "quel che non e' una targa non passa")
    deve(targa.che_cos_e("AB12345") == "moto", "cinque cifre e' una moto")

    print("\nla scheda di un'auto")
    s = cliente.scheda("CX118GD", cartella=cartella)
    deve(s.get("marca") == "KIA", "la marca arriva")
    deve(s.get("kw") == 106, "i kilowatt arrivano")
    deve(s.get("anno") == "2005" and "immatricolazione" not in s,
         "dell'immatricolazione arriva l'anno, e non si promette il giorno")
    deve(s["assicurazione"].get("compagnia") == "Generali Italia",
         "la polizza arriva")
    deve(s["assicurazione"].get("assicurato") is True,
         "il «e' assicurato» arriva come booleano, non sparisce")
    deve(s["neopatentati"]["si_puo"] is False,
         "106 kW: non la guida un neopatentato, e si sa senza la massa")
    deve(s["patente"] == "B", "ci vuole la B")
    deve(s["grezzo"].get("KType") == "12345",
         "il grezzo si tiene: nessun campo si perde")

    print("\nla memoria")
    prima = conto()
    cliente.scheda("CX 118 GD", cartella=cartella)
    dopo = conto()
    deve(prima == dopo, "la stessa targa non si paga due volte")
    cliente.scheda("CX118GD", cartella=cartella, fresco=True)
    deve(conto()["/IT-car"] == dopo["/IT-car"] + 1,
         "«correggi» invece paga, e si vede")

    print("\nla moto")
    m = cliente.scheda("AB12345", cartella=cartella)
    deve(m.get("modello") == "CB 650 R", "la moto passa dalla rotta sua")
    deve("kw" not in m, "della moto il fornitore non manda la potenza")
    deve(m["patente"] == "A2 o A, secondo la potenza",
         "senza potenza la patente si dice a meta', invece di indovinare")

    print("\nla massa, che il fornitore non manda")
    senza = cliente.scheda("DD222DD", cartella=cartella)
    deve(senza["neopatentati"]["si_puo"] is None
         and senza["neopatentati"]["serve_massa"] is True,
         "sotto i 70 kW si chiede la massa invece di inventarla")
    con = cliente.scheda("DD222DD", cartella=cartella, massa=1100)
    deve(con["neopatentati"]["si_puo"] is True,
         "con la massa il conto si chiude: 51 kW su 1100 kg, si puo'")
    stretta = cliente.scheda("DD222DD", cartella=cartella, massa=850)
    deve(stretta["neopatentati"]["si_puo"] is False,
         "e la stessa auto piu' leggera no: 60 kW per tonnellata")

    print("\nil passaggio di proprieta'")
    from veicoli import passaggio
    deve(s["passaggio"]["euro"] == 670.0,
         "106 kW: il listino dice 670 € al pubblico")
    deve("costo" not in json.dumps(s) and "margine" not in json.dumps(s),
         "quel che costa a NOI non entra nella scheda, mai")
    deve(passaggio.prezzo(150)["euro"] is None
         and "non arriva" in passaggio.prezzo(150)["perche"],
         "sopra il listino non si estrapola: si dice che va chiesto")
    deve(passaggio.prezzo(82)["euro"] is None,
         "dove la foto non si legge, non si inventa un numero")
    deve(passaggio.margine(106) == 78.5,
         "il margine si sa, e resta un fatto nostro")
    deve(m.get("passaggio") is None,
         "delle moto non si dice il prezzo: il listino e' delle auto")

    print("\nla coda del fornitore (302 + check_id)")
    os.environ["VEICOLI_LENTO"] = "1"
    lento = cliente.scheda("EE333EE", cartella=cartella,
                           con_assicurazione=False)
    deve(lento.get("marca") == "KIA",
         "sotto carico risponde 302: si aspetta e la risposta arriva")
    deve(conto().get("/check_id", 0) >= 2,
         "e si aspetta chiedendo a /check_id, non seguendo il rimando")
    os.environ["VEICOLI_LENTO"] = ""

    print("\nquando va storto")
    try:
        cliente.scheda("ZZ999ZZ", cartella=cartella)
        deve(False, "la targa che non risulta deve fermarsi")
    except cliente.VeicoloRifiutato as e:
        deve(e.codice == 404 and "non risulta" in e.utente,
             "«non risulta» si spiega, non sembra un guasto")
    quante = conto().get("/IT-car", 0)
    try:
        cliente.scheda("ZZ999ZZ", cartella=cartella)
    except cliente.VeicoloRifiutato:
        pass
    deve(conto().get("/IT-car", 0) == quante,
         "anche il «non risulta» si ricorda: chi cicla targhe non ci costa")

    os.environ["VEICOLI_ROTTO"] = "402"
    try:
        cliente.scheda("DD111DD", cartella=cartella)
        deve(False, "il credito esaurito deve fermarsi")
    except cliente.VeicoloRifiutato as e:
        deve("credito" in e.utente.lower(),
             "credito esaurito: si dice cosa fare")
    os.environ["VEICOLI_ROTTO"] = ""

    senza = dict(os.environ)
    os.environ.pop("TOKEN_VEICOLI")
    try:
        cliente.scheda("EE222EE", cartella=cartella)
        deve(False, "senza token deve fermarsi")
    except cliente.VeicoloRifiutato as e:
        deve("non è ancora configurata" in e.utente,
             "senza token si spiega, non esplode")
    os.environ.update(senza)

    print("\nil conto dei neopatentati")
    deve(patente.guidabile_da_neopatentato(50, 1100)["si_puo"] is True,
         "50 kW su 1100 kg: si puo'")
    deve(patente.guidabile_da_neopatentato(66, 1000)["si_puo"] is False,
         "66 kW su una tonnellata: 66 kW/t, troppo")
    deve(patente.guidabile_da_neopatentato(None, 1000)["si_puo"] is None,
         "senza i numeri non si inventa una risposta")

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
