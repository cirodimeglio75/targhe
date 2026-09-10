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
	echo "-- il file del sito: c'e' (/etc/caddy/$SITO.caddy)"
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
echo "Gli ultimi respiri del programma:"
journalctl -u $NOME --no-pager --lines=8 2>/dev/null | sed 's/^/   /' \
	|| echo "   (nessun registro)"
