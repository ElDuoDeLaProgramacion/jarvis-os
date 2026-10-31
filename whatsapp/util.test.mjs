import { test } from 'node:test'
import assert from 'node:assert/strict'
import { digitosLid, eleccion, esDavidConocido, esNo, esSi, esTeclaMusica, opcionesDe, limpiar, lineaChat, numeroDe, partir, textoDe } from './util.mjs'

test('sí y no', () => {
  for (const t of ['sí', 'Si.', 'dale', 'ok envíalo', '¡Sí!']) assert.ok(esSi(t), t)
  for (const t of ['no', 'sí pero espera', 'mejor no', 'hola']) assert.ok(!esSi(t), t)
  for (const t of ['no', 'No.', 'cancela', 'no, déjalo así']) assert.ok(esNo(t), t)
  for (const t of ['no sé qué decirle a Ana, ayúdame con algo', 'nombre de Ana']) assert.ok(!esNo(t), t)
})

test('números de jid', () => {
  assert.equal(numeroDe('573001234567@s.whatsapp.net'), '573001234567')
  assert.equal(numeroDe('573001234567:12@s.whatsapp.net'), '573001234567')
  assert.equal(numeroDe('123456@lid'), '')
  assert.equal(numeroDe(undefined), '')
})

test('dígitos de un @lid', () => {
  assert.equal(digitosLid('123456@lid'), '123456')
  assert.equal(digitosLid('123456:7@lid'), '123456')
  assert.equal(digitosLid('573001234567@s.whatsapp.net'), '')
  assert.equal(digitosLid(undefined), '')
})

test('reconocer a David sin red', () => {
  const david = { pn: '573001234567@s.whatsapp.net', lid: '999888@lid' }
  const lids = new Set(['111222'])   // dígitos de @lid ya aprendidos como suyos
  // Por su número al lado (sender_pn o mapa lid->pn resuelto):
  assert.ok(esDavidConocido(david, lids, '777000@lid', '573001234567@s.whatsapp.net'))
  // Por su @lid de la cuenta, aunque no venga su número:
  assert.ok(esDavidConocido(david, lids, '999888@lid', null))
  assert.ok(esDavidConocido(david, lids, '999888:3@lid', null))
  // Por un @lid ya aprendido:
  assert.ok(esDavidConocido(david, lids, '111222@lid', null))
  // Un desconocido: ni su número, ni su @lid, ni aprendido -> no es David.
  assert.ok(!esDavidConocido(david, lids, '444555@lid', null))
  assert.ok(!esDavidConocido(david, lids, '444555@lid', '573009999999@s.whatsapp.net'))
  // Dos @lid distintos no deben "empatar" por tener número vacío ambos.
  assert.ok(!esDavidConocido(david, lids, '444555@lid', '666777@lid'))
})

test('texto de cada tipo de mensaje', () => {
  assert.equal(textoDe({ conversation: 'hola' }), 'hola')
  assert.equal(textoDe({ extendedTextMessage: { text: 'mira' } }), 'mira')
  assert.equal(textoDe({ imageMessage: { caption: 'la playa' } }), '(foto) la playa')
  assert.equal(textoDe({ audioMessage: { ptt: true } }), '(nota de voz)')
  assert.equal(textoDe({ documentMessage: { fileName: 'cv.pdf' } }), '(documento: cv.pdf)')
  assert.equal(textoDe({ reactionMessage: { text: '👍' } }), null)
  assert.equal(textoDe(undefined), null)
})

test('líneas del registro', () => {
  assert.equal(lineaChat({ hora: '14:32', chat: 'Ana', autor: 'Ana', texto: 'hola\nqué tal' }), '- 14:32 · Ana: hola / qué tal\n')
  assert.equal(lineaChat({ hora: '14:33', chat: 'Ana', autor: 'yo', texto: 'bien' }), '- 14:33 · yo → Ana: bien\n')
  assert.equal(lineaChat({ hora: '9:00', chat: 'Familia', autor: 'Mamá', texto: 'a', grupo: true }), '- 9:00 · Familia · Mamá: a\n')
})

test('formato y trozos', () => {
  assert.equal(limpiar('## Hola\n**ya** [aquí](https://x.co)'), 'Hola\n*ya* aquí (https://x.co)')
  const trozos = partir('a'.repeat(8000))
  assert.equal(trozos.join(''), 'a'.repeat(8000))
  assert.ok(trozos.every((t) => t.length <= 3500))
  assert.deepEqual(partir('uno\ndos', 5), ['uno', 'dos'])
})

test('teclas de música', () => {
  for (const t of ['Jarvis, play', 'pausa', 'Siguiente canción', 'sube el volumen', 'pasa 3 canciones', 'Retrocede dos canciones']) assert.ok(esTeclaMusica(t), t)
  for (const t of ['pon música', 'play de Bad Bunny', 'pausa la reunión de mañana']) assert.ok(!esTeclaMusica(t), t)
})

test('opciones de respuesta', () => {
  const salida = 'Aquí van:\n1) "¡Claro! ¿A qué hora?"\n2. Mañana no puedo, ¿el sábado?\n*3)* Te confirmo en un rato.\n4) sobra'
  assert.deepEqual(opcionesDe(salida), ['¡Claro! ¿A qué hora?', 'Mañana no puedo, ¿el sábado?', 'Te confirmo en un rato.'])
  assert.deepEqual(opcionesDe('NADA'), [])
  assert.equal(eleccion('2', 3), 1)
  assert.equal(eleccion('la 3', 3), 2)
  assert.equal(eleccion('envía la 1.', 3), 0)
  assert.equal(eleccion('4', 3), -1)
  assert.equal(eleccion('dile que 2 horas', 3), -1)
})

test('pedir opciones', async () => {
  const { pideOpciones } = await import('./util.mjs')
  for (const t of ['opciones', 'Dame opciones', '¿Qué le respondo?', 'qué le digo', 'propón respuestas']) assert.ok(pideOpciones(t), t)
  for (const t of ['dile que llego a las 8', 'qué opciones hay de vuelos a Bogotá mañana', 'hola']) assert.ok(!pideOpciones(t), t)
})

test('tipos de archivo', async () => {
  const { tipoDe, extensionDe, nombreSeguro } = await import('./util.mjs')
  assert.equal(tipoDe('tabla.XLSX'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  assert.equal(tipoDe('raro.xyz'), 'application/octet-stream')
  assert.equal(extensionDe('image/jpeg'), 'jpg')
  assert.equal(extensionDe('application/pdf', 'Factura Enero.pdf'), 'pdf')
  assert.equal(nombreSeguro('../../etc/passwd'), 'passwd')
})
