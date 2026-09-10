#!/bin/bash
# Come sta Targhe su questa macchina. Guarda e basta, non cambia niente.
#
#     bash deploy/stato.sh
#
# Serve per rispondere a una domanda sola — «e' online?» — senza dover
# ricordare sette comandi diversi. Tutto quel che stampa si puo' mandare
# a qualcuno: non ci sono dentro token ne' parole d'ordine.
set -uo pipefail

NOME=targhe
DATI=/var/lib/$NOME
SITO=${SITO:-agenzia.stopandgogaranzie.it}

echo "== Come sta Targhe — $(date '+%d/%m/%Y %H:%M')"
echo

# --- il servizio
if systemctl is-active --quiet $NOME 2>/dev/null; then
	echo "-- il servizio: IN PIEDI (da $(systemctl show -p ActiveEnterTimestamp --value $NOME))"
else
	echo "-- il servizio: FERMO o non installato"
	systemctl status $NOME --no-pager --lines=8 2>&1 | sed 's/^/   /' | tail -10
fi

# --- su che porta ascolta davvero
PORTA=$(systemctl show -p ExecStart --value $NOME 2>/dev/null | grep -o -- '--porta [0-9]*' | awk '{print $2}')
PORTA=${PORTA:-8073}
if ss -ltn 2>/dev/null | grep -q ":$PORTA "; then
	echo "-- ascolta sulla porta $PORTA"
else
	echo "-- NON ascolta sulla porta $PORTA"
fi

# --- risponde?
SALUTE=$(curl -sS --max-time 5 "http://127.0.0.1:$PORTA/salute" 2>&1)
if echo "$SALUTE" | grep -q '"in_piedi"'; then
	echo "-- risponde in casa: $SALUTE"
else
	echo "-- in casa NON risponde: $SALUTE"
fi

# --- Caddy davanti
if [ -f "/etc/caddy/$SITO.caddy" ]; then
	PERMESSI=$(stat -c '%a %U:%G' "/etc/caddy/$SITO.caddy" 2>/dev/null)
	echo "-- il file del sito: c'e' ($PERMESSI)"
	# Se Caddy non lo puo' leggere, `validate` da root passa lo stesso e
	# il ricaricamento fallisce: il caso piu' difficile da indovinare.
	UTENTE_CADDY=$(systemctl show -p User --value caddy 2>/dev/null)
	UTENTE_CADDY=${UTENTE_CADDY:-caddy}
	if id "$UTENTE_CADDY" >/dev/null 2>&1; then
		if sudo -u "$UTENTE_CADDY" test -r "/etc/caddy/$SITO.caddy" 2>/dev/null; then
			echo "   e l'utente $UTENTE_CADDY lo puo' leggere"
		else
			echo "   MA l'utente $UTENTE_CADDY NON lo puo' leggere:"
			echo "      chmod 644 /etc/caddy/$SITO.caddy"
		fi
	fi
else
	echo "-- il file del sito: MANCA"
fi
if grep -q "import /etc/caddy/$SITO.caddy" /etc/caddy/Caddyfile 2>/dev/null; then
	echo "-- il Caddyfile lo importa: si'"
else
	echo "-- il Caddyfile NON lo importa: manca la riga"
	echo "       import /etc/caddy/$SITO.caddy"
fi
systemctl is-active --quiet caddy 2>/dev/null \
	&& echo "-- Caddy: in piedi" || echo "-- Caddy: fermo"

# La configurazione e' valida? Se non lo e', Caddy sta ancora servendo la
# vecchia e la riga nuova non e' mai entrata in funzione.
if command -v caddy >/dev/null; then
	if caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
		echo "-- la configurazione di Caddy: valida"
	else
		echo "-- la configurazione di Caddy: NON valida"
		caddy validate --config /etc/caddy/Caddyfile 2>&1 | sed 's/^/   /' | head -6
	fi
fi

# La prova che divide in due il problema: si bussa a Caddy da DENTRO la
# macchina, dicendogli il nome del sito. Se di qui risponde, Caddy e il
# certificato stanno bene e il guaio e' fuori (firewall, o il nome visto
# da internet). Se non risponde, il guaio e' qui.
DENTRO=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 \
	--resolve "$SITO:443:127.0.0.1" "https://$SITO/" 2>&1)
echo "-- da dentro la macchina, con SNI: $DENTRO"
if [ "$DENTRO" = "000" ]; then
	echo "   (Caddy non presenta un certificato per questo nome: o non ha"
	echo "    ancora finito di prenderlo, o non conosce il sito)"
fi

# --- da fuori
FUORI=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 \
	"https://$SITO/" 2>&1)
echo "-- https://$SITO/ risponde: $FUORI"
if [ "$FUORI" = "000" ]; then
	echo "   (000 vuol dire che non si e' aperto il collegamento: o il"
	echo "    certificato non c'e' ancora, o Caddy non conosce il sito)"
fi

# --- i conti
if [ -f "$DATI/conti.json" ]; then
	QUANTI=$(python3 -c "import json;print(len(json.load(open('$DATI/conti.json'))))" 2>/dev/null || echo "?")
	echo "-- conti creati: $QUANTI"
else
	echo "-- conti creati: NESSUNO — nessuno puo' entrare finche' non se ne"
	echo "   fa uno di amministrazione"
fi

# --- il token del fornitore, senza mostrarlo
if grep -q '^TOKEN_VEICOLI=.\+' /etc/$NOME/ambiente 2>/dev/null; then
	echo "-- token Openapi: c'e'"
else
	echo "-- token Openapi: manca (le ricerche targa non funzioneranno)"
fi
if grep -q '^SERVER_POSTA=.\+' /etc/$NOME/ambiente 2>/dev/null; then
	echo "-- posta: configurata"
else
	echo "-- posta: non configurata (note e solleciti non partiranno)"
fi

echo
echo "Cosa dice Caddy di questo sito:"
journalctl -u caddy --no-pager --lines=200 2>/dev/null \
	| grep -i -e "$SITO" -e "certificate" -e "acme" -e "error" \
	| tail -8 | sed 's/^/   /' || echo "   (niente)"

echo
echo "Gli ultimi respiri del programma:"
journalctl -u $NOME --no-pager --lines=8 2>/dev/null | sed 's/^/   /' \
	|| echo "   (nessun registro)"
