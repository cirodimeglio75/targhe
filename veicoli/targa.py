"""La targa: come si scrive e come si riconosce.

Chi digita una targa la scrive come gli viene: con gli spazi, col trattino,
minuscola, con la O al posto dello zero. Il fornitore invece la vuole in un
modo solo. Questa e' la porta d'ingresso: pulisce, e dice se quel che resta
ha la forma di una targa italiana — cosi' una targa storpiata si ferma qui
e non costa una chiamata a pagamento.
"""

import re

# Le forme che valgono oggi in Italia, tenute vicine a quelle che il
# fornitore dichiara nella documentazione (Automotive 1.0.0): quel che
# lui rifiuta non deve nemmeno partire da qui. Le nostre sono un filo piu'
# strette sulle lettere, perche' le targhe italiane nuove non usano I, O,
# Q e U — e chi le scrive di solito ha confuso una cifra.
FORME = (
    # Rimorchi: XA000AA. Sta PRIMA delle auto perche' ne ha la stessa forma:
    # la X iniziale e' riservata ai rimorchi, e le auto non ci sono ancora
    # arrivate — chi arrivera' a discuterne avra' vent'anni di targhe alle
    # spalle e questa riga sotto gli occhi.
    (re.compile(r"^X[A-HJ-NPR-TV-Z]{1,2}[0-9]{3}[A-HJ-NPR-TV-Z]{2}$"), "rimorchio"),
    # Auto dal 1994: AA 000 AA. Le vocali e le lettere ambigue non ci sono
    # nella prima e nell'ultima coppia (niente I, O, Q, U).
    (re.compile(r"^[A-HJ-NPR-TV-Z]{2}[0-9]{3}[A-HJ-NPR-TV-Z]{2}$"), "auto"),
    # Moto e ciclomotori dal 1999: AA 00000.
    (re.compile(r"^[A-HJ-NPR-TV-Z]{2}[0-9]{5}$"), "moto"),
    # Auto prima del 1994: sigla della provincia + cifre (MI123456).
    # Due lettere e sei caratteri, non di piu': e' la forma che il
    # fornitore dichiara di accettare (`^[a-zA-Z]{2}[a-zA-Z0-9]{6}$`), e
    # mandargli una targa che rifiuta costa una chiamata per un «no».
    (re.compile(r"^[A-Z]{2}[A-Z0-9]{6}$"), "auto"),
)

# Chi scrive a mano confonde queste. Si correggono SOLO dove la posizione
# dice che ci vuole una cifra o una lettera, mai alla cieca.
CIFRA_DA_LETTERA = {"O": "0", "Q": "0", "I": "1", "L": "1", "S": "5",
                    "B": "8", "Z": "2"}
LETTERA_DA_CIFRA = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}


def pulisci(scritto: str) -> str:
    """Toglie tutto quel che non e' lettera o cifra e alza le maiuscole."""
    return "".join(c for c in (scritto or "").upper() if c.isalnum())


def raddrizza(targa: str) -> str:
    """Sistema le confusioni tipiche nella forma nuova AA000AA / AA00000.

    Solo su quelle due forme, e solo per posizione: nella parte numerica una
    lettera diventa la cifra che le somiglia, e viceversa. Su una targa
    vecchia non si tocca niente — li' non si sa dove finisce la sigla.
    """
    t = pulisci(targa)
    if len(t) == 7 and t[:2].isalpha():
        if t[2:5].isalnum() and t[5:].isalnum():
            testa = "".join(LETTERA_DA_CIFRA.get(c, c) for c in t[:2])
            # Sette caratteri sono o AA000AA o AA00000: si guarda la coda.
            if t[5:].isdigit() or any(c in CIFRA_DA_LETTERA for c in t[5:]):
                corpo = "".join(CIFRA_DA_LETTERA.get(c, c) for c in t[2:])
                return testa + corpo
            corpo = "".join(CIFRA_DA_LETTERA.get(c, c) for c in t[2:5])
            coda = "".join(LETTERA_DA_CIFRA.get(c, c) for c in t[5:])
            return testa + corpo + coda
    return t


def che_cos_e(targa: str) -> str:
    """«auto», «moto», «rimorchio», o stringa vuota se non ha una forma nota.

    Serve a scegliere la rotta giusta senza chiederlo all'utente: una targa
    di cinque cifre e' una moto, e chiedere «auto o moto?» a chi ha gia'
    scritto la targa e' una domanda che sapevamo gia'.
    """
    t = pulisci(targa)
    for forma, tipo in FORME:
        if forma.match(t):
            return tipo
    return ""


def valida(scritto: str) -> str:
    """La targa pronta per il fornitore, o stringa vuota se non lo e'.

    Prima prova com'e' stata scritta; se non va, prova a raddrizzarla. Se
    nemmeno cosi' ha una forma nota, torna vuota: la chiamata non parte.
    """
    t = pulisci(scritto)
    if che_cos_e(t):
        return t
    raddrizzata = raddrizza(t)
    return raddrizzata if che_cos_e(raddrizzata) else ""
