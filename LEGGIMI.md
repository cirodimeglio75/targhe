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

    python3 prove/prova_cliente.py   # il cervello: 35 controlli
    python3 prove/prova_pagina.py    # la pagina: 26 controlli
    python3 prove/prova_pratiche.py  # i documenti: 19 controlli
    python3 prove/prova_area.py      # il giro intero: 41 controlli

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
| `veicoli/pratiche.py` | quali documenti servono per ogni pratica, dove finiscono, e chi può vederli |
| `veicoli/conti.py` | chi entra: concessionaria, agenzia, amministrazione |
| `veicoli/conteggio.py` | plafond, conteggio del sabato, nota di saldo e il suo PDF |
| `veicoli/pdf.py` | un PDF scritto a mano, senza librerie |
| `veicoli/posta.py` | la nota che arriva per posta, col PDF attaccato |
| `pagine/area.py` | le tre aree, una per mestiere |
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

## Il giro: concessionaria → agenzia → amministrazione

Tre mestieri, tre aree, una strada sola:

1. **la concessionaria** cerca una targa, apre la pratica (il prezzo si
   prende dai kW) e fotografa i documenti. Se il **plafond** non basta, la
   pratica non parte — e si ferma **prima** che qualcuno fotografi
   qualcosa;
2. **l'agenzia** vede tutte le pratiche **raggruppate per concessionaria**,
   apre i documenti caricati, e se qualcosa non va **scrive un messaggio
   dentro la pratica**. Finito il lavoro carica il **documento della
   pratica** e la **ricevuta**, e la chiude;
3. **l'amministrazione** assegna i plafond, e **il sabato** emette la
   **nota di saldo** per ogni concessionaria: le pratiche finite e non
   ancora pagate, con il totale. Quando la concessionaria salda (entro il
   lunedì), la nota si segna pagata e **il plafond torna libero**.

### Le porte, e chi non passa

- **una concessionaria vede solo le sue pratiche.** A chi chiede quelle di
  un'altra si risponde «non esiste», non «non è tua»: la seconda frase
  racconta a uno sconosciuto che quella pratica c'è;
- **i documenti della concessionaria li carica la concessionaria**, quelli
  di fine lavoro l'agenzia. Ognuno i suoi;
- **una pratica non si chiude a mano**: si chiude quando il documento e la
  ricevuta ci sono davvero. Uno stato dichiarabile a vuoto è uno stato di
  cui non ci si può fidare al conteggio del sabato;
- **i plafond e le note li muove solo l'amministrazione**, e lo dice la
  rotta, non una schermata nascosta;
- **la parola d'ordine sta impastata con `scrypt`**, ognuna col suo sale, e
  il confronto è a tempo costante;
- **la chiave di sessione vive in un biscotto `HttpOnly`, `SameSite=Lax`**,
  e in più ogni modulo che arriva da un'altra casa viene rifiutato;
- **i documenti si aprono solo da dentro la pratica**, con il tipo che
  abbiamo stabilito noi guardando i byte, `nosniff` e una regola che
  spegne qualunque cosa il file provasse a eseguire.

### Il primo conto

Non c'è registrazione da fuori: i conti li fa l'amministrazione. Il
primissimo si crea da riga di comando — il server lo scrive all'avvio
quando non ne trova nessuno:

    python3 -c "from pathlib import Path; from veicoli import conti; \
      conti.crea(Path('dati'), 'admin', 'parolalunga', 'amministrazione', \
                 nome='Amministrazione')"

### La nota di saldo è un documento

Quando l'amministrazione emette la nota, nasce anche il suo **PDF** — un
foglio A4 con la concessionaria, le pratiche riga per riga, il totale e
*«Da saldare entro lunedì …»*. Si scarica dall'area (della concessionaria,
o dell'amministrazione) e, se la posta è configurata, **parte per posta
con il PDF attaccato**.

Il PDF si fabbrica **una volta sola**, quando la nota nasce, e poi non si
rifà: rigenerarlo a ogni richiesta vorrebbe dire che una modifica al
programma cambia una carta già mandata a un cliente.

`veicoli/pdf.py` lo scrive a mano, senza librerie: per venti righe di
testo su un foglio, una libreria di PDF è un pacchetto grosso da tenere
aggiornato con le sue falle. Se un giorno servirà un documento più ricco,
quello è il momento di prendere una libreria — non di far crescere quel
file.

**La posta si configura dall'ambiente**, e se manca il conteggio non
fallisce: la nota resta scaricabile e l'amministrazione **legge** che non
è partita, invece di crederlo.

    SERVER_POSTA=smtp.esempio.it   PORTA_POSTA=587
    UTENTE_POSTA=...               PAROLA_POSTA=...
    DA_POSTA="Targhe <note@esempio.it>"

L'indirizzo della concessionaria si mette dall'area amministrazione. Se è
vuoto la nota non parte, e lo si legge.

### Cosa manca ancora, di questo giro

- **nessuno sollecita il lunedì**: il plafond resta occupato finché non si
  salda, e quello frena da solo, ma un promemoria non c'è;
- **i documenti restano sul nostro disco**: non c'è un modo per l'agenzia
  di scaricarli in blocco né una cancellazione automatica a pratica chiusa.
