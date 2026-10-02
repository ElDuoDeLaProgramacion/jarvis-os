---
name: suscripciones
description: Lleva el control de las suscripciones y cobros recurrentes de David a partir de su Gmail. Úsala para "revisa mis suscripciones", "cuánto pago al mes", "qué se renueva pronto", "cómo cancelo X" o pruebas gratis que terminan.
---
# Suscripciones

La lista vive en `boveda/wiki/suscripciones.md`. La fuente son los correos de cobro, recibo y renovación del conector **claude.ai Gmail** (solo lectura y borradores).

## Revisar (o "revisa mis suscripciones")
1. Lee `boveda/wiki/suscripciones.md` y su fecha `ultima-revision`. Si no hay, busca en los últimos 12 meses; si hay, desde esa fecha.
2. Busca en Gmail, por ejemplo:
   - `(suscripción OR suscripcion OR subscription OR membresía OR membership) after:AAAA/MM/DD`
   - `(recibo OR receipt OR factura OR invoice OR "payment received" OR "pago recibido" OR "se renovará" OR "will renew" OR renewal OR renovación) after:AAAA/MM/DD`
   - `("free trial" OR "prueba gratuita" OR "trial ends" OR "tu prueba") after:AAAA/MM/DD`
   - `(cancelled OR canceled OR cancelada OR "has been cancelled") after:AAAA/MM/DD`
3. Abre solo los hilos que parezcan cobros recurrentes. Por cada servicio saca: nombre, precio, moneda, ciclo (mensual, anual...), fecha del último cobro, próximo cobro (último cobro + ciclo, o la fecha que diga el correo) y estado: `activa`, `prueba`, `cancelada` o `dudosa` (un solo cobro, sin señal de que se repita).
4. Actualiza la tabla de `boveda/wiki/suscripciones.md` (una fila por servicio, sin duplicar) y `ultima-revision`. Recalcula los totales por moneda: mensual y anual equivalente. No conviertas monedas.
5. Para cada suscripción `activa` o `prueba` que se cobra en los próximos 7 días, añade a `boveda/wiki/tareas.md`, bajo `## Suscripciones`, si no existe ya:
   `- [ ] Decidir si sigo con <servicio> (<precio> <moneda>) 📅 <día antes del cobro> #suscripciones`
6. Escribe `boveda/outputs/suscripciones/AAAA-MM-DD-revision.md` con lo nuevo, lo que cambió de precio, las que vencen pronto y enlace a [[suscripciones]].
7. Responde en voz: total al mes, cuántas activas y qué se cobra pronto. Máximo 3 frases.

## Preguntas
"¿Cuánto pago al mes?", "¿qué se renueva esta semana?", "¿desde cuándo pago X?": responde desde `boveda/wiki/suscripciones.md`. Si la `ultima-revision` tiene más de 7 días, revisa antes.

## Cancelar
No puedes cancelar ni pagar nada. Lo que sí:
1. Busca en el último correo del servicio el enlace de "gestionar suscripción" o "cancelar". Si no hay, búscalo en la web (habilidad `busqueda`).
2. Dale a David el enlace y los pasos en una frase.
3. Si el servicio solo se cancela por correo, deja un borrador con la habilidad `correo`; nunca lo envíes sin su "sí, envíalo".
4. Cuando David diga que ya la canceló, cambia el estado a `cancelada` con la fecha.

## Reglas
- Nunca guardes números de tarjeta, cuentas, contraseñas ni enlaces con tokens de sesión. El servicio, el precio y la fecha bastan.
- Si un dato no sale en el correo, déjalo vacío con `?`; no lo inventes.
