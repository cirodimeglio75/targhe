#!/usr/bin/env python3
"""Fa un conto, chiedendo la parola d'ordine senza scriverla da nessuna parte.

    sudo -u targhe python3 /opt/targhe/strumenti/primo_conto.py

Esiste per un motivo solo, e non e' la comodita': una parola d'ordine
passata sulla riga di comando finisce **nella cronologia della shell** e
la vede `ps` mentre il comando gira. Qui si digita, non si vede sullo
schermo, e non resta scritta in nessun file.

Serve per il primo conto — quello di amministrazione, senza il quale non
entra nessuno — e per farne altri da riga di comando quando serve.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veicoli import conti                                # noqa: E402

DOVE = "/var/lib/targhe"


def chiedi(domanda: str, predefinito: str = "") -> str:
    scritto = input("%s%s: " % (domanda,
                                (" [%s]" % predefinito) if predefinito else ""))
    return scritto.strip() or predefinito


def main() -> int:
    dove = Path(sys.argv[1] if len(sys.argv) > 1 else DOVE)
    if not dove.is_dir():
        print("La cartella dei dati non c'è: %s" % dove)
        return 1

    gia = conti.conti(dove)
    if gia:
        print("Conti che ci sono già: %s" % ", ".join(sorted(gia)))
    else:
        print("Non c'è ancora nessun conto: questo sarà il primo.")

    utente = chiedi("Nome utente", "admin")
    ruolo = chiedi("Ruolo (amministrazione, agenzia, concessionaria)",
                   "amministrazione")
    nome = chiedi("Nome da mostrare", "Amministrazione")
    concessionaria = ""
    if ruolo == "concessionaria":
        concessionaria = chiedi("Identificativo della concessionaria")

    parola = getpass.getpass("Parola d'ordine (almeno 8, non si vede): ")
    ancora = getpass.getpass("Riscrivila: ")
    if parola != ancora:
        # Meglio fermarsi che creare un conto con una parola diversa da
        # quella che si crede di aver scelto: non si potrebbe piu' entrare.
        print("Le due parole non sono uguali: non ho fatto niente.")
        return 1

    try:
        conto = conti.crea(dove, utente, parola, ruolo, concessionaria, nome)
    except conti.ContoRifiutato as e:
        print(e.utente)
        return 1
    print("Fatto: «%s», ruolo %s. Adesso si entra da /entra."
          % (conto["utente"], conto["ruolo"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
