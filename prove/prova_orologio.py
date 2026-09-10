#!/usr/bin/env python3
"""Il banco dell'orologio: quel che la piattaforma fa da sola.

    python3 prove/prova_orologio.py

Non si aspetta il sabato: si dice all'orologio che ora è. Così si prova in
due secondi quello che nella vita vera succede in due settimane — la
chiusura del sabato, la nota e la fattura che partono, il sollecito che
arriva quando il lunedì è passato, e — la cosa che conta di più — che
niente di tutto questo si ripeta due volte.
"""
import os
import sys
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI))

from veicoli import conteggio, conti, fatture, orologio, pratiche  # noqa: E402

GUASTI = []
DOVE = Path("/tmp/prova-orologio-%d" % os.getpid())
BUSTE = []


def deve(condizione, cosa):
    print(("  ok  " if condizione else "  NO  ") + cosa)
    if not condizione:
        GUASTI.append(cosa)


def spedizioniere(messaggio):
    BUSTE.append(messaggio)


def quando(giorno_settimana, ora=9, settimane=0):
    """Un istante che cade nel giorno della settimana chiesto."""
    adesso = time.time() + settimane * 7 * 86400
    oggi = time.localtime(adesso)
    passi = (giorno_settimana - oggi.tm_wday) % 7
    scelto = time.localtime(adesso + passi * 86400)
    return time.mktime((scelto.tm_year, scelto.tm_mon, scelto.tm_mday, ora,
                        0, 0, 0, 0, -1))


def pratica_finita(targa, prezzo, quale="rossi"):
    i = pratiche.apri(DOVE / "pratiche", "mini", targa, quale, prezzo, 106)
    for chiave in ("visura", "amministratore", "finale", "ricevuta"):
        pratiche.aggiungi(DOVE / "pratiche", i, chiave, b"%PDF-1.4 x")
    pratiche.chiudi(DOVE / "pratiche", i)
    return i


def giro(adesso):
    del BUSTE[:]
    return orologio.giro(DOVE, DOVE / "pratiche", DOVE / "note",
                         DOVE / "fatture", adesso=adesso,
                         spedizioniere=spedizioniere)


def main():
    for pezzo in ("pratiche", "note", "fatture"):
        (DOVE / pezzo).mkdir(parents=True, exist_ok=True)
    conti.salva_concessionaria(DOVE, "rossi", "Autosalone Rossi", 5000,
                               "rossi@example.it")
    pratica_finita("CX118GD", 670.0)
    pratica_finita("DD222DD", 360.0)

    print("\nnei giorni feriali non succede niente")
    fatto = giro(quando(2))          # mercoledì
    deve(not fatto["note"] and not BUSTE,
         "di mercoledì l'orologio gira e non fa niente")

    print("\nil sabato si chiude la settimana")
    fatto = giro(quando(5, 8))
    deve(len(fatto["note"]) == 1, "esce la nota della settimana")
    deve(len(BUSTE) == 1 and "Nota di saldo" in BUSTE[0]["Subject"],
         "e parte per posta alla concessionaria")
    allegati = list(BUSTE[0].iter_attachments())
    deve(len(allegati) == 1 and allegati[0].get_filename().startswith("nota-"),
         "con la nota in PDF attaccata")
    deve(fatto["guasti"] and "fattura non emessa" in fatto["guasti"][0],
         "la fattura NON esce: mancano i dati fiscali, e lo dice")
    nota = conteggio.note(DOVE / "note", "rossi")[0]
    deve(nota["totale"] == 1030.0, "il totale è la somma delle pratiche finite")

    print("\nlo stesso sabato, due volte")
    fatto = giro(quando(5, 11))
    deve(not fatto["note"] and not BUSTE,
         "la settimana già chiusa non si richiude: niente nota doppia")

    print("\ncoi dati fiscali, esce anche la fattura")
    fatture.salva_fisco(DOVE, {"ragione_sociale": "D.G.P Service srl",
                               "piva": "01234567890", "indirizzo": "Via Roma 1",
                               "citta": "Modena", "provincia": "MO",
                               "cap": "41100", "iva": "22",
                               "compenso_mini": "60"})
    deve(fatture.pronto(DOVE) == "", "adesso si può emettere")
    pratica_finita("EE333EE", 530.0)
    fatto = giro(quando(5, 8, settimane=1))
    deve(len(fatto["fatture"]) == 1, "il sabato dopo esce anche la fattura")
    fattura = fatture.elenco(DOVE / "fatture")[0]
    deve(fattura["numero"] == "1/%s" % time.strftime("%Y"),
         "numerata progressiva per anno, dall'uno")
    seconda = conteggio.note(DOVE / "note", "rossi")[0]
    deve([r["targa"] for r in seconda["righe"]] == ["EE333EE"],
         "e dentro c'è SOLO la pratica nuova: quelle della nota di prima "
         "non si rifatturano")
    conti_f = fattura["conti"]
    deve(conti_f["imponibile"] == 60.0 and conti_f["iva"] == 13.2
         and conti_f["anticipazioni"] == 470.0,
         "col compenso imponibile e il resto fuori campo art. 15")
    deve(conti_f["totale"] == 543.2,
         "e il totale del documento tiene conto dell'IVA sul compenso")
    deve(len(list(BUSTE[0].iter_attachments())) == 2,
         "nella busta ci sono nota e fattura")

    print("\nil sollecito, quando il lunedì è passato")
    fatto = giro(quando(5, 8, settimane=1) + 86400)      # domenica
    deve(not fatto["solleciti"], "la domenica dopo non è ancora in ritardo")
    tardi = quando(5, 8, settimane=1) + 4 * 86400        # mercoledì dopo
    fatto = giro(tardi)
    deve(fatto["solleciti"] == ["rossi"], "passato il lunedì, parte il sollecito")
    deve(BUSTE and "Sollecito" in BUSTE[0]["Subject"], "l'oggetto lo dice")
    allegati = list(BUSTE[0].iter_attachments())
    deve(len(allegati) == 1
         and allegati[0].get_filename() == "estratto-conto.pdf",
         "con l'estratto conto attaccato")
    try:
        import pymupdf
    except ImportError:
        pymupdf = None
        print("  --  (salto la lettura del PDF: pymupdf non c'è su questa "
              "macchina)")
    if pymupdf is not None:
        (DOVE / "estratto.pdf").write_bytes(allegati[0].get_payload(decode=True))
        letto = pymupdf.open(DOVE / "estratto.pdf")[0].get_text()
        deve("Estratto conto" in letto and "SCADUTA" in letto,
             "e dentro c'è scritto quali sono scadute")
        deve("1.560" in letto or "1560" in letto,
             "col totale dovuto di tutte le note aperte")

    print("\ne non si sollecita ogni ora")
    fatto = giro(tardi + 3600)
    deve(not fatto["solleciti"],
         "un'ora dopo non si risollecita: la posta finirebbe nello spam")
    fatto = giro(tardi + 4 * 86400)
    deve(fatto["solleciti"] == ["rossi"], "ma dopo il passo, sì")

    print("\nchi salda esce dai solleciti")
    for nota in conteggio.da_saldare(DOVE / "note", "rossi"):
        conteggio.segna_saldata(DOVE / "note", DOVE / "pratiche", nota["id"])
    fatto = giro(tardi + 8 * 86400)
    deve(not fatto["solleciti"] and not BUSTE,
         "saldato tutto, i solleciti smettono")

    print("\nsenza indirizzo di posta")
    conti.salva_concessionaria(DOVE, "muti", "Muti Auto", 1000)
    pratica_finita("FF444FF", 300.0, "muti")
    fatto = giro(quando(5, 8, settimane=2))
    deve(any("muti" in g for g in fatto["guasti"]),
         "si annota che la posta non è partita")
    deve(conteggio.note(DOVE / "note", "muti"),
         "ma la nota esiste lo stesso: il credito c'è anche senza posta")

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
