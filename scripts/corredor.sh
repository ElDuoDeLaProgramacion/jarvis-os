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

# Si un corredor anterior murió a medias, devuelve sus intenciones a pendientes.
for f in cola/en-curso/*.md; do
  [ -e "$f" ] && mv "$f" cola/pendientes/
done

while true; do
  siguiente=$(ls cola/pendientes/*.md 2>/dev/null | sort | head -n 1)
  [ -z "$siguiente" ] && break

  nombre=$(basename "$siguiente")
  en_curso="cola/en-curso/$nombre"
  mv "$siguiente" "$en_curso"

  pedido=$(sed -n 's/^pedido: "\(.*\)"$/\1/p' "$en_curso" | sed 's/\\"/"/g')
  origen=$(sed -n 's/^origen: //p' "$en_curso")

  # Las rutinas corren sin nadie delante: JARVIS no debe esperar respuesta.
  if [ "$origen" = "rutina" ]; then
    pedido="$pedido (Ejecución automática de una rutina: nadie está mirando. No hagas preguntas; si te falta un dato, déjalo marcado como pendiente en la nota.)"
  fi

  echo "$(date -Iseconds) corredor > $nombre: $pedido" >> logs/corredor.log
  inicio=$(date +%s)

  if respuesta=$(./scripts/jarvis.sh "$pedido" 2>&1); then
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
