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
per intero e non si spende un centesimo. Prova `CX118GD` (auto grossa),
`DD222DD` (auto piccola: chiede la massa), `AB12345` (moto), `ZZ999ZZ`
(targa che non risulta).

I due banchi, che girano da soli:

    python3 prove/prova_cliente.py   # il cervello: 31 controlli
    python3 prove/prova_pagina.py    # la pagina: 26 controlli
    python3 prove/prova_pratiche.py  # i documenti: 20 controlli

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
| `veicoli/passaggio.py` | il listino del passaggio di proprietà, dai kW. **Due colonne: solo `pubblico` esce di qui** |
| `veicoli/pratiche.py` | quali documenti servono per ogni pratica, e dove finiscono quelli caricati |
| `pagine/pratica.py` | l'elenco dei documenti con le spunte, e i tasti per fotografare |
| `strumenti/finto_openapi.py` | il fornitore finto del banco, che conta le domande |
| `prove/prova_cliente.py` | il banco del cervello |
| `prove/prova_pagina.py` | il banco della pagina |

## Cosa manda il fornitore, e cosa no

I nomi dei campi vengono dalla documentazione ufficiale (*API Reference
Automotive 1.0.0*, letta il 9/09/2026), non da un'ipotesi. Quel che conta
è soprattutto la seconda colonna:

| Arriva | Non arriva |
|---|---|
| marca, modello, versione, descrizione | la **massa** del veicolo |
| **anno** di immatricolazione | il giorno e il luogo |
| cilindrata, alimentazione | la categoria (M1, L3E…) |
| kW, CV, cavalli fiscali (solo auto) | la **potenza delle moto** |
| telaio, porte, ABS, airbag, KType | la classe Euro |
| compagnia, scadenza e stato della polizza | la **revisione** |

Tre conseguenze, tutte visibili nella pagina:

1. **I neopatentati si possono dire per metà.** Sopra i 70 kW un'auto è
   vietata comunque, e lì si risponde con certezza. Sotto, la risposta
   dipende dalla massa: la pagina la chiede a chi guarda (sta sul libretto,
   riga G) invece di inventarne una media. Una massa inventata direbbe a un
   ragazzo che può guidare un'auto che non può guidare.
2. **La patente per una moto si dice a metà**: senza potenza, sopra i 125 cc
   la risposta è «A2 o A, secondo la potenza».
3. **La revisione per l'Italia non esiste in questo servizio.** C'è solo per
   il Regno Unito (`/UK-mot`). Era la domanda aperta dello studio: serve un
   altro fornitore, o si toglie dall'elenco delle cose promesse.

## La coda del fornitore, che non è un errore

Sotto carico il servizio taglia a dieci secondi e risponde **302** con un
identificativo: la risposta si va a prendere su `/check_id/{id}` finché non
è pronta. Il rimando **non si segue in automatico** — lo dice la
documentazione — perché i token valgono per percorso, e seguirlo porterebbe
il token su una rotta per cui potrebbe non valere: si vedrebbe un «Wrong
Token» per una richiesta andata benissimo. Il finto fornitore sa fare anche
questo (`VEICOLI_LENTO=1`), e il banco lo prova.

## Il token, e perché non c'è una pagina per incollarlo

Come per gli SMS di Ops!: vince quello salvato dall'amministrazione
(`salva_token`), `TOKEN_VEICOLI` nell'ambiente fa da fondo. `carta()` legge
cosa il token dichiara di sé — a cosa serve e quando scade — perché quando
il fornitore risponde «Wrong Token» la risposta sta quasi sempre lì dentro.

Una pagina web per incollarlo **non c'è apposta**: finché non esiste
un'amministrazione con un'identità dietro, sarebbe un modulo che regala le
nostre credenziali a chiunque arrivi alla porta. Il server ascolta su
127.0.0.1 e vuole un reverse proxy davanti, che faccia HTTPS.

## Il passaggio di proprietà, e la riga da non attraversare

Il passaggio si paga **in base ai kW** — la voce **P.2** del libretto — e i
kW sono l'unico dato di potenza che il fornitore manda. Quindi la scheda
sa dire da sola quanto costa: è l'unico prezzo che questa app possiede.

`veicoli/passaggio.py` tiene **due colonne**: `pubblico`, il prezzo di
listino, e `costo`, quanto costa a noi. **Solo la prima esce da questo
server.** Il costo e il margine non entrano nella pagina, non entrano nel
JSON delle schermate native, non si scrivono nei registri. I due banchi lo
verificano cercando quei numeri nell'HTML e nel JSON: se un giorno
trapelano, il banco diventa rosso.

Dove la foto del listino non si legge (55, 82, 83-85, 86, 146-147 kW) il
valore è `None` e la pagina dice che il prezzo va chiesto. Sopra i 147 kW
il listino finisce e non si estrapola: un prezzo inventato in una
schermata è una promessa che poi qualcuno deve mantenere allo sportello.

## Le pratiche, e i documenti che ci caricano dentro

Dalla scheda si comincia una pratica: mini passaggio, da società a privato,
perdita di possesso, immatricolazione. Quali documenti servano lo dice il
foglio scritto a mano dell'agenzia, non un'idea nostra. La pagina elenca,
spunta quel che è arrivato e apre la fotocamera del telefono per il resto —
senza una riga di JavaScript.

**Manca il passaggio fra due privati**, che è il caso più comune di tutti:
sul foglio non c'è, quindi non è qui. Va chiesto all'agenzia e aggiunto in
`pratiche.TIPI`. Una lista di documenti inventata manda una persona a
fotografare le carte due volte.

### Le regole di chi accetta documenti d'identità

Qui dentro non passano file: passano dati personali di chi si fida di noi.
Tutte queste sono applicate e provate dal banco:

- **il nome che arriva dal telefono non diventa mai un percorso**: si tiene
  per mostrarlo, si scrive con un nome nostro;
- **si guarda dentro il file**, non l'estensione: un `.jpg` che comincia con
  `<?php` non entra. Passano JPG, PNG, HEIC (gli iPhone fotografano così) e
  PDF;
- **l'indirizzo della pratica è il permesso**, come il numero di telefono in
  Ops!: lungo, non indovinabile. Finché non c'è un'identità vera è l'unica
  protezione, ed è per questo che **i documenti caricati non si riscaricano
  da nessuna rotta**: entrano e basta;
- **nei registri finisce l'identificativo della pratica**, mai il nome del
  documento né la targa;
- tetti: 8 MB a documento, 12 MB di busta, 20 documenti per pratica.

**Quel che manca, e non è codice**: informativa, tempo di conservazione,
cancellazione a pratica chiusa, e il modo in cui l'agenzia ritira i
documenti. Vanno scritti prima che questa roba veda un utente vero.
