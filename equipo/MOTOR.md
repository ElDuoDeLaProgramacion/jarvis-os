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

## 3. Otro proveedor por pasarela — p. ej. tu OpenRouter
Apuntas Claude Code a un proxy compatible con la API de Anthropic (LiteLLM, claude-code-router...) que
traduce a OpenRouter/OpenAI/Gemini con **tu** clave (no la de Anthropic). En `/home/equipo/.env`:
```
ANTHROPIC_BASE_URL=http://127.0.0.1:4000   # tu pasarela
ANTHROPIC_AUTH_TOKEN=tu-clave-de-la-pasarela
```
- **A favor:** usas una clave que ya tienes (OpenRouter) y eliges el modelo.
- **En contra:** más montaje (hay que correr la pasarela), y el uso de herramientas/agente rinde mejor
  con modelos Claude; los modelos locales no caben en un servidor de 2 GB. Si quieres esta vía, dime y
  te dejo la pasarela lista.

## 4. API key de Anthropic con tope — lo más simple si el tema es el costo
Si lo que te preocupa es gastar de más, no hace falta evitar la API key: en console.anthropic.com le
pones un **límite de gasto** al workspace (p. ej. 5–10 USD/mes) y listo. `ANTHROPIC_API_KEY=` en el .env.

---
El servicio toma la primera que encuentre. Para cambiar de una a otra, edita `/home/equipo/.env`, borra
la línea que ya no uses y `sudo systemctl restart orion-equipo`.
