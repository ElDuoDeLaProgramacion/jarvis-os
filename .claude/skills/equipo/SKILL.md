---
name: equipo
description: Reparte un pedido entre los agentes especializados de JARVIS (programador, revisor-codigo, auditor-seguridad, disenador, juez-ideas, investigador) y junta sus respuestas. Úsala para "pídele al auditor...", "que lo revise el revisor", "junta al equipo", "crea un programa que..." o pedidos grandes que mezclan áreas.
---
# Equipo de agentes

Los agentes están en `.claude/agents/`. Se llaman con la herramienta de agentes (Task/Agent), cada uno con un encargo completo: él no ve esta conversación, así que dale el pedido de David, las rutas y lo que ya sabes.

| Agente | Para |
|---|---|
| `programador` | escribir, arreglar o crear un programa |
| `revisor-codigo` | revisar un cambio o proyecto sin tocarlo |
| `auditor-seguridad` | auditar servidores, webs, programas o dependencias |
| `disenador` | proponer o criticar un diseño, maquetas HTML |
| `juez-ideas` | evaluar una idea con nota y riesgos |
| `investigador` | investigar a fondo y comparar con fuentes |

## Cómo
1. Si David nombra un agente ("que lo vea el auditor"), usa ese.
2. Si no, elige los mínimos que hagan falta. Ejemplos:
   - "Crea un programa que..." → `programador` y después `revisor-codigo` sobre lo que hizo; si el revisor encuentra algo Alto, otra vuelta del `programador` (máximo dos vueltas).
   - "Audita mis servidores" → un `auditor-seguridad` por objetivo, en paralelo.
   - "¿Qué opinas de esta app?" → `disenador` y `juez-ideas` en paralelo.
3. Lanza en paralelo lo que no dependa de otra cosa.
   Si David quiere también la opinión de IAs externas ("con todas las IAs"), usa la habilidad `panel`, que combina estos agentes con varias IAs por especialidad.
4. Junta los resultados en `boveda/outputs/equipo/AAAA-MM-DD-<tema>.md` (frontmatter `fecha`, `tipo: equipo`, `tags`), con una sección por agente y enlaces `[[...]]` a las notas que usaron.

Las reglas de JARVIS valen para los agentes: nada de push, envíos, despliegues ni borrados sin el "sí" de David, y seguridad solo sobre sus sistemas.

Cada agente gasta uso de Claude como una petición entera: no lances más de los que el pedido necesita. En rutinas automáticas no uses agentes.

## Respuesta hablada
Lo que concluyó el equipo en dos o tres frases, y si algo necesita a David.
