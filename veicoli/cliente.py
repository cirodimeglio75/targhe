"""Il cliente delle targhe: chiede a Openapi e torna una scheda.

Stampo dichiarato: `av/sms.py` del programma Ops!, che parla con la stessa
casa. Da li' vengono le cose che gia' ci sono costate care una volta:

- **il token viene da due posti, e vince l'amministrazione.** Finche' stava
  solo in `.env` si accendeva solo da una scrivania con le chiavi SSH, e il
  proprietario comanda dal telefono. `.env` fa da fondo per chi configura a
  mano.
- **un token di Openapi e' un JWT che dichiara per cosa vale**: quando il
  fornitore risponde «Wrong Token» la spiegazione sta quasi sempre li'
  dentro — token generato per un altro servizio o gia' scaduto — e
  `carta()` la legge senza rigenerare token a tentativi.
- **la rotta sbagliata non da' 404**: i token valgono per metodo+percorso,
  quindi una rotta sbagliata risponde «Wrong Token» accusando il token. Se
  un giorno queste rotte rispondono 401 con un token appena fatto, il
  sospettato numero uno e' il percorso, non la credenziale.

I nomi dei campi vengono dalla **documentazione ufficiale** (API Reference
Automotive 1.0.0, letta il 9/09/2026). Quel che quella lettura ha
insegnato, e che nessuno indovinerebbe:

- **il fornitore non manda la massa del veicolo**, e nemmeno la categoria.
  Il conto dei neopatentati vive di quella: vedi `patente.py`, che adesso
  dice «non lo so» invece di inventare.
- **della data di immatricolazione arriva solo l'ANNO** (`RegistrationYear`),
  non il giorno. Una schermata che promette «28 giu 2005» prometterebbe un
  dato che non abbiamo.
- **della moto non arriva la potenza**: niente `PowerKW` su `/IT-bike`,
  quindi la patente si dice per quel che si sa dalla cilindrata, e il resto
  si dichiara ignoto.
- **la revisione, per l'Italia, non esiste in questo servizio.** C'e' solo
  per il Regno Unito (`/UK-mot`). Era la domanda aperta dello studio:
  la risposta e' no, e serve un altro fornitore.
- **sotto carico il fornitore risponde 302, non 200**: dopo dieci secondi
  taglia, da' un identificativo e va chiesto a `/check_id/{id}` finche' non
  e' DONE. Il redirect NON va seguito in automatico — la documentazione lo
  dice a chiare lettere — perche' il token vale per percorso e la
  ridirezione lo porterebbe su una rotta per cui potrebbe non valere.

`normalizza()` **tiene sempre il grezzo** lo stesso: costa niente, e il
giorno che il fornitore aggiunge un campo lo troviamo li' invece di
scoprirlo per caso.
"""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from . import memoria, patente, targa as targhe

# Dove sta il servizio. `BASE_VEICOLI` lo dirotta sul finto, per il banco.
CASA = "https://automotive.openapi.com"
# Quanto si aspetta una risposta: chi ha digitato una targa sta guardando
# lo schermo. Il fornitore taglia da solo a dieci secondi.
ATTESA = 15
# E quanto si insiste, quando il fornitore mette la richiesta in coda.
PAZIENZA = 25

FILE = "veicoli.json"
SEGRETO = "•" * 8

# Il servizio nostro -> la rotta del fornitore. Una riga sola da cambiare
# se un giorno le rotte cambiano nome.
ROTTE = {"auto": "/IT-car", "moto": "/IT-bike",
         "assicurazione": "/IT-insurance"}


class NonSeguire(urllib.request.HTTPRedirectHandler):
    """Il 302 del fornitore non e' una ridirezione da seguire: e' una
    risposta che dice «ci vuole piu' tempo, richiamami a questo numero».

    Seguirla in automatico porterebbe il token su `/check_id`, e i token di
    Openapi valgono per metodo+percorso: la risposta sarebbe «Wrong Token»
    per una richiesta che invece era andata benissimo."""

    def redirect_request(self, richiesta, risposta, codice, messaggio,
                         intestazioni, nuovo):
        return None


APRITORE = urllib.request.build_opener(NonSeguire)


class VeicoloRifiutato(Exception):
    """Guasto del fornitore o della rete. `utente` e' cio' che si puo'
    mostrare: l'errore di un fornitore non deve arrivare all'utente cosi'
    com'e', e non deve nemmeno sparire nel nulla."""

    def __init__(self, messaggio: str, utente: str = "", codice: int = 0):
        super().__init__(messaggio)
        self.utente = utente or ("Non riesco a leggere i dati di questa "
                                 "targa in questo momento. Riprova fra poco.")
        self.codice = codice


def _casa() -> str:
    return (os.environ.get("BASE_VEICOLI", "").strip() or CASA).rstrip("/")


def _salvato(dati: Optional[Path]) -> Dict[str, str]:
    """Cio' che l'amministrazione ha salvato. Mai un errore: file assente o
    illeggibile vuol dire «vale l'ambiente»."""
    if not dati:
        return {}
    try:
        dentro = json.loads((Path(dati) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: str(v) for k, v in dentro.items()} if isinstance(dentro, dict) else {}


def salva_token(dati: Path, token: str) -> None:
    """Scrive il token accanto ai dati, leggibile solo dal programma.

    Vuoto o col segnaposto non cancella quel che c'era: cancellare per
    omissione e' il modo piu' rapido di spegnere il servizio credendo di
    averlo corretto. Per tornare a `.env` c'e' `dimentica_token`."""
    token = (token or "").strip()
    if not token or token == SEGRETO:
        return
    percorso = Path(dati) / FILE
    provvisorio = percorso.with_suffix(".nuovo")
    provvisorio.write_text(json.dumps({"token": token}, ensure_ascii=False),
                           encoding="utf-8")
    os.chmod(provvisorio, 0o600)
    provvisorio.replace(percorso)


def dimentica_token(dati: Path) -> bool:
    """Butta via il token salvato dall'amministrazione: torna a valere `.env`."""
    try:
        (Path(dati) / FILE).unlink()
        return True
    except OSError:
        return False


def _token(dati: Optional[Path] = None) -> str:
    return (_salvato(dati).get("token", "").strip()
            or os.environ.get("TOKEN_VEICOLI", "").strip())


def da_dove(dati: Optional[Path] = None) -> str:
    """Da dove viene il token in uso: «amministrazione», «ambiente», o niente."""
    if _salvato(dati).get("token", "").strip():
        return "amministrazione"
    if os.environ.get("TOKEN_VEICOLI", "").strip():
        return "ambiente"
    return ""


def configurato(dati: Optional[Path] = None) -> bool:
    """Se si puo' chiedere davvero. La pagina lo dice invece di fallire a
    sorpresa."""
    return bool(_token(dati))


def carta(dati: Optional[Path] = None) -> str:
    """Cio' che il token dichiara di se': per cosa vale e quando scade.

    E' un JWT: la parte di mezzo si legge da chiunque, il segreto e' la
    firma — quindi mostrarla non svela niente."""
    token = _token(dati)
    if not token:
        return ""
    pezzi = token.split(".")
    if len(pezzi) != 3:
        # Non e' per forza un errore: il token degli SMS e' un JWT che si
        # lascia leggere, ma altri servizi di Openapi danno chiavi opache.
        # Dire «sbagliato» a una chiave buona manderebbe a rigenerare token
        # a vuoto per un pomeriggio.
        return ("non e' un JWT, quindi non posso leggerne la scadenza ne' "
                "i servizi: alcune chiavi di Openapi sono cosi', e non "
                "vuol dire che sia sbagliata. Se il fornitore risponde "
                "«Wrong Token», e' da confrontare con la console")
    try:
        grezzo = pezzi[1] + "=" * (-len(pezzi[1]) % 4)
        dentro = json.loads(base64.urlsafe_b64decode(grezzo.encode("ascii")))
        if not isinstance(dentro, dict):
            raise ValueError("non un oggetto")
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return ("il token ha tre pezzi ma la parte di mezzo non si lascia "
                "leggere: probabilmente e' stato storpiato nella copia")
    fuori = []
    ambiti = dentro.get("scopes") or dentro.get("scope") or []
    if isinstance(ambiti, str):
        ambiti = ambiti.split()
    if ambiti:
        fuori.append("vale per: " + ", ".join(str(a) for a in ambiti))
        # Il caso che fa perdere un pomeriggio: token buono, servizio
        # sbagliato. Se gli ambiti ci sono e l'automotive non c'e', si dice.
        if not any("car" in str(a).lower() or "bike" in str(a).lower()
                   or "insurance" in str(a).lower()
                   or "automotive" in str(a).lower() for a in ambiti):
            fuori.append("ATTENZIONE: fra i servizi non compare l'automotive: "
                         "questo token e' probabilmente di un altro prodotto")
    else:
        fuori.append("non dichiara nessun servizio")
    scadenza = dentro.get("exp") or dentro.get("expire")
    if isinstance(scadenza, (int, float)) and scadenza > 0:
        quando = time.strftime("%d/%m/%Y", time.localtime(scadenza))
        fuori.append(("SCADUTO il " if scadenza < time.time() else "scade il ")
                     + quando)
    return "; ".join(fuori)


# ---------------------------------------------------------------- la chiamata

def _porta(rotta: str, token: str) -> urllib.request.Request:
    return urllib.request.Request(
        _casa() + rotta,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/json"})


def _guasto(e: urllib.error.HTTPError) -> "VeicoloRifiutato":
    """Il guasto del fornitore tradotto in una frase che dice cosa fare.

    I codici sono quelli dichiarati dalla documentazione. Di 406, 417 e 428
    la documentazione NON dice il significato: si riporta il numero e si
    ammette di non saperlo, che e' meglio di una spiegazione inventata che
    manda a cercare dalla parte sbagliata.
    """
    detto = e.read().decode("utf-8", "replace")[:300]
    if e.code == 404:
        # Non e' un guasto: e' una risposta. Chi ha sbagliato una lettera
        # deve capire di riprovare, non che il servizio e' rotto.
        return VeicoloRifiutato(
            "targa non trovata: %s" % detto,
            "Questa targa non risulta. Controlla di averla scritta bene.",
            404)
    if e.code in (401, 403):
        return VeicoloRifiutato(
            "credenziali rifiutate (%d): %s" % (e.code, detto),
            "Il servizio non è configurato bene: va controllato il token "
            "nella console del fornitore.", e.code)
    if e.code == 402:
        return VeicoloRifiutato(
            "credito esaurito: %s" % detto,
            "Il credito per le ricerche è esaurito: va ricaricato dalla "
            "console del fornitore.", e.code)
    if e.code == 429:
        return VeicoloRifiutato(
            "troppe richieste: %s" % detto,
            "Troppe ricerche in poco tempo. Riprova fra qualche minuto.",
            e.code)
    if e.code in (406, 417, 428):
        return VeicoloRifiutato(
            "il fornitore ha rifiutato la richiesta (%d): %s" % (e.code, detto),
            "Il fornitore non accetta questa richiesta. Se la targa è "
            "giusta, è un problema nostro da guardare.", e.code)
    return VeicoloRifiutato("risposta %d: %s" % (e.code, detto), codice=e.code)


def _leggi(risposta) -> Dict[str, Any]:
    return json.loads(risposta.read().decode("utf-8", "replace") or "{}")


def _aspetta(identificativo: str, token: str) -> Dict[str, Any]:
    """La richiesta lenta: si richiama `/check_id` finche' non e' pronta.

    Il fornitore taglia a dieci secondi e restituisce un identificativo:
    non e' un errore, e' una coda. Si aspetta fino a `PAZIENZA` secondi
    chiedendo ogni secondo e mezzo — oltre, chi ha digitato la targa ha
    gia' chiuso la pagina, e insistere costa senza servire a nessuno.
    """
    scade = time.time() + PAZIENZA
    while time.time() < scade:
        time.sleep(1.5)
        try:
            with APRITORE.open(_porta("/check_id/" + urllib.parse.quote(identificativo),
                                      token), timeout=ATTESA) as risposta:
                dentro = _leggi(risposta)
        except urllib.error.HTTPError as e:
            raise _guasto(e) from e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise VeicoloRifiutato("rete mentre si aspettava: %s" % e) from e
        dati = dentro.get("data") or {}
        # Finche' e' in coda torna {state, id}; quando e' pronta, al posto
        # dello stato c'e' il veicolo. Si guarda quello, non lo stato: cosi'
        # va bene anche se un giorno lo stato smette di arrivare.
        if isinstance(dati, dict) and dati.get("state") == "PENDING":
            continue
        return dentro
    raise VeicoloRifiutato(
        "richiesta ancora in coda dopo %d secondi" % PAZIENZA,
        "Il fornitore sta rispondendo lentamente. Riprova fra poco.")


def _chiedi(servizio: str, targa: str,
            dati: Optional[Path] = None) -> Dict[str, Any]:
    """Una domanda al fornitore, senza memoria e senza rete di protezione.

    Fuori di qui si passa da `interroga`, che ricorda. Questa resta separata
    perche' il banco deve poter provare la chiamata nuda."""
    token = _token(dati)
    if not token:
        raise VeicoloRifiutato(
            "TOKEN_VEICOLI non configurato",
            "La ricerca per targa non è ancora configurata su questo server.")
    rotta = ROTTE.get(servizio)
    if not rotta:
        raise VeicoloRifiutato("servizio sconosciuto: %s" % servizio)
    richiesta = _porta(rotta + "/" + urllib.parse.quote(targa), token)
    try:
        with APRITORE.open(richiesta, timeout=ATTESA) as risposta:
            return _leggi(risposta)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            # Non e' una ridirezione: e' «ci vuole piu' tempo». L'indirizzo
            # finisce per /check_id/ID, e da li' si prende l'identificativo.
            dove = e.headers.get("Location") or ""
            identificativo = dove.rstrip("/").rsplit("/", 1)[-1]
            if not identificativo:
                raise VeicoloRifiutato(
                    "il fornitore ha rimandato senza identificativo: %s" % dove
                ) from e
            return _aspetta(identificativo, token)
        raise _guasto(e) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise VeicoloRifiutato("rete: %s" % e) from e
    except ValueError as e:
        raise VeicoloRifiutato("risposta non leggibile: %s" % e) from e


# I nomi veri, dalla documentazione ufficiale (Automotive 1.0.0). Dove ce
# n'e' piu' d'uno, il primo che c'e' vince: `CarMake` e' la marca secca,
# `MakeDescription` la stessa cosa scritta per esteso.
#
# Non c'e' niente da inventare qui, ma c'e' molto da NON promettere: la
# massa, la categoria, la classe Euro, il luogo e il giorno di
# immatricolazione NON esistono in questo servizio. Se un giorno compaiono,
# si aggiunge una riga qui e la pagina se ne accorge da sola.
CAMPI = {
    "targa": ("LicensePlate",),
    "marca": ("CarMake", "MakeDescription"),
    "modello": ("CarModel", "ModelDescription"),
    "allestimento": ("Version",),
    "descrizione": ("Description",),
    "anno": ("RegistrationYear",),
    "alimentazione": ("FuelType",),
    "cilindrata": ("EngineSize",),
    "kw": ("PowerKW",),
    "cavalli": ("PowerCV",),
    "fiscali": ("PowerFiscal",),
    "porte": ("NumberOfDoors",),
    "telaio": ("Vin",),
    # L'assicurazione ha una risposta sua, con tre campi e basta.
    "compagnia": ("Company",),
    "scadenza_polizza": ("Expiry",),
    "assicurato": ("IsInsured",),
}

def _pesca(dentro: Dict[str, Any], nomi) -> Any:
    """Il primo dei nomi che c'e' davvero, cercato anche un piano piu' sotto.

    I fornitori annidano: `data.vehicle.make` e' comune quanto `data.make`.
    Si guarda in superficie e in ogni sotto-oggetto, un piano solo — piu'
    giu' si finisce a indovinare."""
    for nome in nomi:
        if nome in dentro and (dentro[nome] is False
                               or dentro[nome] not in (None, "")):
            return dentro[nome]
    for valore in dentro.values():
        if isinstance(valore, dict):
            for nome in nomi:
                if nome in valore and (valore[nome] is False
                                       or valore[nome] not in (None, "")):
                    return valore[nome]
    return None


def normalizza(risposta: Dict[str, Any]) -> Dict[str, Any]:
    """Dalla risposta del fornitore ai nomi nostri, tenendo il grezzo.

    Il grezzo si tiene sempre: finche' le mappe qui sopra non sono confermate
    sulla console, e' l'unica cosa che sicuramente non perde niente."""
    dentro = risposta.get("data") if isinstance(risposta.get("data"), dict) \
        else risposta
    if isinstance(risposta.get("data"), list) and risposta["data"]:
        primo = risposta["data"][0]
        dentro = primo if isinstance(primo, dict) else {}
    if not isinstance(dentro, dict):
        dentro = {}
    fuori = {nostro: _pesca(dentro, nomi) for nostro, nomi in CAMPI.items()}
    # `is False` non e' «vuoto»: un veicolo NON assicurato e' la risposta
    # piu' importante che questo servizio sappia dare, e un filtro scritto
    # male la farebbe sparire dalla schermata.
    fuori = {k: v for k, v in fuori.items()
             if v is False or v not in (None, "")}
    fuori["grezzo"] = dentro
    return fuori


def _numero(valore: Any) -> Optional[float]:
    """Un numero da quel che manda il fornitore: «106 kW» e «106» valgono
    uguale, e una stringa vuota non deve far esplodere un conto."""
    if isinstance(valore, (int, float)):
        return float(valore)
    if not isinstance(valore, str):
        return None
    ripulito = valore.replace(",", ".")
    cifre = "".join(c for c in ripulito
                    if c.isdigit() or c == ".").strip(".")
    try:
        return float(cifre) if cifre else None
    except ValueError:
        return None


def interroga(servizio: str, scritta: str, dati: Optional[Path] = None,
              cartella: Optional[Path] = None,
              fresco: bool = False) -> Dict[str, Any]:
    """Un servizio su una targa, passando dalla memoria.

    `fresco` salta la memoria: e' il tasto «correggi», e costa una chiamata
    vera — per questo non e' il modo normale."""
    targa = targhe.valida(scritta)
    if not targa:
        raise VeicoloRifiutato(
            "targa senza forma nota: %r" % scritta,
            "Questa non sembra una targa italiana. Controlla come l'hai "
            "scritta.")
    if not fresco:
        # Anche il «non risulta» e' ricordato: senza, chi cicla targhe a caso
        # ci fa pagare ogni tentativo a vuoto.
        vuoto = memoria.leggi(cartella, "sconosciuta", targa)
        if vuoto and vuoto.get("servizio_chiesto") == servizio:
            raise VeicoloRifiutato("targa non trovata (dalla memoria)",
                                   "Questa targa non risulta. Controlla di "
                                   "averla scritta bene.", 404)
        saputo = memoria.leggi(cartella, servizio, targa)
        if saputo:
            saputo["dalla_memoria"] = True
            return saputo
    try:
        risposta = _chiedi(servizio, targa, dati)
    except VeicoloRifiutato as e:
        if e.codice == 404:
            memoria.scrivi(cartella, "sconosciuta", targa,
                           {"servizio_chiesto": servizio})
        raise
    roba = normalizza(risposta)
    roba["dalla_memoria"] = False
    memoria.scrivi(cartella, servizio, targa, roba)
    return roba


def scheda(scritta: str, dati: Optional[Path] = None,
           cartella: Optional[Path] = None,
           con_assicurazione: bool = True,
           fresco: bool = False,
           massa: Optional[float] = None) -> Dict[str, Any]:
    """La schermata intera: dati del veicolo, polizza, e chi lo puo' guidare.

    La rotta la sceglie la forma della targa, non l'utente: chi ha gia'
    scritto AB12345 ci ha gia' detto che e' una moto, e chiedergli «auto o
    moto?» e' una domanda di cui sapevamo la risposta.

    L'assicurazione e' una chiamata a parte, quindi un costo a parte: se
    fallisce, la scheda esce lo stesso con dentro il perche'. Meta' schermata
    e' meglio di una schermata di errore su un dato che abbiamo gia' pagato.

    `massa` la porta chi guarda, dal libretto: il fornitore non la manda, e
    senza non si chiude il conto dei neopatentati sotto i 70 kW. Non si
    memorizza insieme alla risposta — e' un dato di chi chiede, non del
    veicolo, e domani potrebbe scriverlo un'altra persona.
    """
    targa = targhe.valida(scritta)
    if not targa:
        raise VeicoloRifiutato(
            "targa senza forma nota: %r" % scritta,
            "Questa non sembra una targa italiana. Controlla come l'hai "
            "scritta.")
    tipo = targhe.che_cos_e(targa)
    servizio = "moto" if tipo == "moto" else "auto"
    fuori: Dict[str, Any] = {"targa": targa, "tipo": tipo}
    fuori.update(interroga(servizio, targa, dati, cartella, fresco))

    kw = _numero(fuori.get("kw"))
    # La categoria non arriva dal fornitore: la sa la forma della targa, che
    # e' l'unica cosa che distingue un'auto da una moto in questo servizio.
    categoria = "L3E" if servizio == "moto" else "M1"
    fuori["categoria"] = categoria
    fuori["neopatentati"] = patente.guidabile_da_neopatentato(kw, massa,
                                                             categoria)
    fuori["patente"] = patente.patente_necessaria(
        categoria, _numero(fuori.get("cilindrata")), kw, massa)
    if massa:
        fuori["massa"] = massa      # detta da chi guarda, non dal fornitore

    if con_assicurazione:
        try:
            fuori["assicurazione"] = interroga("assicurazione", targa, dati,
                                               cartella, fresco)
        except VeicoloRifiutato as e:
            fuori["assicurazione"] = {"errore": e.utente}
    return fuori
