#!/usr/bin/env python3
"""Finto fornitore automotive, per il banco: non costa niente e conta tutto.

Serve a provare la ricerca per targa senza spendere venti centesimi a giro.
Conta le domande ricevute, cosi' il banco puo' dimostrare che la memoria
funziona davvero: due ricerche sulla stessa targa devono arrivare qui una
volta sola.

  BASE_VEICOLI=http://127.0.0.1:8612 TOKEN_VEICOLI=finto  python3 …
  python3 strumenti/finto_openapi.py 8612

Simula anche i guasti che contano, perche' vanno provati anche quelli:

  VEICOLI_ROTTO=401   credenziali rifiutate
  VEICOLI_ROTTO=402   credito esaurito
  VEICOLI_ROTTO=429   troppe richieste
  VEICOLI_ROTTO=rete  non risponde affatto

Le targhe hanno due regole: **ZZ999ZZ non risulta** (404), e **AA000AA
risponde con una marca avvelenata** — dentro c'e' uno script. Serve al
banco per dimostrare che la pagina lo mostra come testo e non lo esegue:
il campo «marca» e' testo di terzi come un modulo compilato da uno
sconosciuto. Tutte le altre targhe rispondono normalmente.
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Quante domande sono arrivate, per rotta. Il banco lo legge da /conto.
CONTO = {}

# Una risposta verosimile, coi nomi che il fornitore *probabilmente* usa.
# Non e' la verita': e' un manichino. Il giorno che si legge la console vera
# questo file e le mappe di `cliente.CAMPI` cambiano insieme.
AUTO = {"make": "KIA", "model": "CARNIVAL", "version": "2.9 16V CRDI classe",
        "registrationDate": "2005-06-28", "registrationPlace": "Modena (MO)",
        "fuel": "Diesel", "displacement": 2902, "kw": 106, "hp": 144,
        "weight": 2100, "category": "M1", "euroClass": "Euro 3"}
MOTO = {"make": "HONDA", "model": "CB 650 R", "registrationDate": "2021-04-02",
        "fuel": "Benzina", "displacement": 649, "kw": 70, "hp": 95,
        "weight": 202, "category": "L3E"}
POLIZZA = {"company": "Generali Italia", "expirationDate": "2027-03-14",
           "insured": True}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _out(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/conto":
            return self._out(200, CONTO)
        pezzi = [p for p in self.path.split("/") if p]
        if len(pezzi) != 2:
            return self._out(404, {"success": False, "message": "non esiste"})
        rotta, targa = "/" + pezzi[0], pezzi[1].upper()
        CONTO[rotta] = CONTO.get(rotta, 0) + 1

        # Il token: qui basta che ci sia, ma l'assenza va punita come la
        # punisce il fornitore vero, senno' il banco non prova niente.
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            return self._out(401, {"success": False, "message": "Wrong Token"})
        rotto = os.environ.get("VEICOLI_ROTTO", "")
        if rotto == "rete":
            self.close_connection = True
            return
        if rotto.isdigit():
            return self._out(int(rotto),
                             {"success": False, "message": "guasto simulato"})
        if targa == "AA000AA" and rotta == "/IT-car":
            # Il fornitore non lo farebbe apposta, ma un dato sporco puo'
            # arrivare da chiunque abbia scritto in un archivio pubblico.
            return self._out(200, {"success": True, "data": dict(
                AUTO, plate=targa,
                make="<script>alert(1)</script>",
                model="Fiat\" onmouseover=\"alert(2)")})
        if targa == "ZZ999ZZ":
            return self._out(404, {"success": False,
                                   "message": "plate not found"})
        if rotta == "/IT-insurance":
            return self._out(200, {"success": True,
                                   "data": dict(POLIZZA, plate=targa)})
        if rotta == "/IT-bike":
            return self._out(200, {"success": True,
                                   "data": dict(MOTO, plate=targa)})
        if rotta == "/IT-car":
            return self._out(200, {"success": True,
                                   "data": dict(AUTO, plate=targa)})
        # Rotta sconosciuta: il fornitore vero NON risponde 404, risponde
        # «Wrong Token», perche' i token valgono per metodo+percorso. Il
        # finto imita la trappola, senno' il banco non la vede mai.
        return self._out(401, {"success": False, "message": "Wrong Token"})


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8612
    server = ThreadingHTTPServer(("127.0.0.1", porta), H)
    print("finto fornitore automotive su http://127.0.0.1:%d" % porta,
          flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
