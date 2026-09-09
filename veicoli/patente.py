"""Neopatentati e patente necessaria: il conto lo facciamo noi, e costa zero.

Questa e' la riga della schermata che il fornitore non vende, e non serve
che la venda: i due numeri che servono — i kilowatt e la massa — stanno gia'
nella risposta che abbiamo pagato per i dati tecnici.

La regola (art. 117 del Codice della Strada, come riscritto nel 2011) vale
**per il primo anno** dalla patente B, e chiede due cose insieme:

  - non piu' di **55 kW per tonnellata** di massa in ordine di marcia;
  - e, per le automobili (categoria M1), non piu' di **70 kW** in assoluto.

I disabili con veicolo adattato sono fuori dalla regola: la mostriamo come
avvertenza, non come sentenza. E il numero giusto per il conto e' la **massa
in ordine di marcia** (la tara col pieno e il guidatore), non la massa
totale a terra: sbagliare riga fa passare per proibite auto che vanno bene.
"""

from typing import Any, Dict, Optional

TETTO_KW = 70.0                 # solo per le automobili (M1)
TETTO_KW_PER_TONNELLATA = 55.0


def guidabile_da_neopatentato(kw: Optional[float], massa_kg: Optional[float],
                              categoria: str = "M1") -> Dict[str, Any]:
    """Se un neopatentato la puo' guidare nel primo anno, e perche'.

    Torna sempre un motivo scritto: una schermata che dice solo «no» manda
    la persona a cercare altrove il perche'.
    """
    categoria = (categoria or "").upper().strip()
    if not kw or not massa_kg or kw <= 0 or massa_kg <= 0:
        return {"si_puo": None,
                "perche": "mancano la potenza o la massa: non posso dirlo"}
    per_tonnellata = kw / (massa_kg / 1000.0)
    if categoria.startswith("M1") and kw > TETTO_KW:
        return {"si_puo": False, "kw_per_tonnellata": round(per_tonnellata, 1),
                "perche": "supera i 70 kW: nel primo anno di patente B non "
                          "si può guidare"}
    if per_tonnellata > TETTO_KW_PER_TONNELLATA:
        return {"si_puo": False, "kw_per_tonnellata": round(per_tonnellata, 1),
                "perche": "%.1f kW per tonnellata: sopra il limite di 55 del "
                          "primo anno di patente B" % per_tonnellata}
    return {"si_puo": True, "kw_per_tonnellata": round(per_tonnellata, 1),
            "perche": "entro i limiti del primo anno di patente B (55 kW "
                      "per tonnellata%s)"
                      % (", 70 kW in tutto" if categoria.startswith("M1")
                         else "")}


def patente_necessaria(categoria: str = "", cilindrata: Optional[float] = None,
                       kw: Optional[float] = None,
                       massa_kg: Optional[float] = None) -> str:
    """Che patente ci vuole per guidarlo, nella grafia che legge una persona.

    Per le moto la soglia non e' solo la potenza ma anche il rapporto con la
    massa: una moto leggera da 35 kW resta fuori dalla A2.
    """
    categoria = (categoria or "").upper().strip()
    if categoria.startswith("L"):           # ciclomotori e motocicli
        if cilindrata and cilindrata <= 50:
            return "AM"
        if cilindrata and cilindrata <= 125 and (not kw or kw <= 11):
            if not massa_kg or not kw or kw / massa_kg <= 0.1:
                return "A1"
        if kw and kw <= 35:
            if not massa_kg or kw / massa_kg <= 0.2:
                return "A2"
        return "A"
    if categoria.startswith("N") or (massa_kg and massa_kg > 3500):
        return "C"
    return "B"
