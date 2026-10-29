#!/usr/bin/env bash
# Hace que Caddy anote cada visita (JSON) en /var/log/caddy/acceso.log para que el centinela vea los
# ataques a las webs. Añade a cada sitio de /etc/caddy/Caddyfile y /etc/caddy/conf.d/*.caddy la línea
#   import /etc/caddy/orion-registro*.caddy
# (con comodín: si un día borras ese archivo, Caddy sigue arrancando). Copia de respaldo y marcha atrás
# si Caddy no acepta el cambio. Se puede repetir. Lo llama centinela/instalar.sh.
# Caddy no guarda Cookie ni Authorization en el registro (las tapa como REDACTED).
set -euo pipefail
command -v caddy >/dev/null || { echo "Caddy no está instalado: nada que hacer."; exit 0; }
# Caddy corre como su propio usuario: la carpeta y el archivo del registro tienen que ser suyos o no arranca.
yo_caddy=$(systemctl show -p User --value caddy 2>/dev/null || true)
yo_caddy=${yo_caddy:-caddy}
id "$yo_caddy" >/dev/null 2>&1 || yo_caddy=root
dueno() {
  sudo install -d -o "$yo_caddy" -g "$yo_caddy" -m 755 /var/log/caddy
  [ -f /var/log/caddy/acceso.log ] || sudo install -o "$yo_caddy" -g "$yo_caddy" -m 640 /dev/null /var/log/caddy/acceso.log
  sudo chown "$yo_caddy:$yo_caddy" /var/log/caddy/acceso.log*
}
dueno
sudo tee /etc/caddy/orion-registro.caddy >/dev/null <<'REG'
# Lo escribe centinela/caddy-registro.sh: registro de visitas que lee el centinela de Orión.
log {
	output file /var/log/caddy/acceso.log {
		roll_size 20MiB
		roll_keep 5
	}
	format json
}
REG
marca=$(date +%Y%m%d%H%M%S)
cambiados=()
for f in /etc/caddy/Caddyfile /etc/caddy/conf.d/*.caddy; do
  [ -f "$f" ] || continue
  # Sitio = línea sin sangría que abre llave y no es el bloque global "{" ni un snippet "(nombre)".
  nuevo=$(awk '
    prev_sitio && $0 !~ /import \/etc\/caddy\/orion-registro/ { print "\timport /etc/caddy/orion-registro*.caddy" }
    { print; prev_sitio = ($0 ~ /^[^[:space:]#({][^{]*\{[[:space:]]*$/) }
  ' "$f")
  if [ "$nuevo" != "$(cat "$f")" ]; then
    sudo cp -p "$f" "$f.antes-del-centinela-$marca"
    printf '%s\n' "$nuevo" | sudo tee "$f" >/dev/null
    cambiados+=("$f")
  fi
done
if [ ${#cambiados[@]} -eq 0 ]; then echo "Caddy ya anotaba las visitas."; exit 0; fi
# validate corre como root y puede dejar el archivo a nombre de root: se devuelve a Caddy antes de recargar.
if sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 && dueno && sudo systemctl reload caddy; then
  echo "Caddy anota las visitas en /var/log/caddy/acceso.log (sitios en: ${cambiados[*]})."
else
  for f in "${cambiados[@]}"; do sudo cp -p "$f.antes-del-centinela-$marca" "$f"; done
  sudo journalctl -u caddy -n 8 --no-pager -o cat 2>/dev/null | grep -iE 'error|denied|fail' | tail -3 || true
  sudo systemctl reload caddy || true
  echo "Caddy no aceptó el cambio; dejé todo como estaba. El centinela sigue vigilando el servidor, pero no las webs."
fi
