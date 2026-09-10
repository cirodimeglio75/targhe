# Mettere Targhe sul server

Per `agenzia.stopandgogaranzie.it`.

## Prima di tutto: questi comandi vanno dati SUL SERVER

Non sul Mac. Sul Mac `/root` non esiste nemmeno, e il `sudo` chiede la
password del Mac, che col server non c'entra niente. Dal Terminale del Mac
si entra nel server così, e **solo dopo** si danno i comandi:

    ssh root@62.238.104.99

Da lì in poi tutto quello che segue è dentro quella finestra: il segno del
prompt cambia, e non dice più `MacBook-Pro-di-Ciro`.

## Prima di cominciare

- il nome **agenzia.stopandgogaranzie.it deve già puntare a questa
  macchina** (record A verso il suo indirizzo). Senza, Caddy non riesce a
  prendere il certificato e il sito resta senza HTTPS;
- le porte **80 e 443** devono essere aperte da fuori;
- serve **Python 3.9 o più nuovo** e **Caddy**. Il programma non ha nessuna
  altra dipendenza: usa solo la libreria che viene con Python, e nemmeno per
  fare i PDF.

## Il repository è privato: prima la chiave

Il server non ha un conto GitHub, quindi un `git clone` con l'indirizzo
`https://` gli chiederebbe una password che non ha. Si fa una chiave, una
volta sola, e poi funziona per sempre — anche per gli aggiornamenti:

    ssh-keygen -t ed25519 -C "server targhe" -f /root/.ssh/id_targhe -N ""
    cat /root/.ssh/id_targhe.pub

Quella riga che stampa si incolla su GitHub, nel repository `targhe`:
**Settings → Deploy keys → Add deploy key**. Titolo qualsiasi, spunta
«Allow write access» NON serve. Poi, sempre sul server:

    printf 'Host github.com\n  IdentityFile /root/.ssh/id_targhe\n' >> /root/.ssh/config

## I tre comandi (sul server)

    git clone git@github.com:cirodimeglio75/targhe.git /root/targhe
    cd /root/targhe
    bash deploy/controlla.sh        # guarda e basta, non cambia niente
    bash deploy/installa.sh         # questo installa

### La strada corta, se il Mac ha già GitHub

Se sul Mac il repository ce l'hai già, invece della chiave puoi copiarlo:

    git clone https://github.com/cirodimeglio75/targhe ~/targhe
    scp -r ~/targhe root@62.238.104.99:/root/targhe

E poi entrare col `ssh` e continuare da `bash deploy/controlla.sh`.

Poi, una volta sola:

1. **riempi `/etc/targhe/ambiente`** — il token dell'automotive di Openapi
   e i dati della posta. Il file è già lì, con dentro i nomi dei campi;
2. **aggiungi una riga al Caddyfile.** Lo script scrive il file del sito e
   ti dice la riga da aggiungere in fondo a `/etc/caddy/Caddyfile`:
   `import /etc/caddy/agenzia.stopandgogaranzie.it.caddy`. Il Caddyfile che
   c'è **non viene toccato**: su una macchina che serve già altri siti,
   sovrascriverlo li spegnerebbe tutti;
3. **fai il primo conto** dell'amministrazione:

       sudo -u targhe python3 /opt/targhe/strumenti/primo_conto.py

   Chiede tutto lui, e la parola d'ordine non si vede mentre la scrivi e
   non finisce nella cronologia della shell. Senza un conto non entra
   nessuno — e non c'è registrazione da fuori, apposta.

## Se la macchina ha già altre cose in funzione

`controlla.sh` lo dice. Due casi:

- **la porta 8073 è già occupata**: lo script cerca lui la prima libera e
  te la dice, oppure sceglie da solo:

      PORTA=auto bash deploy/installa.sh

  Il numero scelto vale dappertutto: unità di sistema e file di Caddy.

- **Caddy gira già**: bene, non va reinstallato. Lo script scrive solo il
  file del sito nuovo e lascia il resto com'è.

## Dopo

    sudo bash deploy/aggiorna.sh

Fa girare i cinque banchi **prima** di sostituire il programma: se qualcosa
è rosso, non mette su niente. I dati in `/var/lib/targhe` non si toccano —
lì dentro ci sono documenti d'identità e fatture già emesse.

## Com'è messo

    /opt/targhe        il programma. L'utente del servizio NON lo può
                       riscrivere: se un giorno qualcuno trova un buco, non
                       si riscrive il programma da solo
    /var/lib/targhe    i dati: conti, pratiche, documenti, note, fatture.
                       È l'unico posto dove il servizio può scrivere
    /etc/targhe        i segreti, leggibili solo da root e dal servizio

Il programma ascolta **solo su 127.0.0.1**: da fuori si passa da Caddy, che
fa l'HTTPS. L'unità di sistema ha le cinghie strette (`ProtectSystem`,
`NoNewPrivileges`, niente scrittura fuori dai dati) perché qui dentro
passano documenti d'identità.

## Cosa NON fa questa installazione

- **non fa i salvataggi.** Documenti d'identità e fatture emesse stanno su
  un disco solo: prima di aprire ai clienti veri va deciso dove finisce la
  copia, e per quanto si tiene;
- **non manda niente allo SdI**: la fattura elettronica è un pezzo a parte;
- **non cancella niente**: i documenti restano finché non si decide quanto
  vanno tenuti.
