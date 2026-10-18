#!/usr/bin/env bash
# Publica la API de Orión en internet con HTTPS, sin Tailscale ni otra app de por medio.
#   ./servidor/publicar.sh                 -> https://<ip-con-guiones>.sslip.io (gratis, sin comprar dominio)
#   ./servidor/publicar.sh orion.midominio.com   -> con tu propio dominio (su registro A apunta a este servidor)
#
# Caddy recibe en los puertos 80 y 443, saca y renueva solo el certificado (Let's Encrypt) y pasa todo
# a la API, que sigue escuchando solo en 127.0.0.1:7788. Sin la clave (JARVIS_API_TOKEN) no se entra,
# y tras 5 claves malas esa IP espera 15 minutos.
set -euo pipefail
cd "$(dirname "$0")/.."
paso() { echo; echo "== $* =="; }

ip=$(curl -fsS4 --max-time 10 https://api.ipify.org || true)
dominio=${1:-}
if [ -z "$dominio" ]; then
  [ -n "$ip" ] || { echo "No pude saber la IP pública de este servidor. Pasa un dominio: $0 orion.tudominio.com"; exit 1; }
  dominio="${ip//./-}.sslip.io"
fi

paso "Caddy (HTTPS automático)"
if ! command -v caddy >/dev/null; then
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y caddy
fi

# "tailscale serve" (como se instalaba antes) ocupa el 443 y Caddy no arranca: se suelta primero.
if command -v tailscale >/dev/null; then sudo tailscale serve reset >/dev/null 2>&1 || true; fi

# Las páginas que Orión publica ("publícalo"): las escribe la API (servidor/sitios.py) y Caddy las sirve
# en sitios.<dominio>, otro origen, así una página no puede leer la clave que guarda la app.
sitios_dir=${JARVIS_SITIOS:-/srv/orion-sitios}
sudo install -d -o "$(id -un)" -g "$(id -gn)" -m 755 "$sitios_dir"
touch .env
if ! grep -q '^JARVIS_SITIOS_URL=' .env; then echo "JARVIS_SITIOS_URL=https://sitios.$dominio" >> .env; fi

sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
# Lo escribe servidor/publicar.sh. La API de Orión, publicada con HTTPS.
$dominio {
	encode gzip
	request_body {
		max_size 45MB
	}
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		-Server
	}
	reverse_proxy 127.0.0.1:7788
}

sitios.$dominio {
	encode gzip
	root * $sitios_dir
	file_server
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		Referrer-Policy strict-origin-when-cross-origin
		-Server
	}
}
EOF
sudo systemctl restart jarvis-app 2>/dev/null || true   # para que la API lea JARVIS_SITIOS_URL
sudo systemctl enable caddy >/dev/null 2>&1 || true
sudo systemctl reload caddy 2>/dev/null || sudo systemctl restart caddy || true
if ! systemctl is-active --quiet caddy; then
  echo "Caddy no arrancó. Lo que dice:"
  sudo journalctl -u caddy -n 5 --no-pager | grep -E 'error|bind' || true
  echo "Si dice 'address already in use', otro programa usa el 80 o el 443:  sudo ss -ltnp | grep -E ':(80|443) '"
fi

paso "Cortafuegos"
if command -v ufw >/dev/null && sudo ufw status | grep -q "Status: active"; then
  sudo ufw allow 80/tcp >/dev/null
  sudo ufw allow 443/tcp >/dev/null
  echo "ufw: abiertos 80 y 443."
else
  echo "ufw no está activo en este servidor; nada que abrir aquí."
fi
echo "Si tu proveedor tiene cortafuegos en su panel (Clouding, Oracle...), abre ahí también TCP 80 y 443."

paso "Probando"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 "https://$dominio/app/" >/dev/null 2>&1; then ok=1; break; fi
  sleep 3
done
echo
if [ $ok = 1 ]; then
  echo "Listo: https://$dominio"
else
  echo "Caddy aún no responde con HTTPS en https://$dominio."
  echo "Casi siempre es el cortafuegos del panel del proveedor (puertos 80 y 443). Ábrelos y vuelve a correr esto."
  echo "Detalle: sudo journalctl -u caddy -n 30"
fi
echo "  App del celular: https://$dominio/app/"
echo "  Páginas que publique Orión: https://sitios.$dominio/<nombre>/"
echo "  En el PC, en .env:  JARVIS_SERVIDOR=https://$dominio"
echo "  En la app de Android, campo Servidor:  https://$dominio"
if command -v tailscale >/dev/null; then
  echo "  Tailscale ya no hace falta. Para quitarlo:  sudo tailscale serve reset && sudo tailscale down"
fi
