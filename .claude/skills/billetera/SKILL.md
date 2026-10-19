---
name: billetera
description: La billetera simulada de Orión, donde todas las IAs deciden solas qué hacer con una cartera de cripto durante 14 días. Úsala para "cómo va la billetera", "empieza el experimento", "pausa/reanuda la billetera", "qué decidieron las IAs", "termina la billetera".
---
# Billetera de Orión (simulada)

Script: `python3 scripts/billetera.py`. Corre en el servidor; el cron hace una ronda cada 4 horas (`servidor/rutinas.sh`). En cada ronda todas las IAs disponibles reciben los precios reales (CoinGecko) y la cartera, votan una acción en JSON con su razón, y gana la mayoría (empate = mantener). Dinero de mentira: no hay ninguna billetera ni exchange real conectado.

| Pedido | Comando |
|---|---|
| "empieza el experimento", "arranca la billetera" | `python3 scripts/billetera.py iniciar` (por defecto 1000 USD simulados y 14 días; David puede pedir otro saldo con `--saldo` o días con `--dias`) |
| "cómo va la billetera", "cuánto lleva" | `python3 scripts/billetera.py estado` |
| "pausa la billetera", "para la billetera" | `python3 scripts/billetera.py pausar` |
| "reanuda la billetera" | `python3 scripts/billetera.py reanudar` |
| "termina el experimento" | `python3 scripts/billetera.py terminar` (deja `informe-final.md`) |
| "qué decidieron", "por qué compró X" | lee `boveda/outputs/billetera/diario/AAAA-MM-DD.md`; el detalle de cada voto está en `decisiones.jsonl` |

Reglas que ninguna IA puede saltarse (en el código, no en el prompt): máximo 25 % por operación, 3 operaciones al día, comisión simulada de 0,5 %, solo BTC, ETH y SOL, sin préstamos ni apalancamiento.

## Dinero real: nunca desde aquí
El modo real no existe. Si David pide usar una billetera de verdad, dile que primero hay que construirlo (elegir red y una billetera nueva solo para Orión, con un tope que él fija) y anótalo en `boveda/wiki/ideas-jarvis.md`. Nunca pidas, guardes ni escribas frases semilla, claves privadas o contraseñas de billeteras.

## Respuesta hablada
Valor actual, cuánto ganó o perdió en porcentaje, la comparación con solo guardar BTC y la última decisión, en dos o tres frases. No es asesoría financiera: si David pregunta si invertir dinero real, dilo.
