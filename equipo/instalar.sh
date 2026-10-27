#!/usr/bin/env bash
# Monta Orión Equipo en este servidor, aislado del Orión de David (equipo/README.md).
# Lo corre David, con su usuario, desde su copia del repo. Se puede repetir: así también se actualiza.
#   ./equipo/instalar.sh                      -> sala en https://equipo.<ip-con-guiones>.sslip.io
#   ./equipo/instalar.sh equipo.midominio.com -> con un dominio propio (registro A a este servidor)
#
# Qué deja:
#   usuario "equipo" (sin sudo, sin SSH), con su ~/.env, ~/personas y ~/espacio (bóveda y habilidades propias)
#   /opt/orion-equipo   solo el código que necesita (equipo/ y scripts/seguridad.sh), de root, solo lectura
#   orion-equipo.service  encerrado: no ve /home de nadie más ni la red local (127.0.0.1, 10.x, Tailscale...)
#   Caddy: la sala por HTTPS en su propio subdominio
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
CODIGO=/opt/orion-equipo
CASA=/home/equipo
paso() { echo; echo "== $* =="; }

paso "Usuario equipo"
if ! id equipo >/dev/null 2>&1; then
  sudo useradd --create-home --home-dir "$CASA" --shell /usr/sbin/nologin equipo
fi
sudo gpasswd -d equipo sudo >/dev/null 2>&1 || true
sudo chmod 750 "$CASA"
# Tu carpeta: que ningún otro usuario la lea (en Ubuntu 24.04 ya viene así; lo aseguramos).
sudo chmod 750 "$HOME"
[ -f .env ] && chmod 600 .env

paso "Código (solo lo necesario, sin tu bóveda ni tus habilidades)"
sudo rm -rf "$CODIGO.nuevo"
sudo install -d -o root -g root -m 755 "$CODIGO.nuevo" "$CODIGO.nuevo/scripts"
sudo cp -r equipo "$CODIGO.nuevo/"
sudo install -o root -g root -m 755 scripts/seguridad.sh "$CODIGO.nuevo/scripts/seguridad.sh"
sudo chown -R root:root "$CODIGO.nuevo"
sudo chmod -R a+rX,go-w "$CODIGO.nuevo"
sudo rm -rf "$CODIGO"; sudo mv "$CODIGO.nuevo" "$CODIGO"

paso "Espacio del equipo (bóveda propia, vacía)"
como() { sudo -u equipo -H "$@"; }
if ! sudo test -d "$CASA/espacio"; then
  sudo cp -r equipo/plantilla "$CASA/espacio"
else
  # Reglas y habilidades se actualizan; la bóveda y los proyectos no se tocan.
  sudo rm -rf "$CASA/espacio/.claude"
  sudo cp -r equipo/plantilla/.claude equipo/plantilla/CLAUDE.md "$CASA/espacio/"
fi
sudo install -d "$CASA/espacio/proyectos" "$CASA/sala"
sudo chown -R equipo:equipo "$CASA"

paso "Dirección de la sala"
dominio=${1:-}
if [ -z "$dominio" ]; then
  ip=$(curl -fsS4 --max-time 10 https://api.ipify.org || true)
  [ -n "$ip" ] || { echo "No pude saber la IP pública. Pasa un dominio: $0 equipo.tudominio.com"; exit 1; }
  dominio="equipo.${ip//./-}.sslip.io"
fi
echo "https://$dominio"

paso "Claves del equipo (~equipo/.env)"
if ! sudo test -f "$CASA/.env"; then
  como tee "$CASA/.env" >/dev/null <<EOF
# Orión Equipo. Nada de esto es de David: claves propias del equipo.
# Cómo autenticar el motor (elige UNA; ver equipo/MOTOR.md para las alternativas sin API key de Anthropic):
#  - API key de Anthropic SOLO del equipo, con tope de gasto (console.anthropic.com):
ANTHROPIC_API_KEY=
#  - o suscripción de una cuenta de Claude del equipo:   CLAUDE_CODE_OAUTH_TOKEN=   ('claude setup-token')
#  - o Bedrock/Vertex:   CLAUDE_CODE_USE_BEDROCK=1   /   CLAUDE_CODE_USE_VERTEX=1
#  - o pasarela (p. ej. OpenRouter):   ANTHROPIC_BASE_URL=   y   ANTHROPIC_AUTH_TOKEN=
# Lo único que el equipo puede probar (dominios/IP de David, separados por coma). Lo editas tú a mano.
JARVIS_OBJETIVOS_SEGURIDAD=
# Pedidos por persona y por día (0 = sin tope).
ORION_EQUIPO_LIMITE_DIA=40
ORION_EQUIPO_URL=https://$dominio
EOF
fi
# Frase secreta del servidor (firma los tokens de sesión y las contraseñas): se crea una vez.
if ! sudo grep -q '^ORION_EQUIPO_SECRETO=.\+' "$CASA/.env"; then
  sudo sed -i '/^ORION_EQUIPO_SECRETO=/d' "$CASA/.env"
  echo "ORION_EQUIPO_SECRETO=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" | sudo tee -a "$CASA/.env" >/dev/null
fi
sudo sed -i "s|^ORION_EQUIPO_URL=.*|ORION_EQUIPO_URL=https://$dominio|" "$CASA/.env"
sudo chown equipo:equipo "$CASA/.env"; sudo chmod 600 "$CASA/.env"
sudo -u equipo touch "$CASA/personas"; sudo chmod 600 "$CASA/personas"
# Carpetas de autorizaciones (lo que el equipo pide y David aprueba) e informes de cada sesión.
sudo -u equipo mkdir -p "$CASA/autorizaciones/pendientes" "$CASA/autorizaciones/aprobadas" "$CASA/informes"

paso "Claude Code para el usuario equipo"
if ! sudo test -x "$CASA/.local/bin/claude"; then
  como bash -c 'cd ~ && curl -fsSL https://claude.ai/install.sh | bash'
fi
# Herramientas de pentest (pentest.sh usa lo que haya; lo que falte lo dice al correr).
sudo apt-get install -y -qq nmap whois dnsutils whatweb nikto >/dev/null 2>&1 || true
# ffuf y sqlmap no siempre están en apt; si falta, pentest.sh dice cómo instalarlos.
sudo apt-get install -y -qq ffuf sqlmap >/dev/null 2>&1 || true

paso "Servicio orion-equipo (encerrado)"
sudo tee /etc/systemd/system/orion-equipo.service >/dev/null <<UNIDAD
[Unit]
Description=Orión Equipo: sala web aislada para el equipo de ciberseguridad
After=network-online.target
Wants=network-online.target

[Service]
User=equipo
Group=equipo
WorkingDirectory=$CASA
Environment=HOME=$CASA
Environment=PATH=$CASA/.local/bin:/usr/local/bin:/usr/bin:/bin
# Carga ANTHROPIC_API_KEY, JARVIS_OBJETIVOS_SEGURIDAD, ORION_EQUIPO_SECRETO y demás del .env del equipo.
EnvironmentFile=-$CASA/.env
ExecStart=/usr/bin/python3 $CODIGO/equipo/servidor.py
Restart=always
RestartSec=10
RuntimeDirectory=orion-equipo
RuntimeDirectoryMode=0755
# Encierro: el resto de /home desaparece (solo existe /home/equipo), el sistema es de solo lectura,
# sin sudo ni privilegios, y no ve los procesos de otros usuarios.
ProtectHome=tmpfs
BindPaths=$CASA
ReadWritePaths=$CASA
ProtectSystem=strict
PrivateTmp=yes
PrivateDevices=yes
NoNewPrivileges=yes
CapabilityBoundingSet=
RestrictSUIDSGID=yes
ProtectProc=invisible
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
LockPersonality=yes
InaccessiblePaths=-/srv -/var/lib/caddy -/etc/sudoers.d -/var/log
# Red: internet sí; la red local no (la API de David en 127.0.0.1:7788, Syncthing, Tailscale,
# la nube 169.254.169.254). Solo el DNS local para resolver nombres. Caddy le llega por el socket.
IPAddressDeny=localhost link-local multicast 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fc00::/7
IPAddressAllow=127.0.0.53/32

[Install]
WantedBy=multi-user.target
UNIDAD
sudo systemctl daemon-reload
sudo systemctl enable orion-equipo >/dev/null 2>&1
sudo systemctl restart orion-equipo

paso "Caddy: la sala por HTTPS"
command -v caddy >/dev/null || { echo "Falta Caddy: corre primero ./servidor/publicar.sh"; exit 1; }
sudo install -d -m 755 /etc/caddy/conf.d
sudo tee /etc/caddy/conf.d/orion-equipo.caddy >/dev/null <<EOF
# Lo escribe equipo/instalar.sh. La sala de Orión Equipo.
$dominio {
	encode gzip
	request_body {
		max_size 64KB
	}
	header {
		Strict-Transport-Security "max-age=31536000"
		-Server
	}
	reverse_proxy unix//run/orion-equipo/sala.sock
}
EOF
grep -q 'import /etc/caddy/conf.d/\*.caddy' /etc/caddy/Caddyfile \
  || echo 'import /etc/caddy/conf.d/*.caddy' | sudo tee -a /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy

echo
echo "Listo."
echo "  Sala del equipo: https://$dominio"
echo "  Tu panel:        https://$dominio/panel"
if ! sudo grep -qE '^(ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_USE_BEDROCK|CLAUDE_CODE_USE_VERTEX)=.+' "$CASA/.env" \
   && ! sudo test -f "$CASA/.claude/.credentials.json"; then
  echo "  Falta: configura el motor en $CASA/.env (API key, token de suscripción o pasarela). Ver equipo/MOTOR.md, luego sudo systemctl restart orion-equipo"
fi
sudo grep -q '^JARVIS_OBJETIVOS_SEGURIDAD=.\+' "$CASA/.env" || echo "  Falta: los objetivos autorizados en JARVIS_OBJETIVOS_SEGURIDAD del mismo archivo"
sudo test -f "$CASA/admin.json" || echo "  Falta: configura tu panel con  ./equipo/admin.sh  (clave + código de 6 dígitos)"
echo "  Dar entrada a alguien:  ./equipo/persona.sh agregar ana"
echo "  Código de un proyecto para auditar:  sudo cp -r <carpeta> $CASA/espacio/proyectos/ && sudo chown -R equipo: $CASA/espacio/proyectos"
echo "  Poner usuario y contraseña delante (Cloudflare Access): ver equipo/CLOUDFLARE.md"
