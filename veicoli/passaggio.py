"""Quanto costa il passaggio di proprietà, dai kW.

Il listino di D.G.P Service, trascritto dalle foto del 9/09/2026. Sta qui
perche' e' l'unico prezzo che questa app puo' dire da sola: il passaggio si
paga **in base ai kW**, e i kW sono l'unico dato di potenza che il fornitore
manda (`PowerKW`, la voce **P.2** del libretto). Sappiamo la targa, sappiamo
i kW, quindi sappiamo il prezzo — senza chiedere niente a nessuno.

**Due colonne, e una sola si mostra.** `pubblico` e' il prezzo di listino,
quello che si dice a chi guarda. `costo` e' quanto costa a noi: non esce mai
da questo server, non entra in nessuna pagina e non finisce nel JSON delle
schermate native. Serve a sapere il margine, e il margine e' un fatto
nostro. Chi aggiunge una riga alla pagina si fermi a chiedersi da quale
delle due colonne la sta prendendo.

Quel che nelle foto non si legge, qui e' `None`, e `None` vuol dire «non lo
so»: la pagina dice «su richiesta» invece di stampare un numero inventato.
Un prezzo sbagliato in una schermata e' una promessa che poi qualcuno deve
mantenere allo sportello.

Da confermare con chi ha stampato il listino:
  - **55 kW**: manca nella colonna dei costi (nel listino al pubblico c'e').
  - **82, 83-85 e 86 kW**: nel listino al pubblico il riflesso della foto
    copre le cifre. Al pubblico si leggono solo le centinaia.
  - **146-147 kW**: nella colonna dei costi il numero e' tagliato via.
  - **oltre 147 kW** il listino finisce: sopra, si chiede.
  - la riga «130-131» dei costi contro «130-132» del pubblico, e la riga
    «122-116» che e' evidentemente **112-116** (il pubblico lo conferma).
  - «tutti i prezzi hanno 2.5 di commissioni postali»: da capire se sono
    gia' dentro i numeri o si aggiungono.

Le altre due voci scritte a mano, senza prezzo al pubblico:
mini passaggio 92,00 di costo; perdita di possesso 32,00, «da giustificare
il motivo della avvenuta perdita».
"""

from typing import Any, Dict, Optional

# (kW da, kW a, prezzo al pubblico, quanto costa a noi)
LISTINO = (
    (0, 53, 360.00, 304.00),
    (54, 54, 410.00, 350.20),
    (55, 55, 420.00, None),      # il costo manca nella foto
    (56, 56, 430.00, 355.20),
    (57, 58, 440.00, 369.20),
    (59, 59, 450.00, 372.50),
    (60, 62, 460.00, 377.50),
    (63, 65, 470.00, 401.00),
    (66, 70, 510.00, 422.50),
    (71, 80, 530.00, 468.50),
    (81, 81, 540.00, 473.50),
    (82, 82, None, 477.50),      # al pubblico: coperto dal riflesso
    (83, 85, None, 492.20),
    (86, 86, None, 495.50),
    (87, 90, 590.00, 515.50),
    (91, 92, 600.00, 523.50),
    (93, 94, 610.00, 532.50),
    (95, 96, 620.00, 541.50),
    (97, 97, 630.00, 547.50),
    (98, 100, 640.00, 558.50),
    (101, 103, 650.00, 573.50),
    (104, 105, 660.00, 582.50),
    (106, 107, 670.00, 591.50),
    (108, 111, 680.00, 609.50),
    (112, 116, 710.00, 632.50),  # nei costi era scritto «122-116»
    (117, 118, 720.00, 641.50),
    (119, 121, 730.00, 655.50),
    (122, 123, 740.00, 664.50),
    (124, 126, 750.00, 678.50),
    (127, 129, 770.00, 692.50),
    (130, 132, 780.00, 702.50),  # nei costi la riga si fermava a 131
    (133, 135, 795.00, 719.50),
    (136, 138, 810.00, 733.50),
    (139, 140, 820.00, 742.50),
    (141, 142, 830.00, 751.50),
    (143, 145, 840.00, 755.50),
    (146, 147, 850.00, None),    # il costo e' tagliato nella foto
)

# Sopra l'ultima riga il listino non dice niente, e non si estrapola.
TETTO = LISTINO[-1][1]


def _riga(kw: Optional[float]):
    if not kw or kw <= 0:
        return None
    for da, a, pubblico, costo in LISTINO:
        if da <= kw <= a:
            return (da, a, pubblico, costo)
    return None


def prezzo(kw: Optional[float]) -> Dict[str, Any]:
    """Il prezzo al pubblico per una potenza. **Senza il nostro costo.**

    E' questa la funzione che puo' chiamare una pagina. Torna sempre un
    perche', anche quando non c'e' un numero, cosi' la schermata ha qualcosa
    di sensato da scrivere invece di una riga vuota.
    """
    if not kw or kw <= 0:
        return {"euro": None,
                "perche": "non conosco i kW di questo veicolo"}
    if kw > TETTO:
        return {"euro": None,
                "perche": "sopra i %d kW il listino non arriva: il prezzo "
                          "si chiede" % TETTO}
    riga = _riga(kw)
    if not riga or riga[2] is None:
        return {"euro": None,
                "perche": "per questa potenza il prezzo va confermato"}
    return {"euro": riga[2], "da": riga[0], "a": riga[1],
            "perche": "listino D.G.P Service, per la potenza sul libretto "
                      "(voce P.2)"}


def margine(kw: Optional[float]) -> Optional[float]:
    """Quanto ci resta. **Non esce da questo server**: non si mette in una
    pagina, non si mette nel JSON delle schermate native."""
    riga = _riga(kw)
    if not riga or riga[2] is None or riga[3] is None:
        return None
    return round(riga[2] - riga[3], 2)
