"""Un PDF scritto a mano, senza librerie.

Serve per la nota di saldo, ed e' l'unico documento che questo programma
fabbrica invece di ricevere. Farlo a mano non e' orgoglio: una libreria di
PDF e' un pacchetto grosso, che va aggiornato e che porta con se' le sue
falle, per stampare venti righe di testo su un foglio. Il formato, per
quel poco che ci serve, e' quattro oggetti e una tabella di posizioni.

Cosa sa fare: pagine A4, testo in Helvetica normale e nera, righe e
riquadri. Cosa NON sa fare: immagini, colori, tabelle vere, accapo
automatico. Se un giorno serve un documento piu' ricco di questo, e' il
momento di prendere una libreria — non di far crescere questo file.

Sugli accenti: il testo esce in **WinAnsi**, che e' la codifica che i
lettori di PDF sanno leggere senza che si debba allegare un carattere. Ci
stanno dentro le lettere accentate italiane e il simbolo dell'euro; quel
che non c'e' diventa un punto interrogativo invece di rompere il file.
"""

from typing import Any, List, Tuple

# A4 in punti tipografici, che e' l'unita' del PDF (72 per pollice).
LARGHEZZA = 595
ALTEZZA = 842

# Un pezzo di pagina: («testo», x, y, corpo, grassetto) oppure
# («riga», x1, y1, x2, y2) — bastano per una nota di saldo.
Pezzo = Tuple


def testo(x: float, y: float, quello: str, corpo: float = 11,
          grassetto: bool = False) -> Pezzo:
    return ("testo", x, y, quello, corpo, grassetto)


def riga(x1: float, y1: float, x2: float, y2: float) -> Pezzo:
    return ("riga", x1, y1, x2, y2)


def _scappa(quello: str) -> bytes:
    """Il testo come lo vuole il PDF: parentesi e barre hanno un significato."""
    dentro = quello.encode("cp1252", "replace")
    for prima, dopo in ((b"\\", b"\\\\"), (b"(", b"\\("), (b")", b"\\)")):
        dentro = dentro.replace(prima, dopo)
    return dentro


def _corpo_pagina(pezzi: List[Pezzo]) -> bytes:
    fuori = []
    for pezzo in pezzi:
        if pezzo[0] == "testo":
            _, x, y, quello, corpo, grassetto = pezzo
            fuori.append(b"BT /%s %s Tf %s %s Td (%s) Tj ET"
                         % (b"F2" if grassetto else b"F1",
                            ("%g" % corpo).encode(), ("%g" % x).encode(),
                            ("%g" % y).encode(), _scappa(quello)))
        elif pezzo[0] == "riga":
            _, x1, y1, x2, y2 = pezzo
            fuori.append(b"0.8 w 0.75 G %g %g m %g %g l S"
                         % (x1, y1, x2, y2))
    return b"\n".join(fuori)


def fabbrica(pagine: List[List[Pezzo]], titolo: str = "") -> bytes:
    """Il PDF finito, in byte. `pagine` e' una lista di liste di pezzi."""
    if not pagine:
        pagine = [[]]
    oggetti: List[bytes] = []

    def aggiungi(roba: bytes) -> int:
        oggetti.append(roba)
        return len(oggetti)        # i numeri partono da 1

    catalogo = aggiungi(b"")       # si riempie dopo: serve il numero
    elenco = aggiungi(b"")
    numeri_pagine = []
    for pezzi in pagine:
        flusso = _corpo_pagina(pezzi)
        contenuto = aggiungi(b"<< /Length %d >>\nstream\n%s\nendstream"
                             % (len(flusso), flusso))
        numeri_pagine.append(aggiungi(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> "
            b"/Contents %d 0 R >>"
            % (elenco, LARGHEZZA, ALTEZZA, 0, 0, contenuto)))
    normale = aggiungi(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                       b"/Encoding /WinAnsiEncoding >>")
    grassetto = aggiungi(b"<< /Type /Font /Subtype /Type1 /BaseFont "
                         b"/Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    # I caratteri si conoscono solo adesso: si riscrivono le pagine coi
    # numeri veri. E' il prezzo di numerare gli oggetti man mano.
    for numero in numeri_pagine:
        oggetti[numero - 1] = oggetti[numero - 1].replace(
            b"/F1 0 0 R /F2 0 0 R",
            b"/F1 %d 0 R /F2 %d 0 R" % (normale, grassetto))
    oggetti[catalogo - 1] = (b"<< /Type /Catalog /Pages %d 0 R >>" % elenco)
    oggetti[elenco - 1] = (
        b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % n for n in numeri_pagine), len(numeri_pagine)))

    fuori = bytearray(b"%PDF-1.4\n")
    # Il commento coi byte alti dice ai programmi che il file NON e' testo:
    # senza, qualcuno lo trasferisce «correggendo» gli accapo e lo rovina.
    fuori += b"%\xe2\xe3\xcf\xd3\n"
    posizioni = []
    for numero, roba in enumerate(oggetti, start=1):
        posizioni.append(len(fuori))
        fuori += b"%d 0 obj\n%s\nendobj\n" % (numero, roba)
    inizio_tabella = len(fuori)
    fuori += b"xref\n0 %d\n" % (len(oggetti) + 1)
    fuori += b"0000000000 65535 f \n"
    for posizione in posizioni:
        fuori += b"%010d 00000 n \n" % posizione
    fuori += (b"trailer\n<< /Size %d /Root %d 0 R%s >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(oggetti) + 1, catalogo,
                 (b" /Info << /Title (%s) >>" % _scappa(titolo)) if titolo
                 else b"", inizio_tabella))
    return bytes(fuori)
