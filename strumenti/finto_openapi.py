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
  VEICOLI_LENTO=1     la coda: risponde 302 e fa aspettare su /check_id,
                      come fa quello vero quando e' sotto carico

Le targhe hanno tre regole: **DD222DD e' un'auto sotto i 70 kW** (serve a
provare il caso in cui i neopatentati dipendono dalla massa che il
fornitore non manda), **ZZ999ZZ non risulta** (404), e **AA000AA
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

# Le risposte, coi nomi VERI della documentazione ufficiale (Automotive
# 1.0.0). Il manichino serve a poco se e' vestito diversamente dall'uomo:
# qui dentro c'e' esattamente quel che manda il fornitore — e soprattutto
# quel che NON manda, cioe' la massa, la categoria, la classe Euro e il
# giorno di immatricolazione (dell'anno arriva solo l'anno).
AUTO = {"Description": "KIA CARNIVAL 2.9 16V CRDI classe",
        "RegistrationYear": "2005", "CarMake": "KIA", "CarModel": "CARNIVAL",
        "MakeDescription": "KIA", "ModelDescription": "CARNIVAL",
        "EngineSize": "2902", "FuelType": "Diesel",
        "Version": "2.9 16V CRDI classe", "NumberOfDoors": "5",
        "ABS": "true", "AirBag": "true", "Immobiliser": "true",
        "Vin": "KNEUP751255123456", "KType": "12345",
        "PowerCV": 144, "PowerKW": 106, "PowerFiscal": 21}
# La moto NON ha la potenza: e' cosi' anche dal fornitore vero, ed e' il
# motivo per cui la patente di una moto si dice a meta'.
MOTO = {"Description": "HONDA CB 650 R", "RegistrationYear": "2021",
        "CarMake": "HONDA", "CarModel": "CB 650 R",
        "MakeDescription": "HONDA", "ModelDescription": "CB 650 R",
        "EngineSize": "649", "FuelType": "Benzina", "Version": "CB 650 R",
        "ABS": "true", "AirBag": "false", "Immobiliser": "true",
        "Vin": "ZDCRH02A0MF123456", "KType": "54321"}
POLIZZA = {"Company": "Generali Italia", "Expiry": "2027-03-14",
           "ExpiryTimeStamp": 1804032000, "IsInsured": True}


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

    def _rimanda(self, dove):
        """Il 302 della coda: la risposta non e' pronta, si richiama."""
        self.send_response(302)
        self.send_header("Location", dove)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/conto":
            return self._out(200, CONTO)

        # La coda: prima volta PENDING, poi la risposta vera. Cosi' il banco
        # prova davvero il giro d'attesa, non solo il codice 302.
        if self.path.startswith("/check_id/"):
            CONTO["/check_id"] = CONTO.get("/check_id", 0) + 1
            fatte = CONTO["/check_id"]
            identificativo = self.path.rsplit("/", 1)[-1]
            if fatte < 2:
                return self._out(200, {"success": True,
                                       "data": {"state": "PENDING",
                                                "id": identificativo}})
            return self._out(200, {"success": True,
                                   "data": dict(AUTO, LicensePlate="CX118GD")})
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
        if os.environ.get("VEICOLI_LENTO") == "1":
            return self._rimanda("https://automotive.openapi.com/check_id/"
                                 "abc123")
        if rotto.isdigit():
            return self._out(int(rotto),
                             {"success": False, "message": "guasto simulato"})
        if targa == "DD222DD" and rotta == "/IT-car":
            # Un'auto SOTTO i 70 kW: e' il caso in cui la risposta sui
            # neopatentati dipende dalla massa, che il fornitore non manda.
            return self._out(200, {"success": True, "data": dict(
                AUTO, LicensePlate=targa, CarMake="FIAT", CarModel="PANDA",
                Description="FIAT PANDA 1.2", EngineSize="1242",
                Version="1.2 Lounge", PowerKW=51, PowerCV=69,
                PowerFiscal=13)})
        if targa == "AA000AA" and rotta == "/IT-car":
            # Il fornitore non lo farebbe apposta, ma un dato sporco puo'
            # arrivare da chiunque abbia scritto in un archivio pubblico.
            return self._out(200, {"success": True, "data": dict(
                AUTO, LicensePlate=targa,
                CarMake="<script>alert(1)</script>",
                CarModel="Fiat\" onmouseover=\"alert(2)")})
        if targa == "ZZ999ZZ":
            return self._out(404, {"success": False,
                                   "message": "plate not found"})
        if rotta == "/IT-insurance":
            return self._out(200, {"success": True,
                                   "data": dict(POLIZZA, LicensePlate=targa)})
        if rotta == "/IT-bike":
            return self._out(200, {"success": True,
                                   "data": dict(MOTO, LicensePlate=targa)})
        if rotta == "/IT-car":
            return self._out(200, {"success": True,
                                   "data": dict(AUTO, LicensePlate=targa)})
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
