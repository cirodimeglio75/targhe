# Targhe — quel che va saputo prima di toccare qualsiasi cosa

## Si scrive solo in italiano

Ordine del proprietario, 5/09/2026: tutto quel che lui legge è in italiano —
risposte, commenti, messaggi di commit, nomi delle cose, testi delle app.
Restano in inglese solo le cose che non si possono cambiare: parole chiave,
nomi di librerie e di API, comandi.

## Non dipende da Ops!, e non deve cominciare

Questo codice è nato dentro il repository di Ops! e il 9/09/2026 si è
trasferito qui. Non importa una riga da lì e non deve importarla: se una
cosa serve a tutti e due (il modo di salvare un token, per dire), si
ricopia e si dichiara nel commento, come è stato fatto per il cliente sullo
stampo di `av/sms.py`. Le correzioni non passano da sole fra i due
repository — chi corregge di là deve ricordarsi di qua, e viceversa.

## Ogni chiamata costa

Circa venti centesimi. Prima di aggiungere una chiamata al fornitore ci si
chiede se la risposta ce l'abbiamo già in memoria, e ogni dato nuovo entra
in `memoria.SCADENZE` con la sua scadenza — i dati tecnici non cambiano mai,
la polizza sì. Un ciclo di ricerche senza memoria e senza tetto è il modo
noto di svuotare il portafoglio in un pomeriggio.

## Il grezzo si tiene

Finché i nomi dei campi non sono confermati sulla console del fornitore,
`normalizza()` tiene sempre `grezzo`. Non si toglie per pulizia: è l'unica
cosa che sicuramente non perde dati.

## Il banco prima del commit

    python3 prove/prova_cliente.py

Deve dire «tutto bene». Se una modifica cambia il comportamento apposta, si
cambia anche il banco nello stesso lotto — mai dopo.

## Non si promette quel che il fornitore non manda

La massa, la categoria, la classe Euro, il giorno di immatricolazione, la
potenza delle moto e la revisione **non arrivano** (documentazione
ufficiale Automotive 1.0.0). Dove servono, si chiedono a chi guarda o si
dichiara di non sapere. Non si stimano, non si deducono dal modello, non
si prendono da una tabella «di solito è così»: una massa inventata dice a
un neopatentato che può guidare un'auto che non può guidare.

## Il 302 non è una ridirezione

Sotto carico il fornitore risponde 302 con `/check_id/{id}`: si aspetta
chiedendo lì, e il rimando NON si segue in automatico (i token valgono per
percorso). `APRITORE` in `cliente.py` serve a questo — non si sostituisce
con `urllib.request.urlopen` per fare prima.

## Il costo nostro non esce dal server

`passaggio.LISTINO` ha due colonne. `pubblico` si mostra; `costo` e
`margine()` no: mai in una pagina, mai nel JSON, mai in un registro. È
protetto dai banchi, non dalla buona volontà — prima di aggiungere una
riga a una schermata, guarda da quale colonna la stai prendendo.

## I documenti d'identità sono la roba più delicata che tocchiamo

Prima di cambiare qualcosa in `pratiche.py` o nella rotta POST, rileggi le
regole in testa a quel file. In breve: il nome che arriva non tocca mai il
disco, il tipo si stabilisce guardando i primi byte, i documenti non si
riscaricano da nessuna rotta, e nei registri non finiscono né nomi né
targhe. Il banco `prove/prova_pratiche.py` prova ognuna di queste: se una
diventa rossa, non è un controllo da aggiustare, è una porta che si è
aperta.

## Tre mestieri, e le porte fra loro

Concessionaria, agenzia, amministrazione. Prima di toccare una rotta,
chiediti chi la può chiamare — e ricordati che a chi non ha diritto si
risponde «non esiste», mai «non è tuo». `prove/prova_area.py` prova ogni
porta: una concessionaria che vede le pratiche di un'altra non è un
controllo da aggiustare, è un cliente che legge i dati di un altro cliente.

## Lo stato di una pratica non si dichiara

«consegnata» vuol dire che i documenti ci sono, e si ricalcola guardando.
«finita» richiede il documento e la ricevuta. Non aggiungere un tasto che
imposti uno stato a mano: il conteggio del sabato si fida di quegli stati.

## Le fatture non si toccano alla leggera

Numerazione progressiva senza buchi né doppioni, imponibile separato dalle
anticipazioni art. 15, e niente emissione senza i dati fiscali. Prima di
cambiare qualcosa in `fatture.py`, rileggi i tre freni in testa al file: due
sono lì perché la risposta la deve dare un commercialista, non noi.

## L'orologio non deve mai fermarsi

`orologio.giro()` si può chiamare quante volte si vuole e non ripete quel
che ha già fatto: è il registro a garantirlo, non la fortuna. E il filo che
lo chiama ingoia qualunque guasto: un orologio che si ferma alla prima
posta rifiutata è un orologio che nessuno si accorge che è fermo.
