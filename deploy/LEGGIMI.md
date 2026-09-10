# Mettere Targhe sul server

Per `agenzia.stopandgogaranzie.it`. Tre comandi, da root, sulla macchina.

## Prima di cominciare

- il nome **agenzia.stopandgogaranzie.it deve già puntare a questa
  macchina** (record A verso il suo indirizzo). Senza, Caddy non riesce a
  prendere il certificato e il sito resta senza HTTPS;
- le porte **80 e 443** devono essere aperte da fuori;
- serve **Python 3.9 o più nuovo** e **Caddy**. Il programma non ha nessuna
  altra dipendenza: usa solo la libreria che viene con Python, e nemmeno per
  fare i PDF.

## I tre comandi

    git clone https://github.com/cirodimeglio75/targhe /root/targhe
    cd /root/targhe
    sudo bash deploy/installa.sh

Poi, una volta sola:

1. **riempi `/etc/targhe/ambiente`** — il token dell'automotive di Openapi
   e i dati della posta. Il file è già lì, con dentro i nomi dei campi;
2. **copia `deploy/Caddyfile` in `/etc/caddy/Caddyfile`** e
   `systemctl reload caddy`;
3. **fai il primo conto** dell'amministrazione: il comando esatto lo stampa
   `installa.sh` quando finisce. Senza, non entra nessuno — e non c'è
   registrazione da fuori, apposta.

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
