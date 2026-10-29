#!/usr/bin/env bash
# Pone al centinela de Orión a vigilar este servidor (ver centinela/README.md). Se puede repetir: así
# también se actualiza, porque lo que corre como root es una copia en /opt que solo root puede cambiar.
#   ./centinela/instalar.sh            -> bloquea solo y avisa por WhatsApp
#   ./centinela/instalar.sh avisar     -> solo avisa, no bloquea nada (para probar unos días)
set -euo pipefail
cd "$(dirname "$0")/.."
YO=$(id -un)
GRUPO=$(id -gn)
MODO=${1:-actuar}
DESTINO=/opt/orion-centinela
CONF=/etc/orion-centinela.conf
paso() { echo; echo "== $*"; }

[ "$MODO" = actuar ] || [ "$MODO" = avisar ] || { echo "Uso: $0 [avisar]"; exit 1; }

paso "Herramientas (nftables, ss)"
sudo apt-get install -y -qq nftables iproute2 python3 >/dev/null

paso "Copia del centinela en $DESTINO (solo root puede cambiarla)"
sudo install -d -o root -g root -m 755 "$DESTINO"
sudo install -o root -g root -m 755 centinela/centinela.py "$DESTINO/centinela.py"
sudo install -o root -g root -m 644 centinela/reglas.nft "$DESTINO/reglas.nft"
sudo install -o root -g root -m 644 centinela/web.py "$DESTINO/web.py"
sudo ln -sf "$DESTINO/centinela.py" /usr/local/sbin/orion-centinela

paso "Carpetas: avisos (los lee el puente de WhatsApp) y registro"
sudo install -d -o root -g root -m 711 /var/lib/orion-centinela
sudo install -d -o root -g "$GRUPO" -m 770 /var/lib/orion-centinela/avisos
sudo touch /var/log/orion-centinela.jsonl
sudo chown root:"$GRUPO" /var/log/orion-centinela.jsonl
sudo chmod 640 /var/log/orion-centinela.jsonl

paso "Ajustes en $CONF"
# Tu IP de ahora (desde la que corres esto por SSH) queda permitida para siempre: así nunca te deja fuera.
mi_ip=${SSH_CLIENT%% *}
# Y la IP pública del propio servidor: las pruebas de Orión Equipo contra él mismo no son un ataque.
publica=$(curl -fsS4 --max-time 8 https://api.ipify.org 2>/dev/null || true)
permitidas=$(echo "${mi_ip:-},${publica:-}" | sed 's/^,//; s/,$//')
if [ ! -f "$CONF" ]; then
  sudo tee "$CONF" >/dev/null <<EOF
# Centinela de Orión. Cambia y espera un minuto (lo lee en cada ronda); para reglas nuevas: sudo orion-centinela encender
# actuar = bloquea solo y avisa; avisar = solo avisa
CENTINELA_MODO=$MODO
# IPs o redes que nunca se bloquean (tu casa, tu oficina), separadas por comas
CENTINELA_PERMITIDOS=$permitidas
# Grupo que lee los avisos (el del puente de WhatsApp)
CENTINELA_GRUPO=$GRUPO
# Umbrales (los valores por defecto están en centinela/centinela.py, AJUSTES):
# CENTINELA_SSH_FALLOS=8
# CENTINELA_BLOQUEO_MIN=60
# CENTINELA_CONEXIONES_IP=150
# CENTINELA_SALIDA_MB=300
# Cloudflare (opcional): bloquear en Cloudflare a quien ataca las webs a través de él y activar Under Attack.
# Token en Cloudflare > Mi perfil > API Tokens, solo para tu zona, con permisos Zone > Firewall Services: Edit,
# Zone Settings: Edit y Analytics: Read. El ID de zona sale en la portada del dominio (columna derecha).
# CENTINELA_CF_TOKEN=
# CENTINELA_CF_ZONA=
EOF
  echo "Creado. Permitidas para siempre: ${permitidas:-ninguna}"
else
  sudo sed -i "s/^CENTINELA_MODO=.*/CENTINELA_MODO=$MODO/" "$CONF"
  if [ -n "${mi_ip:-}" ] && ! grep -q "$mi_ip" "$CONF"; then
    echo "Tu IP de ahora ($mi_ip) no está en CENTINELA_PERMITIDOS. Igual no te bloquea: al entrar por SSH queda"
    echo "de confianza 3 días. Si es fija, añádela en $CONF."
  fi
fi

# Puede llevar el token de Cloudflare: solo root lo lee.
sudo chmod 600 "$CONF"

paso "Caddy: anotar las visitas para vigilar las webs"
./centinela/caddy-registro.sh || echo "No pude activar el registro de Caddy; el resto sigue igual."

paso "Kernel: aguantar inundaciones SYN y no aceptar redirecciones"
sudo tee /etc/sysctl.d/60-orion-centinela.conf >/dev/null <<'EOF'
# Centinela de Orión (centinela/instalar.sh)
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 4096
net.ipv4.tcp_synack_retries = 3
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
EOF
sudo sysctl -q --system >/dev/null || true

paso "Orión puede ver el estado y bloquear o soltar IPs (nada más)"
regla=/etc/sudoers.d/orion-centinela
c=/usr/local/sbin/orion-centinela
echo "$YO ALL=(root) NOPASSWD: $c estado, $c lista, $c bloquear *, $c desbloquear *" | sudo tee "$regla" >/dev/null
sudo chmod 440 "$regla"
sudo visudo -cf "$regla" >/dev/null || { sudo rm -f "$regla"; echo "Aviso: no pude crear $regla"; }

paso "Ronda cada minuto (systemd)"
sudo tee /etc/systemd/system/orion-centinela.service >/dev/null <<EOF
[Unit]
Description=Centinela de Orión: una ronda de vigilancia
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $DESTINO/centinela.py ronda
Nice=10
TimeoutStartSec=50
EOF
sudo tee /etc/systemd/system/orion-centinela.timer >/dev/null <<'EOF'
[Unit]
Description=Centinela de Orión cada minuto

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
# Las webs, casi al instante: lee el registro de Caddy cada 2 s y corta a la primera petición mala.
sudo tee /etc/systemd/system/orion-centinela-web.service >/dev/null <<EOF
[Unit]
Description=Centinela de Orión: vigila las webs cada 2 segundos
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 $DESTINO/centinela.py web-vivo
Restart=always
RestartSec=5
Nice=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
if [ "$MODO" = actuar ]; then sudo orion-centinela encender; fi
sudo systemctl enable --now orion-centinela.timer
sudo systemctl start orion-centinela.service || true
sudo systemctl enable orion-centinela-web.service >/dev/null 2>&1
sudo systemctl restart orion-centinela-web.service
# Lo que acaba de instalar (sudoers, servicio) no es una intrusión: queda como lo normal.
sudo orion-centinela aceptar >/dev/null

paso "Puente de WhatsApp: para que mande los avisos"
sudo systemctl restart jarvis-whatsapp 2>/dev/null && echo "Reiniciado." || echo "jarvis-whatsapp no está instalado aquí; los avisos quedan en el registro."

echo
echo "Listo. En un minuto te llega por WhatsApp: \"Centinela encendido\"."
echo "  Ver qué pasa:        sudo orion-centinela estado"
echo "  Soltar una IP:       sudo orion-centinela desbloquear 1.2.3.4"
echo "  Quitar todo bloqueo: sudo orion-centinela apagar     (vuelve con: sudo orion-centinela encender)"
echo "  Desinstalar:         sudo systemctl disable --now orion-centinela.timer orion-centinela-web && sudo orion-centinela apagar"
