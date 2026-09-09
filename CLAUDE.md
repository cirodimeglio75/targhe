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
