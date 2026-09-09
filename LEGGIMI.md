# Targhe — il cervello, prima della faccia

Da una targa italiana: dati del veicolo, polizza RCA, e chi lo può guidare.
Questo è il **cliente server** — la parte che parla con Openapi, ricorda le
risposte e fa i conti che sa fare da sola.

## Dove sta, e cosa manca

Questo repository è la casa: ci è arrivato il 9/09/2026 dal clone di Ops!,
dov'era nato parcheggiato in attesa che il repository esistesse. Non
dipende da Ops! in nessun punto, e non deve cominciare.

Manca tutto il resto: la pagina web (che è dove si prova e dove sta il
computer) e le schermate native, gemelle Android e iPhone, che parlano
JSON sulle stesse rotte della pagina. Lo studio che dice perché e con
quali conti sta in Ops!, in `studi/targa-openapi.md`.

## Come si prova, adesso, senza spendere niente

    python3 prove/prova_cliente.py

Fa partire un finto fornitore, chiede una targa, e controlla le cose che
sbagliate si pagano: la memoria che non ricorda (soldi), il «non risulta»
che sembra un guasto (recensioni), il token assente che esplode invece di
spiegarsi (assistenza). Se stampa «tutto bene», il cliente fa quel che dice.

Per giocarci a mano, col finto:

    python3 strumenti/finto_openapi.py 8612 &
    BASE_VEICOLI=http://127.0.0.1:8612 TOKEN_VEICOLI=finto python3 -c \
      "from veicoli import scheda; import json; print(json.dumps(scheda('CX118GD'), indent=2, ensure_ascii=False))"

## Cosa c'è dentro

| file | cosa fa |
|---|---|
| `veicoli/targa.py` | pulisce e riconosce la targa: una targa storpiata si ferma qui e non costa una chiamata |
| `veicoli/cliente.py` | chiede a Openapi (`/IT-car`, `/IT-bike`, `/IT-insurance`), traduce, spiega i guasti |
| `veicoli/memoria.py` | ricorda le risposte: la stessa targa non si paga due volte |
| `veicoli/patente.py` | neopatentati e patente necessaria: il conto lo facciamo noi, costa zero |
| `strumenti/finto_openapi.py` | il fornitore finto del banco, che conta le domande |
| `prove/prova_cliente.py` | il banco |

## Le due cose ancora da fare prima di fidarsi

1. **I nomi dei campi non sono confermati.** Dalla macchina dove è nato
   questo codice openapi.com è chiuso dal filtro di rete, quindi le mappe in
   `cliente.CAMPI` accettano più grafie per lo stesso dato e **tengono
   sempre il grezzo**. Mezz'ora sulla console col nostro token, e si
   aggiustano lì senza toccare altro.
2. **La revisione non c'è.** Non l'ho trovata come servizio a sé nel
   catalogo: o è dentro `/IT-car` (e allora basta aggiungere una riga alle
   mappe), o serve un secondo fornitore. Il furto e i punti patente non ci
   sono e non ci saranno da Openapi: perché, sta nello studio
   (`studi/targa-openapi.md`, nel repository di Ops!).

## Il token

Come per gli SMS: vince quello salvato dall'amministrazione
(`salva_token`), `TOKEN_VEICOLI` nell'ambiente fa da fondo. `carta()` legge
cosa il token dichiara di sé — a cosa serve e quando scade — perché quando
il fornitore risponde «Wrong Token» la risposta sta quasi sempre lì dentro.
