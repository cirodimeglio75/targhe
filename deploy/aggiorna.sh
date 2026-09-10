#!/bin/bash
# Porta sulla macchina l'ultima versione, senza toccare i dati.
#
#     bash deploy/aggiorna.sh
#
# I dati stanno in /var/lib/targhe e non si toccano MAI: qui dentro ci
# sono documenti d'identita' e fatture emesse.
set -euo pipefail
NOME=targhe
CASA=/opt/$NOME
QUI="$(cd "$(dirname "$0")/.." && pwd)"
[ "$(id -u)" = "0" ] || { echo "Va lanciato da root." >&2; exit 1; }

echo "-- provo il programma prima di metterlo su"
cd "$QUI"
python3 prove/prova_cliente.py >/dev/null
python3 prove/prova_pagina.py >/dev/null
python3 prove/prova_pratiche.py >/dev/null
python3 prove/prova_area.py >/dev/null
python3 prove/prova_orologio.py >/dev/null
echo "   i cinque banchi sono verdi"

cp -r "$QUI"/{server.py,veicoli,pagine,strumenti,prove,LEGGIMI.md} "$CASA"/
chown -R root:root "$CASA"
systemctl restart $NOME
sleep 1
systemctl --no-pager --lines=5 status $NOME || true
