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

cp "$QUI/deploy/targhe.service" /etc/systemd/system/targhe.service
systemctl daemon-reload
systemctl enable --now targhe
sleep 1
systemctl --no-pager --lines=5 status targhe || true

echo
echo "== Il programma gira su 127.0.0.1:8073."
echo "   Davanti ci va Caddy: copia deploy/Caddyfile in /etc/caddy/Caddyfile"
echo "   e ricarica (systemctl reload caddy). Prima pero' il nome"
echo "   agenzia.stopandgogaranzie.it deve puntare a QUESTA macchina,"
echo "   senno' il certificato non si prende."
echo
echo "== Il primo conto (senza, non entra nessuno):"
echo "   sudo -u $NOME python3 -c \"import sys; sys.path.insert(0,'$CASA'); \\"
echo "     from pathlib import Path; from veicoli import conti; \\"
echo "     conti.crea(Path('$DATI'), 'admin', 'UNA-PAROLA-LUNGA', \\"
echo "     'amministrazione', nome='Amministrazione')\""
