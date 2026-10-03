#!/usr/bin/env bash
# Ejecuta, en orden de llegada, todas las intenciones de cola/pendientes/.
# Cada intención pasa por scripts/jarvis.sh y termina en cola/hechas/ o cola/fallidas/
# con la respuesta (o el error) añadida al final del archivo.
# Solo corre un corredor a la vez (flock), así dos rutinas no se pisan.
set -uo pipefail

cd "$(dirname "$0")/.."
mkdir -p cola/pendientes cola/en-curso cola/hechas cola/fallidas logs

exec 9>cola/.corredor.lock
if ! flock -n 9; then
  echo "Ya hay un corredor trabajando; la intención se procesará en esa pasada."
  exit 0
fi

# Si un corredor anterior murió a medias (se cerró JARVIS, se apagó el PC), sus intenciones quedaron
# en en-curso/. Las recientes vuelven a pendientes; las de hace más de 3 h ya no tienen sentido
# (un "resumen matutino" a la noche), así que pasan a fallidas con una nota.
for f in cola/en-curso/*.md; do
  [ -e "$f" ] || continue
  creado=$(sed -n 's/^creado: //p' "$f" | head -n 1)
  edad=$(( $(date +%s) - $(date -d "$creado" +%s 2>/dev/null || stat -c %Y "$f") ))
  if [ "$edad" -gt 10800 ]; then
    printf '\n## Resultado (fallida, %s)\n\nInterrumpida: JARVIS se cerró mientras la ejecutaba y ya pasó su hora.\n' \
      "$(date -Iseconds)" >> "$f"
    mv "$f" cola/fallidas/
    echo "$(date -Iseconds) corredor: $(basename "$f") interrumpida hace más de 3 h, a fallidas" >> logs/corredor.log
  else
    mv "$f" cola/pendientes/
  fi
done

while true; do
  siguiente=$(ls cola/pendientes/*.md 2>/dev/null | sort | head -n 1)
  [ -z "$siguiente" ] && break

  nombre=$(basename "$siguiente")
  en_curso="cola/en-curso/$nombre"
  mv "$siguiente" "$en_curso"

  pedido=$(sed -n 's/^pedido: "\(.*\)"$/\1/p' "$en_curso" | sed 's/\\"/"/g')
  origen=$(sed -n 's/^origen: //p' "$en_curso")

  # Lo que llega de rutinas o del HUD corre sin conversación: JARVIS no puede esperar respuesta.
  automatico=0
  if [ "$origen" != "manual" ]; then
    automatico=1
    pedido="$pedido (Ejecución automática desde la cola ($origen): nadie puede responderte. No hagas preguntas; si te falta un dato, déjalo marcado como pendiente en la nota.)"
  fi

  echo "$(date -Iseconds) corredor > $nombre: $pedido" >> logs/corredor.log
  inicio=$(date +%s)

  # Tope de 20 min: si algo se cuelga (la red, un conector), la cola no se queda atascada para siempre.
  if respuesta=$(JARVIS_AUTOMATICO=$automatico timeout 20m ./scripts/jarvis.sh "$pedido" 2>&1); then
    destino="cola/hechas/$nombre"
    estado="hecha"
  else
    destino="cola/fallidas/$nombre"
    estado="fallida"
  fi

  {
    echo ""
    echo "## Resultado ($estado, $(( $(date +%s) - inicio )) s, $(date -Iseconds))"
    echo ""
    echo "$respuesta"
  } >> "$en_curso"
  mv "$en_curso" "$destino"

  echo "$(date -Iseconds) corredor < $nombre: $estado" >> logs/corredor.log
  echo "[$estado] $pedido"
done
