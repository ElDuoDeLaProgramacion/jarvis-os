#!/usr/bin/env bash
# Pruebas de seguridad de JARVIS (habilidad "seguridad"): solo revisiones que no rompen ni cambian nada,
# y solo sobre los sistemas de David: este equipo y los que él puso a mano en JARVIS_OBJETIVOS_SEGURIDAD (.env).
#
#   scripts/seguridad.sh local                    auditoría de este equipo (SSH, puertos, cortafuegos, updates...)
#   scripts/seguridad.sh puertos <host>           puertos abiertos y versiones (nmap, sin scripts intrusivos)
#   scripts/seguridad.sh web <https://host[/..]>  cabeceras de seguridad, certificado y versiones de TLS
#   scripts/seguridad.sh dependencias <carpeta>   vulnerabilidades conocidas en las dependencias de un proyecto
#
# Nada de fuerza bruta, exploits ni pruebas de carga: eso lo corre David a mano si quiere.
set -uo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi

titulo() { printf '\n## %s\n' "$*"; }
falta() { echo "(no está instalado $1: sudo apt install -y $2)"; }

permitido() {
  local h="${1,,}"
  for o in localhost 127.0.0.1 ::1 "$(hostname)" "$(hostname -f 2>/dev/null)" \
           $(echo "${JARVIS_OBJETIVOS_SEGURIDAD:-}" | tr ',;' '  '); do
    [ -n "$o" ] && [ "$h" = "${o,,}" ] && return 0
  done
  echo "Objetivo no permitido: $1"
  echo "Solo se prueban los sistemas de David. Para añadir uno, David lo pone a mano en .env:"
  echo "  JARVIS_OBJETIVOS_SEGURIDAD=servidor.tu-red.ts.net,79.143.88.182"
  exit 2
}

local_() {
  titulo "Equipo"
  echo "$(hostname) · $(uname -sr) · encendido $(uptime -p 2>/dev/null)"

  titulo "Actualizaciones pendientes"
  if command -v apt >/dev/null; then
    pend=$(apt list --upgradable 2>/dev/null | grep -c upgradable || true)
    seg=$(apt list --upgradable 2>/dev/null | grep -ci security || true)
    echo "$pend paquetes por actualizar ($seg de seguridad)"
    [ -f /var/run/reboot-required ] && echo "AVISO: hay que reiniciar para aplicar actualizaciones"
    dpkg -s unattended-upgrades >/dev/null 2>&1 && echo "Actualizaciones automáticas: instaladas" \
      || echo "Actualizaciones automáticas: NO instaladas"
  fi

  titulo "Puertos escuchando"
  ss -tulnH 2>/dev/null | awk '{print $1, $5}' | sort -u

  titulo "SSH"
  grep -hEi '^\s*(Port|PermitRootLogin|PasswordAuthentication|KbdInteractiveAuthentication|PubkeyAuthentication|PermitEmptyPasswords|X11Forwarding|MaxAuthTries|AllowUsers)\b' \
    /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || echo "(sin ajustes explícitos: valen los de fábrica)"
  if sudo -n true 2>/dev/null; then
    echo "-- efectivo:"; sudo -n sshd -T 2>/dev/null | grep -Ei '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries) '
  fi

  titulo "Intentos de entrada fallidos por SSH (24 h)"
  fallos=$(journalctl -u ssh -u sshd --since "-24h" --no-pager 2>/dev/null | grep -Ei "failed password|invalid user" || true)
  if [ -n "$fallos" ]; then
    echo "$(echo "$fallos" | wc -l) intentos. IPs con más intentos:"
    echo "$fallos" | grep -oE 'from [0-9a-f.:]+' | sort | uniq -c | sort -rn | head -5
  else
    echo "Ninguno visible (o sin permiso para leer el registro)"
  fi

  titulo "Cortafuegos y fail2ban"
  if sudo -n true 2>/dev/null; then
    sudo -n ufw status verbose 2>/dev/null || echo "ufw no está instalado"
    sudo -n fail2ban-client status 2>/dev/null || echo "fail2ban no está instalado o no corre"
  else
    systemctl is-active ufw >/dev/null 2>&1 && echo "ufw: servicio activo (detalle necesita sudo)" || echo "ufw: servicio inactivo o no instalado"
    systemctl is-active fail2ban >/dev/null 2>&1 && echo "fail2ban: activo" || echo "fail2ban: inactivo o no instalado"
  fi

  titulo "Usuarios"
  echo "Con UID 0: $(awk -F: '$3==0 {print $1}' /etc/passwd | xargs)"
  echo "Con shell: $(awk -F: '$7 ~ /(bash|sh|zsh|fish)$/ {print $1}' /etc/passwd | xargs)"
  echo "En sudo: $(getent group sudo | cut -d: -f4)"
  awk -F: '$2=="" {print "AVISO: " $1 " no tiene contraseña"}' /etc/shadow 2>/dev/null || true

  titulo "Permisos de archivos sensibles"
  for f in .env "$HOME/.ssh" "$HOME/.ssh/authorized_keys" voz/.spotify-token.json whatsapp/sesion; do
    [ -e "$f" ] && stat -c '%A %U %n' "$f"
  done

  titulo "Servicios de JARVIS"
  for s in jarvis-app jarvis-whatsapp tailscaled syncthing@"${USER:-$(id -un)}"; do
    printf '%s: %s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null)"
  done

  titulo "Lynis (auditoría completa)"
  if command -v lynis >/dev/null; then
    lynis audit system --quick --no-colors 2>/dev/null \
      | grep -E "Hardening index|Warnings|Suggestions|^\s+! |^\s+\* " | head -60
  else
    falta lynis lynis
  fi
}

puertos() {
  permitido "$1"
  command -v nmap >/dev/null || { falta nmap nmap; exit 1; }
  titulo "Puertos y servicios de $1"
  nmap -Pn -sV -T3 --top-ports 1000 --open "$1"
}

web() {
  local url="$1" host
  host=$(echo "$url" | sed -E 's#^[a-z]+://##; s#[/:].*##')
  permitido "$host"
  titulo "Cabeceras de seguridad de $url"
  cab=$(curl -sS -I -L --max-time 15 "$url" 2>&1)
  echo "$cab" | grep -iE '^(HTTP/|server:|x-powered-by:)'
  for h in Strict-Transport-Security Content-Security-Policy X-Frame-Options X-Content-Type-Options Referrer-Policy Permissions-Policy; do
    echo "$cab" | grep -qi "^$h:" && echo "OK     $h" || echo "FALTA  $h"
  done
  titulo "Certificado TLS"
  echo | openssl s_client -connect "$host:443" -servername "$host" 2>/dev/null \
    | openssl x509 -noout -subject -issuer -dates 2>/dev/null || echo "Sin TLS en el puerto 443"
  titulo "Versiones de TLS aceptadas"
  for v in tls1 tls1_1 tls1_2 tls1_3; do
    if echo | openssl s_client -connect "$host:443" -servername "$host" "-$v" >/dev/null 2>&1; then
      echo "$v: aceptada"
    else
      echo "$v: rechazada"
    fi
  done
}

dependencias() {
  local d
  d=$(realpath "$1" 2>/dev/null) || { echo "No existe: $1"; exit 1; }
  case "$d" in "$PWD"*|/mnt/p/*|"$HOME"/*) ;; *) echo "Fuera de las carpetas de David: $d"; exit 2 ;; esac
  titulo "Dependencias de $d"
  if [ -f "$d/package-lock.json" ]; then
    (cd "$d" && npm audit --omit=dev 2>&1 | tail -25)
  fi
  for r in "$d"/requirements*.txt; do
    [ -f "$r" ] || continue
    if command -v pip-audit >/dev/null; then pip-audit -r "$r" 2>&1 | tail -25; else falta pip-audit "pipx && pipx install pip-audit"; fi
  done
  [ -f "$d/package-lock.json" ] || ls "$d"/requirements*.txt >/dev/null 2>&1 || echo "No encontré package-lock.json ni requirements*.txt"
}

case "${1:-}" in
  local) local_ ;;
  puertos) [ -n "${2:-}" ] || { echo "Falta el host"; exit 1; }; puertos "$2" ;;
  web) [ -n "${2:-}" ] || { echo "Falta la dirección"; exit 1; }; web "$2" ;;
  dependencias) [ -n "${2:-}" ] || { echo "Falta la carpeta"; exit 1; }; dependencias "$2" ;;
  *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
