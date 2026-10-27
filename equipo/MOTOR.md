# El motor de Orión Equipo (sin API key de Anthropic, si prefieres)

Orión Equipo corre sobre Claude Code. Claude Code puede autenticarse de varias formas; pones la que
elijas en `/home/equipo/.env` y reinicias con `sudo systemctl restart orion-equipo`. Todas mantienen el
aislamiento: sea cual sea, los conectores de claude.ai quedan apagados y no se usa tu cuenta personal.

## 1. Suscripción de Claude — recomendada si no quieres pago por uso
Una cuenta de Claude **aparte para el equipo** (Pro ~20 USD/mes, costo fijo), no la tuya.
```bash
sudo -u equipo -H bash -lc 'claude setup-token'   # inicia sesión con la cuenta del equipo; da un token
```
Pega el token en `/home/equipo/.env`:
```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat...
```
- **A favor:** costo fijo y previsible; nada de facturación por uso.
- **En contra:** las suscripciones de Claude son para uso individual; una cuenta dedicada al equipo y
  compartida entre pocos es zona gris de los términos, y la suscripción tiene su propio tope de uso que
  se reparte entre todos. **No uses tu cuenta personal** (le daría al equipo tus conectores).

## 2. Claude por AWS Bedrock o Google Vertex — sin API key de Anthropic
Modelos de Claude facturados por tu nube. En `/home/equipo/.env`:
```
CLAUDE_CODE_USE_BEDROCK=1      # (y las credenciales de AWS del equipo)
# o
CLAUDE_CODE_USE_VERTEX=1       # (y las credenciales de GCP del equipo)
```
- **A favor:** si ya tienes cuenta de AWS/GCP, entra en esa factura; buen control de permisos y gasto.
- **En contra:** hay que configurar las credenciales de la nube; es pago por uso igual, solo que por ahí.

## 3. OpenRouter (u otro proveedor) por pasarela — ya automatizado
Claude Code solo habla el formato de Anthropic; `equipo/pasarela.sh` monta un traductor (LiteLLM) que
lleva los pedidos a OpenRouter con **tu** clave (no la de Anthropic) y deja todo conectado:
```bash
OPENROUTER_API_KEY=sk-or-... ./equipo/pasarela.sh
# o eligiendo modelo (lista en https://openrouter.ai/models):
OPENROUTER_API_KEY=sk-or-... ./equipo/pasarela.sh openrouter/anthropic/claude-sonnet-4.5
```
Deja un servicio `orion-equipo-gw` escuchando solo en `127.0.0.2:8788` —una dirección que el servicio
encerrado de Orión Equipo sí puede alcanzar, mientras tu API privada en `127.0.0.1` sigue bloqueada— y
pone en el `.env` del equipo `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` y el modelo. Cambiar de modelo
= volver a correrlo con otro nombre.
- **A favor:** usas la clave de OpenRouter que ya tienes y eliges el modelo.
- **En contra:** el uso de herramientas/agente rinde mejor con modelos Claude, así que el modelo por
  defecto es Claude Sonnet vía OpenRouter (buen comportamiento, facturado por OpenRouter). Un modelo
  más barato puede fallar más en tareas con herramientas. Los modelos locales no caben en 2 GB.

## 4. API key de Anthropic con tope — lo más simple si el tema es el costo
Si lo que te preocupa es gastar de más, no hace falta evitar la API key: en console.anthropic.com le
pones un **límite de gasto** al workspace (p. ej. 5–10 USD/mes) y listo. `ANTHROPIC_API_KEY=` en el .env.

---
El servicio toma la primera que encuentre. Para cambiar de una a otra, edita `/home/equipo/.env`, borra
la línea que ya no uses y `sudo systemctl restart orion-equipo`.
