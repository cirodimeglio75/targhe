#!/bin/bash
# Prima di installare: guarda se la macchina e' pronta e se il nome punta
# qui. Non cambia niente, dice soltanto.
#
#     bash deploy/controlla.sh
#
# Serve perche' le tre cose che fanno fallire un'installazione sono sempre
# le stesse: il nome che punta altrove, la porta 80 occupata, e Caddy che
# non c'e'. Scoprirle prima costa un minuto, dopo costa un pomeriggio.
set -uo pipefail

NOME=${1:-agenzia.stopandgogaranzie.it}
echo "== Controllo per $NOME"
echo

# --- l'indirizzo di questa macchina, visto da fuori
MIO=""
for dove in "https://api.ipify.org" "https://ifconfig.me/ip" \
            "https://icanhazip.com"; do
	MIO=$(curl -sS --max-time 8 "$dove" 2>/dev/null | tr -d '[:space:]')
	[ -n "$MIO" ] && break
done
if [ -n "$MIO" ]; then
	echo "-- questa macchina, vista da internet: $MIO"
else
	echo "-- non riesco a sapere l'indirizzo pubblico di questa macchina"
fi

# --- dove punta il nome
PUNTA=$(getent ahostsv4 "$NOME" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')
if [ -z "$PUNTA" ]; then
	echo "-- il nome NON risolve: il record A non c'e' ancora, oppure"
	echo "   non e' ancora arrivato fin qui (di solito pochi minuti)"
else
	echo "-- il nome punta a: $PUNTA"
	if [ -z "$MIO" ]; then
		# Senza il nostro indirizzo non si puo' confrontare: dirlo, e
		# non dire «e' sbagliato», che sarebbe una bugia comoda.
		echo "   non so l'indirizzo di questa macchina, quindi non posso"
		echo "   dire se e' lei: controllalo a occhio"
	elif echo "$PUNTA" | grep -qw "$MIO"; then
		echo "   ED E' QUESTA MACCHINA: si puo' installare"
	else
		echo "   MA NON E' QUESTA MACCHINA ($MIO): il certificato non"
		echo "   si prendera'. Va corretto il record A nel pannello del"
		echo "   dominio."
	fi
fi

# --- chi ha le porte
echo
for porta in 80 443 8073; do
	CHI=$(ss -ltnp 2>/dev/null | awk -v p=":$porta" '$4 ~ p"$" {print $NF}' | head -1)
	if [ -n "$CHI" ]; then
		echo "-- porta $porta: occupata da $CHI"
	else
		echo "-- porta $porta: libera"
	fi
done

# --- gli attrezzi
echo
if command -v python3 >/dev/null; then
	echo "-- python3: $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"
else
	echo "-- python3: NON c'e'"
fi
command -v caddy >/dev/null && echo "-- caddy: c'e'" || \
	echo "-- caddy: NON c'e' (apt install caddy)"
command -v git >/dev/null && echo "-- git: c'e'" || echo "-- git: NON c'e'"

echo
echo "Se il nome punta qui, le porte 80 e 443 sono libere (o le tiene gia'"
echo "Caddy) e python3 c'e', si va con: sudo bash deploy/installa.sh"
