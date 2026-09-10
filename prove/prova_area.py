#!/usr/bin/env python3
"""Il banco delle aree: il giro intero, dalla concessionaria al saldo.

    python3 prove/prova_area.py

Segue la strada che ha descritto il proprietario: la concessionaria apre la
pratica e carica i documenti, l'agenzia le vede tutte e scrive se qualcosa
non va, chiude col documento e la ricevuta, l'amministrazione conta,
emette la nota e la segna saldata — e il plafond torna libero.

Poi prova le porte: una concessionaria non deve vedere le pratiche di
un'altra, l'agenzia non deve poter toccare i plafond, e un modulo mandato
da un'altra pagina non deve valere.
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

PORTA_FINTA = 8300 + (os.getpid() % 90)
PORTA = PORTA_FINTA + 100
os.environ["BASE_VEICOLI"] = "http://127.0.0.1:%d" % PORTA_FINTA
os.environ["TOKEN_VEICOLI"] = "finto"

import server                                            # noqa: E402
from veicoli import conteggio, conti, posta, pratiche    # noqa: E402

GUASTI = []
DOVE = Path("/tmp/prova-area-%d" % os.getpid())
FOTO = b"\xff\xd8\xff" + b"una foto" * 30


def deve(condizione, cosa):
    print(("  ok  " if condizione else "  NO  ") + cosa)
    if not condizione:
        GUASTI.append(cosa)


class NonSeguire(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a):
        return None


def chiedi_byte(strada, chiave=""):
    """Come `chiedi`, ma senza tradurre: un PDF non e' testo, e leggerlo
    come tale lo rovina prima ancora di guardarlo."""
    r = urllib.request.Request("http://127.0.0.1:%d%s" % (PORTA, strada))
    if chiave:
        r.add_header("Cookie", "chiave=" + chiave)
    try:
        with urllib.request.urlopen(r, timeout=10) as risposta:
            return risposta.status, risposta.read(), risposta
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e


def chiedi(strada, chiave="", dati=None, tipo=None, segui=True, origine=None):
    r = urllib.request.Request("http://127.0.0.1:%d%s" % (PORTA, strada),
                               data=dati)
    if chiave:
        r.add_header("Cookie", "chiave=" + chiave)
    if tipo:
        r.add_header("Content-Type", tipo)
    if origine:
        r.add_header("Origin", origine)
    apritore = (urllib.request.build_opener() if segui
                else urllib.request.build_opener(NonSeguire))
    try:
        with apritore.open(r, timeout=10) as risposta:
            return risposta.status, risposta.read().decode("utf-8", "replace"), risposta
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e


def modulo(campi, file_campo=None, contenuto=b"", nome_file="foto.jpg"):
    confine = "----%s" % uuid.uuid4().hex
    pezzi = []
    for nome, valore in campi.items():
        pezzi.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\""
                      "\r\n\r\n%s\r\n" % (confine, nome, valore)).encode())
    if file_campo:
        pezzi.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; "
                      "filename=\"%s\"\r\nContent-Type: application/octet-"
                      "stream\r\n\r\n" % (confine, file_campo, nome_file)
                      ).encode())
        pezzi.append(contenuto)
        pezzi.append(b"\r\n")
    pezzi.append(("--%s--\r\n" % confine).encode())
    return b"".join(pezzi), "multipart/form-data; boundary=%s" % confine


def main():
    finto = ThreadingHTTPServer(("127.0.0.1", PORTA_FINTA), finto_openapi.H)
    threading.Thread(target=finto.serve_forever, daemon=True).start()
    for pezzo in ("memoria", "pratiche", "note", "fatture"):
        (DOVE / pezzo).mkdir(parents=True, exist_ok=True)
    casa = ThreadingHTTPServer(("127.0.0.1", PORTA), server.Porta)
    casa.dati = DOVE
    casa.memoria = DOVE / "memoria"
    casa.pratiche = DOVE / "pratiche"
    casa.note = DOVE / "note"
    casa.fatture = DOVE / "fatture"
    casa.fatture.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=casa.serve_forever, daemon=True).start()
    time.sleep(0.3)

    conti.salva_concessionaria(DOVE, "rossi", "Autosalone Rossi", 2000,
                               "rossi@example.it")
    conti.salva_concessionaria(DOVE, "bianchi", "Bianchi Auto", 2000)
    conti.crea(DOVE, "rossi", "parolalunga1", "concessionaria", "rossi",
               "Autosalone Rossi")
    conti.crea(DOVE, "bianchi", "parolalunga2", "concessionaria", "bianchi",
               "Bianchi Auto")
    conti.crea(DOVE, "agenzia", "parolalunga3", "agenzia", nome="L'agenzia")
    conti.crea(DOVE, "admin", "parolalunga4", "amministrazione",
               nome="Amministrazione")

    print("\nentrare")
    dati, tipo = modulo({"utente": "rossi", "parola": "sbagliata"})
    codice, corpo, _ = chiedi("/entra", dati=dati, tipo=tipo)
    deve(codice == 401 and "non giusti" in corpo,
         "la parola sbagliata non entra, e non dice quale dei due era")
    dati, tipo = modulo({"utente": "rossi", "parola": "parolalunga1"})
    codice, corpo, risposta = chiedi("/entra", dati=dati, tipo=tipo,
                                     segui=False)
    biscotto = risposta.headers.get("Set-Cookie", "")
    deve(codice == 303 and "HttpOnly" in biscotto and "SameSite=Lax" in biscotto,
         "entrare dà un biscotto che nessuno script può leggere")
    rossi = biscotto.split("chiave=")[1].split(";")[0]
    agenzia = conti.entra(DOVE, conti.conti(DOVE)["agenzia"])
    admin = conti.entra(DOVE, conti.conti(DOVE)["admin"])
    bianchi = conti.entra(DOVE, conti.conti(DOVE)["bianchi"])

    print("\nla concessionaria apre una pratica")
    codice, corpo, _ = chiedi("/pratica/nuova?tipo=mini&targa=CX118GD")
    deve(codice == 401, "senza entrare non si apre una pratica")
    codice, corpo, risposta = chiedi(
        "/pratica/nuova?tipo=mini&targa=CX118GD", rossi, segui=False)
    pratica = risposta.headers["Location"].rsplit("/", 1)[-1]
    deve(codice == 303, "entrata, la apre")
    dentro = pratiche.leggi(DOVE / "pratiche", pratica)
    deve(dentro["concessionaria"] == "rossi" and dentro["prezzo"] == 670.0,
         "la pratica nasce col suo padrone e col prezzo preso dai kW")
    codice, corpo, _ = chiedi("/area", rossi)
    deve("1.330" in corpo or "1330" in corpo,
         "e il plafond della concessionaria si è mosso: 2000 - 670")

    print("\nle porte fra concessionarie")
    codice, corpo, _ = chiedi("/pratica/" + pratica, bianchi)
    deve(codice == 404,
         "un'altra concessionaria non la vede, e non le si dice che esiste")
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia)
    deve(codice == 200 and "Autosalone" not in corpo and "rossi" in corpo,
         "l'agenzia sì, per mestiere")

    print("\ni documenti, e chi li carica")
    for quale in ("visura", "amministratore"):
        dati, tipo = modulo({"documento": quale}, "file", FOTO)
        codice, corpo, _ = chiedi("/pratica/" + pratica, rossi, dati, tipo)
        deve(codice == 200, "la concessionaria carica «%s»" % quale)
    dati, tipo = modulo({"documento": "finale"}, "file", FOTO)
    codice, corpo, _ = chiedi("/pratica/" + pratica, rossi, dati, tipo)
    deve(codice == 400 and "carica l&#x27;agenzia" in corpo,
         "ma il documento finito no: quello è dell'agenzia")
    dati, tipo = modulo({"documento": "visura"}, "file", FOTO)
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo)
    deve(codice == 400, "e l'agenzia non carica i documenti della concessionaria")

    print("\nl'agenzia guarda i documenti")
    codice, corpo, risposta = chiedi(
        "/pratica/%s/documento/visura" % pratica, agenzia)
    deve(codice == 200 and risposta.headers.get("Content-Type") == "image/jpeg",
         "l'agenzia apre la visura, col tipo che abbiamo stabilito noi")
    deve(risposta.headers.get("X-Content-Type-Options") == "nosniff"
         and "sandbox" in risposta.headers.get("Content-Security-Policy", ""),
         "e il browser non puo' indovinarne un altro ne' eseguire niente")
    codice, corpo, _ = chiedi("/pratica/%s/documento/visura" % pratica,
                              bianchi)
    deve(codice == 404, "un'altra concessionaria non lo apre")
    codice, corpo, _ = chiedi("/pratica/%s/documento/visura" % pratica)
    deve(codice == 404, "e chi non e' entrato nemmeno")
    codice, corpo, _ = chiedi(
        "/pratica/%s/documento/..%%2f..%%2fpratica.json" % pratica, agenzia)
    deve(codice == 404 and "concessionaria" not in corpo,
         "e un nome storpiato non tira fuori altri file")

    print("\nl'agenzia scrive che qualcosa non va")
    dati, tipo = modulo({"messaggio": "La visura non si legge, rifallaa"})
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo)
    deve(codice == 200 and "non si legge" in corpo, "il messaggio resta")
    codice, corpo, _ = chiedi("/pratica/" + pratica, rossi)
    deve("non si legge" in corpo and "L&#x27;agenzia" in corpo,
         "e la concessionaria lo vede, con chi l'ha scritto")

    print("\nl'agenzia chiude")
    dati, tipo = modulo({"chiudi": "1"})
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo)
    deve(codice == 400 and "servono il documento" in corpo,
         "non si chiude senza le carte, nemmeno volendo")
    for quale in ("finale", "ricevuta"):
        dati, tipo = modulo({"documento": quale}, "file", FOTO)
        chiedi("/pratica/" + pratica, agenzia, dati, tipo)
    dati, tipo = modulo({"chiudi": "1"})
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo)
    deve(codice == 200 and "finita" in corpo, "con le carte, si chiude")

    print("\nil conteggio, e il saldo")
    codice, corpo, _ = chiedi("/area", admin)
    deve("670" in corpo and "Emetti" in corpo,
         "l'amministrazione vede che c'è da conteggiare, e quanto")
    dati, tipo = modulo({"concessionaria": "rossi"})
    codice, corpo, _ = chiedi("/area/nota", admin, dati, tipo)
    deve(codice == 200 and "Nota emessa" in corpo, "la nota si emette")
    # Il banco gira senza posta configurata, ed e' il caso che conta: chi
    # emette deve LEGGERE che non e' partita, non crederlo.
    deve("resta scaricabile" in corpo,
         "e se la posta non è configurata lo dice, invece di far finta")
    nota = conteggio.note(DOVE / "note", "rossi")[0]
    deve(nota["totale"] == 670.0 and len(nota["righe"]) == 1,
         "e contiene quella pratica lì, con quel totale lì")
    codice, corpo, _ = chiedi("/area", rossi)
    deve("Da saldare" in corpo, "la concessionaria la vede da saldare")
    print("\nla nota in PDF")
    codice, dato, risposta = chiedi_byte("/nota/%s.pdf" % nota["id"], rossi)
    deve(codice == 200
         and risposta.headers.get("Content-Type") == "application/pdf",
         "la concessionaria scarica il PDF della sua nota")
    deve(dato.startswith(b"%PDF-1.4"), "ed è un PDF vero")
    dove_pdf = DOVE / "nota-provata.pdf"
    dove_pdf.write_bytes(dato)
    # Si legge col lettore di PDF, non guardando i byte: quel che conta e'
    # che il documento si APRA e dica le cose giuste a chi lo riceve.
    #
    # Il lettore pero' e' una libreria in piu', e sul SERVER non c'e' —
    # questo banco gira anche prima di ogni aggiornamento, e non deve
    # bloccarlo per una libreria da banco di prova. Dove manca, si salta
    # e si dice.
    try:
        import pymupdf
    except ImportError:
        pymupdf = None
        print("  --  (salto la lettura del PDF: pymupdf non c'è su questa "
              "macchina)")
    if pymupdf is not None:
        letto = "\n".join(p.get_text() for p in pymupdf.open(dove_pdf))
        deve("Nota di saldo" in letto and "670,00" in letto
             and "Autosalone Rossi" in letto,
             "e un lettore di PDF ci legge dentro nome, righe e totale")
        deve("entro lunedì" in letto,
             "con scritto entro quando si salda, come vuole l'accordo")
    codice, corpo, _ = chiedi("/nota/%s.pdf" % nota["id"], bianchi)
    deve(codice == 404, "un'altra concessionaria non lo apre")
    codice, corpo, _ = chiedi("/nota/%s.pdf" % nota["id"])
    deve(codice == 404, "e chi non è entrato nemmeno")

    print("\nla posta")
    busta = {}
    partita = posta.manda("rossi@example.it", "Nota di saldo", "Eccola.",
                          b"%PDF-1.4 finto", "nota.pdf",
                          spedizioniere=lambda m: busta.update({"m": m}))
    allegati = list(busta["m"].iter_attachments())
    deve(partita and allegati and allegati[0].get_filename() == "nota.pdf"
         and allegati[0].get_content_type() == "application/pdf",
         "la busta porta il PDF attaccato, col nome giusto")
    try:
        posta.manda("", "x", "y")
        deve(False, "senza indirizzo deve fermarsi")
    except posta.PostaRifiutata as e:
        deve("non ha un indirizzo" in e.utente,
             "senza indirizzo lo dice, e dice cosa fare")
    dati, tipo = modulo({"nota": nota["id"]})
    codice, corpo, _ = chiedi("/area/saldo", admin, dati, tipo)
    deve("plafond è tornato libero" in corpo, "segnata saldata")
    resta = conteggio.quanto_resta(DOVE, DOVE / "pratiche", "rossi")
    deve(resta["usato"] == 0 and resta["resta"] == 2000,
         "e il plafond è davvero azzerato")

    print("\nil plafond che non basta")
    conti.salva_concessionaria(DOVE, "bianchi", "Bianchi Auto", 100)
    codice, corpo, _ = chiedi("/pratica/nuova?tipo=mini&targa=CX118GD",
                              bianchi)
    deve(codice == 400 and "plafond non basta" in corpo,
         "una pratica che sfonda il plafond si ferma PRIMA dei documenti")

    print("\nchi non deve toccare i conti")
    dati, tipo = modulo({"concessionaria": "rossi", "plafond": "99999"})
    codice, corpo, _ = chiedi("/area/plafond", agenzia, dati, tipo)
    deve(codice == 403 and conteggio.quanto_resta(
        DOVE, DOVE / "pratiche", "rossi")["plafond"] == 2000,
        "l'agenzia non muove i plafond, e il numero non cambia")
    dati, tipo = modulo({"concessionaria": "rossi", "plafond": "99999"})
    codice, corpo, _ = chiedi("/area/plafond", rossi, dati, tipo)
    deve(codice == 403, "e nemmeno la concessionaria sul proprio")

    print("\nil modulo mandato da un'altra pagina")
    dati, tipo = modulo({"messaggio": "ciao"})
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo,
                              origine="https://sito-cattivo.example")
    deve(codice == 403, "un modulo che arriva da un'altra casa non vale")
    # E il contrario, che e' quello che conta di piu': il modulo mandato
    # dalla NOSTRA pagina deve passare. La prima volta, dietro il proxy,
    # veniva rifiutato — cioe' la difesa chiudeva fuori il padrone di casa.
    dati, tipo = modulo({"messaggio": "questo deve passare"})
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo,
                              origine="http://127.0.0.1:%d" % PORTA)
    deve(codice == 200 and "questo deve passare" in corpo,
         "e uno che arriva dalla nostra pagina passa")
    dati, tipo = modulo({"messaggio": "anche con la porta diversa"})
    codice, corpo, _ = chiedi("/pratica/" + pratica, agenzia, dati, tipo,
                              origine="https://127.0.0.1")
    deve(codice == 200,
         "anche se lo schema e la porta li ha cambiati il proxy davanti")

    print("\nuscire")
    codice, corpo, risposta = chiedi("/esci", rossi, segui=False)
    deve("Max-Age=0" in risposta.headers.get("Set-Cookie", ""),
         "uscire spegne il biscotto")
    codice, corpo, _ = chiedi("/pratica/" + pratica, rossi)
    deve(codice == 404, "e la chiave vecchia non apre più niente")

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
