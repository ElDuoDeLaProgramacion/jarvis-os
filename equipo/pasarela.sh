#!/usr/bin/env bash
# Pasarela para usar OpenRouter (u otro proveedor) como motor de Orión Equipo, sin API key de Anthropic.
# Claude Code solo habla el formato de Anthropic; esta pasarela (LiteLLM) lo traduce a OpenRouter.
# Lo corre David en el servidor, después de ./equipo/instalar.sh:
#   OPENROUTER_API_KEY=sk-or-... ./equipo/pasarela.sh
#   OPENROUTER_API_KEY=sk-or-... ./equipo/pasarela.sh openrouter/anthropic/claude-sonnet-4.5   # elegir modelo
#
# Deja un servicio orion-equipo-gw escuchando SOLO en 127.0.0.2:8788 (una dirección que el servicio
# encerrado de Orión Equipo sí puede alcanzar; la API privada de David en 127.0.0.1 sigue bloqueada),
# y configura el .env del equipo para que el motor use esa pasarela.
set -euo pipefail
CASA=/home/equipo
MODELO="${1:-openrouter/anthropic/claude-sonnet-4.5}"   # ver modelos en https://openrouter.ai/models
paso() { echo; echo "== $* =="; }

[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "Falta OPENROUTER_API_KEY. Úsalo así: OPENROUTER_API_KEY=sk-or-... $0"; exit 1; }
id equipo >/dev/null 2>&1 || { echo "Primero corre ./equipo/instalar.sh"; exit 1; }
como() { sudo -u equipo -H "$@"; }

paso "LiteLLM (el traductor) en un entorno del usuario equipo"
if ! sudo test -x "$CASA/pasarela-venv/bin/litellm"; then
  como python3 -m venv "$CASA/pasarela-venv"
  como "$CASA/pasarela-venv/bin/pip" install -q --upgrade pip
  como "$CASA/pasarela-venv/bin/pip" install -q "litellm[proxy]"
fi

paso "Claves y configuración"
# Token compartido entre Orión Equipo y la pasarela (para que nadie más la use), se crea una vez.
if ! sudo grep -q '^ORION_GW_TOKEN=.\+' "$CASA/.env"; then
  echo "ORION_GW_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" | sudo tee -a "$CASA/.env" >/dev/null
fi
sudo sed -i '/^OPENROUTER_API_KEY=/d' "$CASA/.env"
echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" | sudo tee -a "$CASA/.env" >/dev/null
# El motor del equipo usa la pasarela (orion-equipo.sh ya acepta estas dos variables).
for par in "ANTHROPIC_BASE_URL=http://127.0.0.2:8788" "ANTHROPIC_AUTH_TOKEN=\${ORION_GW_TOKEN}" "ORION_EQUIPO_MODELO=orion"; do
  clave=${par%%=*}
  sudo sed -i "/^$clave=/d" "$CASA/.env"
done
{
  echo 'ANTHROPIC_BASE_URL=http://127.0.0.2:8788'
  echo 'ANTHROPIC_AUTH_TOKEN=${ORION_GW_TOKEN}'   # systemd EnvironmentFile no expande esto; se resuelve abajo
  echo 'ORION_EQUIPO_MODELO=orion'
} | sudo tee -a "$CASA/.env" >/dev/null
# EnvironmentFile no expande variables; fijamos ANTHROPIC_AUTH_TOKEN al valor real del token.
tok=$(sudo grep -oP '^ORION_GW_TOKEN=\K.*' "$CASA/.env")
sudo sed -i "s|^ANTHROPIC_AUTH_TOKEN=.*|ANTHROPIC_AUTH_TOKEN=$tok|" "$CASA/.env"
sudo chown equipo:equipo "$CASA/.env"; sudo chmod 600 "$CASA/.env"

# Config de LiteLLM: el nombre "orion" (el que pide Orión Equipo) -> el modelo de OpenRouter que elijas.
como tee "$CASA/pasarela.yaml" >/dev/null <<YAML
model_list:
  - model_name: orion
    litellm_params:
      model: $MODELO
      api_key: os.environ/OPENROUTER_API_KEY
litellm_settings:
  drop_params: true
general_settings:
  master_key: os.environ/ORION_GW_TOKEN
YAML
sudo chmod 600 "$CASA/pasarela.yaml"

paso "Servicio de la pasarela (solo en 127.0.0.2:8788)"
sudo tee /etc/systemd/system/orion-equipo-gw.service >/dev/null <<UNIDAD
[Unit]
Description=Orión Equipo: pasarela a OpenRouter (traduce Anthropic -> OpenRouter)
After=network-online.target
Wants=network-online.target
Before=orion-equipo.service

[Service]
User=equipo
Group=equipo
WorkingDirectory=$CASA
Environment=HOME=$CASA
EnvironmentFile=$CASA/.env
ExecStart=$CASA/pasarela-venv/bin/litellm --config $CASA/pasarela.yaml --host 127.0.0.2 --port 8788
Restart=always
RestartSec=10
# Encierro: no ve /home ajeno ni toca el sistema; solo necesita salir a internet (OpenRouter).
ProtectHome=tmpfs
BindPaths=$CASA
ReadWritePaths=$CASA
ProtectSystem=strict
PrivateTmp=yes
NoNewPrivileges=yes
ProtectProc=invisible
# No puede hablar con la red local (ni la API de David); internet sí, para llegar a OpenRouter.
IPAddressDeny=link-local multicast 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fc00::/7
IPAddressAllow=127.0.0.0/8

[Install]
WantedBy=multi-user.target
UNIDAD
sudo systemctl daemon-reload
sudo systemctl enable orion-equipo-gw >/dev/null 2>&1
sudo systemctl restart orion-equipo-gw
sudo systemctl restart orion-equipo

paso "Comprobando"
ok=0
for _ in $(seq 1 15); do
  if curl -fsS --max-time 3 http://127.0.0.2:8788/health/readiness >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
echo
if [ "$ok" = 1 ]; then
  echo "Listo. Orión Equipo usa OpenRouter con el modelo: $MODELO"
  echo "Para cambiar de modelo: OPENROUTER_API_KEY=... $0 openrouter/<otro-modelo>  (lista: https://openrouter.ai/models)"
else
  echo "La pasarela aún no responde. Mira: sudo journalctl -u orion-equipo-gw -n 30"
fi
