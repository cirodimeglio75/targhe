# Targhe

Da una targa italiana: dati del veicolo, polizza RCA, e chi lo può guidare.
Ci sono il **cervello** — la parte che parla con Openapi, ricorda le
risposte e fa i conti che sa fare da sola — e la **pagina**, che è dove si
prova tutto e dove sta il computer.

## Dove sta, e cosa manca

Questo repository è la casa: ci è arrivato il 9/09/2026 dal clone di Ops!,
dov'era nato parcheggiato in attesa che il repository esistesse. Non
dipende da Ops! in nessun punto, e non deve cominciare.

Mancano le **schermate native**, gemelle Android e iPhone — e quando si
faranno chiedono le stesse rotte di qui con `Accept: application/json`,
non rotte loro: un'API parallela sarebbe una seconda verità da tenere
allineata. Lo studio che dice perché e con quali conti sta in Ops!, in
`studi/targa-openapi.md`.

Manca anche il **modo di vendere** (crediti, tetti, pacchetti), che nello
studio è il nodo vero: qui non c'è nessun limite di spesa, quindi il
server non va messo su internet aperto com'è.

## Come si prova, adesso, senza spendere niente

    python3 server.py --finto        # poi http://127.0.0.1:8073

`--finto` accende un fornitore finto dentro il server: la pagina funziona
per intero e non si spende un centesimo. Prova `CX118GD` (auto),
`AB12345` (moto), `ZZ999ZZ` (targa che non risulta).

I due banchi, che girano da soli:

    python3 prove/prova_cliente.py   # il cervello: 20 controlli
    python3 prove/prova_pagina.py    # la pagina: 20 controlli

Controllano le cose che sbagliate si pagano: la memoria che non ricorda
(soldi), il «non risulta» che sembra un guasto (recensioni), il token
assente che esplode invece di spiegarsi (assistenza), e un campo
avvelenato dal fornitore che finisce a schermo come programma invece che
come testo (guai).

## Cosa c'è dentro

| file | cosa fa |
|---|---|
| `server.py` | due rotte: la pagina e `/targa/AB123CD`. Tutte e due rispondono in JSON a chi lo chiede |
| `pagine/scheda.py` | la faccia: la ricerca e la scheda. Qui dentro non si chiede niente a nessuno |
| `veicoli/targa.py` | pulisce e riconosce la targa: una targa storpiata si ferma qui e non costa una chiamata |
| `veicoli/cliente.py` | chiede a Openapi (`/IT-car`, `/IT-bike`, `/IT-insurance`), traduce, spiega i guasti |
| `veicoli/memoria.py` | ricorda le risposte: la stessa targa non si paga due volte |
| `veicoli/patente.py` | neopatentati e patente necessaria: il conto lo facciamo noi, costa zero |
| `strumenti/finto_openapi.py` | il fornitore finto del banco, che conta le domande |
| `prove/prova_cliente.py` | il banco del cervello |
| `prove/prova_pagina.py` | il banco della pagina |

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

## Il token, e perché non c'è una pagina per incollarlo

Come per gli SMS di Ops!: vince quello salvato dall'amministrazione
(`salva_token`), `TOKEN_VEICOLI` nell'ambiente fa da fondo. `carta()` legge
cosa il token dichiara di sé — a cosa serve e quando scade — perché quando
il fornitore risponde «Wrong Token» la risposta sta quasi sempre lì dentro.

Una pagina web per incollarlo **non c'è apposta**: finché non esiste
un'amministrazione con un'identità dietro, sarebbe un modulo che regala le
nostre credenziali a chiunque arrivi alla porta. Il server ascolta su
127.0.0.1 e vuole un reverse proxy davanti, che faccia HTTPS.
