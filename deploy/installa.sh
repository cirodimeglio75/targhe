#!/bin/bash
# Installa Targhe su una macchina Debian/Ubuntu pulita. Si lancia da root:
#
#     bash deploy/installa.sh
#
# Non chiede niente e non indovina niente: quel che manca lo dice e si
# ferma. Rilanciarlo una seconda volta non fa danni.
set -euo pipefail

NOME=targhe
CASA=/opt/$NOME
DATI=/var/lib/$NOME
SEGRETI=/etc/$NOME
QUI="$(cd "$(dirname "$0")/.." && pwd)"
# La porta si puo' cambiare: su una macchina che ha gia' altre cose in
# funzione, 8073 puo' essere gia' presa.
#     PORTA=8074 bash deploy/installa.sh
PORTA=${PORTA:-8073}
SITO=${SITO:-agenzia.stopandgogaranzie.it}

echo "== Targhe: installazione da $QUI"

if [ "$(id -u)" != "0" ]; then
	echo "Va lanciato da root (sudo bash deploy/installa.sh)." >&2
	exit 1
fi

command -v python3 >/dev/null || { echo "Serve python3." >&2; exit 1; }
python3 - <<'PY' || { echo "Serve Python 3.9 o piu' nuovo." >&2; exit 1; }
import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
echo "-- python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))'): va bene"
# Il programma non ha dipendenze: solo la libreria che viene con Python.
# E' una scelta, e questa riga la ricorda a chi installa.

# La porta: se e' gia' occupata da qualcun altro NON si prosegue. Due
# programmi sulla stessa porta vuol dire che uno dei due non parte piu', e
# scoprirlo dopo, su una macchina che ha gia' roba in funzione, e' il modo
# di spegnere qualcosa che funzionava.
chi_tiene() {
	ss -ltnp 2>/dev/null | awk -v p=":$1" '$4 ~ p"$" {print $NF}' | head -1
}
prima_libera() {
	local p
	for p in $(seq 8073 8199); do
		[ -z "$(chi_tiene "$p")" ] && { echo "$p"; return; }
	done
}

if [ "$PORTA" = "auto" ]; then
	PORTA=$(prima_libera)
	[ -n "$PORTA" ] || { echo "Nessuna porta libera fra 8073 e 8199." >&2; exit 1; }
	echo "-- porta scelta da sola: $PORTA"
fi

CHI_PORTA=$(chi_tiene "$PORTA")
if [ -n "$CHI_PORTA" ]; then
	if echo "$CHI_PORTA" | grep -q "$NOME"; then
		echo "-- porta $PORTA: la tiene gia' Targhe, la riprendo"
	else
		# Suggerire un numero a caso e' inutile: su questa macchina puo'
		# essere occupato pure quello. Se ne cerca uno VERO, adesso.
		LIBERA=$(prima_libera)
		echo "La porta $PORTA e' gia' occupata da: $CHI_PORTA" >&2
		if [ -n "$LIBERA" ]; then
			echo "La prima libera su questa macchina e' la $LIBERA:" >&2
			echo "    PORTA=$LIBERA bash deploy/installa.sh" >&2
			echo "oppure lascia scegliere a me:" >&2
			echo "    PORTA=auto bash deploy/installa.sh" >&2
		fi
		exit 1
	fi
fi
echo "-- porta $PORTA: si puo' usare"

id -u $NOME >/dev/null 2>&1 || useradd --system --home "$CASA" --shell /usr/sbin/nologin $NOME
echo "-- utente $NOME: c'e'"

mkdir -p "$CASA" "$DATI" "$SEGRETI"
# Il programma sta in una cartella che NON puo' riscrivere: se un giorno
# qualcuno trova un buco, non si riscrive il programma da solo.
cp -r "$QUI"/{server.py,veicoli,pagine,strumenti,prove,LEGGIMI.md} "$CASA"/
chown -R root:root "$CASA"
chown -R $NOME:$NOME "$DATI"
chmod 750 "$DATI"

if [ ! -f "$SEGRETI/ambiente" ]; then
	cp "$QUI/deploy/ambiente.esempio" "$SEGRETI/ambiente"
	chown root:$NOME "$SEGRETI/ambiente"
	chmod 640 "$SEGRETI/ambiente"
	echo "-- scritto $SEGRETI/ambiente: VA RIEMPITO (token e posta)"
else
	echo "-- $SEGRETI/ambiente: c'e' gia', non lo tocco"
fi

sed "s|--porta 8073|--porta $PORTA|" "$QUI/deploy/targhe.service" \
	> /etc/systemd/system/targhe.service
systemctl daemon-reload
systemctl enable --now targhe
sleep 1
systemctl --no-pager --lines=5 status targhe || true

# --- Caddy: il file del sito, SENZA toccare quello che c'e' gia'
PEZZO=/etc/caddy/$SITO.caddy
if [ -d /etc/caddy ]; then
	sed -e "s|agenzia.stopandgogaranzie.it|$SITO|" \
	    -e "s|127.0.0.1:8073|127.0.0.1:$PORTA|" \
	    "$QUI/deploy/Caddyfile" > "$PEZZO"
	echo "-- scritto $PEZZO"
	if grep -q "import $PEZZO" /etc/caddy/Caddyfile 2>/dev/null; then
		echo "-- il Caddyfile lo importa gia'"
		if caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
			systemctl reload caddy && echo "-- Caddy ricaricato"
		else
			echo "!! il Caddyfile non e' valido: NON ricarico" >&2
		fi
	else
		# Il Caddyfile che c'e' puo' servire altri siti: non lo si
		# sovrascrive e non ci si scrive dentro da soli. Si dice la
		# riga da aggiungere, e la aggiunge una persona che sa cosa
		# c'e' gia' li' dentro.
		echo
		echo "!! MANCA UNA RIGA in /etc/caddy/Caddyfile. Aggiungila IN FONDO,"
		echo "   fuori da qualunque parentesi graffa:"
		echo
		echo "       import $PEZZO"
		echo
		echo "   poi:  caddy validate --config /etc/caddy/Caddyfile"
		echo "         systemctl reload caddy"
		echo
		echo "   Il Caddyfile che c'e' NON l'ho toccato: puo' servire altri"
		echo "   siti, e sovrascriverlo li spegnerebbe."
	fi
fi

echo
echo "== Il programma gira su 127.0.0.1:$PORTA, e il sito e' $SITO."
echo
echo "== Il primo conto (senza, non entra nessuno):"
echo "   sudo -u $NOME python3 -c \"import sys; sys.path.insert(0,'$CASA'); \\"
echo "     from pathlib import Path; from veicoli import conti; \\"
echo "     conti.crea(Path('$DATI'), 'admin', 'UNA-PAROLA-LUNGA', \\"
echo "     'amministrazione', nome='Amministrazione')\""
