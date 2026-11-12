import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  copiaDe, digitosLid, eleccion, esDavidConocido, esNo, esSi, esTeclaMusica, leerEstado, limpiar, lineaChat, medioDe, numeroDe, opcionesDe,
  ordenReenvios, partir, pesoDe, textoDe, vistosPor,
} from './util.mjs'

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

test('explicarError: traduce el motivo de jarvis.sh', async () => {
  const { explicarError } = await import('./util.mjs')
  assert.equal(explicarError(''), '')
  assert.equal(explicarError('SESION=abc\n'), '')
  const login = explicarError('algo\nERROR=Invalid API key · Please run /login\n')
  assert.match(login, /Invalid API key/)
  assert.match(login, /\/login/)
  assert.match(explicarError('ERROR=Claude AI usage limit reached|1730000000'), /límite de uso/)
  assert.match(explicarError('ERROR=no encuentro el programa claude en el PATH (/usr/bin)'), /reinstálalo/)
  assert.match(explicarError('ERROR=otra cosa rara'), /^Hubo un error al ejecutar el pedido: otra cosa rara$/)
})

test('ordenReenvios entiende encender, apagar, solo texto y consulta', () => {
  for (const t of ['desactiva los reenvíos', 'Apaga los avisos', 'Orión, pausa los reenvíos.', 'no me reenvies nada', 'reenvíos off'])
    assert.equal(ordenReenvios(t), 'nada', t)
  for (const t of ['activa los reenvíos', 'Enciende los avisos de WhatsApp', 'reenvíame todo', 'reenvios on'])
    assert.equal(ordenReenvios(t), 'todo', t)
  for (const t of ['reenvíos solo texto', 'avisos sin stickers', 'reenviame solo el texto'])
    assert.equal(ordenReenvios(t), 'texto', t)
  assert.equal(ordenReenvios('¿cómo están los reenvíos?'), 'consulta')
  for (const t of ['reenvíale a Ana la foto', 'activa la alarma', 'qué avisos hay del centinela hoy y por qué', 'hola'])
    assert.equal(ordenReenvios(t), null, t)
})

test('medioDe y copiaDe rehacen stickers, fotos, audios, ubicaciones y contactos', () => {
  const buf = Buffer.from('x')
  assert.equal(medioDe({ conversation: 'hola' }), null)
  assert.equal(medioDe({ stickerMessage: {} }), 'sticker')
  assert.deepEqual(copiaDe({ stickerMessage: {} }, buf), { sticker: buf })
  assert.equal(copiaDe({ stickerMessage: {} }, null), null)   // sin bajar el archivo no se puede
  assert.deepEqual(copiaDe({ audioMessage: { ptt: true } }, buf), { audio: buf, mimetype: 'audio/ogg; codecs=opus', ptt: true })
  assert.equal(copiaDe({ imageMessage: { caption: 'mira' } }, buf).caption, 'mira')
  const doc = { documentWithCaptionMessage: { message: { documentMessage: { fileName: 'a.pdf', mimetype: 'application/pdf', fileLength: 9 } } } }
  assert.equal(medioDe(doc), 'documento')
  assert.equal(copiaDe(doc, buf).fileName, 'a.pdf')
  assert.equal(pesoDe(doc), 9)
  assert.deepEqual(copiaDe({ locationMessage: { degreesLatitude: 4.6, degreesLongitude: -74 } }, null).location.degreesLatitude, 4.6)
  assert.equal(copiaDe({ contactMessage: { displayName: 'Ana', vcard: 'BEGIN:VCARD' } }, null).contacts.contacts[0].vcard, 'BEGIN:VCARD')
})

test('leerEstado acepta texto o foto dentro del repo y rechaza lo demás', () => {
  assert.deepEqual(leerEstado({ texto: ' Hola ', color: 'azul' }), { texto: 'Hola', archivo: '', color: '#1e3a8a', fuente: 0 })
  assert.equal(leerEstado({ texto: 'x', color: '#ABCDEF' }).color, '#abcdef')
  assert.equal(leerEstado({ texto: 'x', color: 'url(x)' }).color, '#111111')
  assert.equal(leerEstado({ texto: 'x', color: '#abcdef' }).color, '#abcdef')
  assert.equal(leerEstado({}), null)
  assert.equal(leerEstado({ archivo: '/etc/passwd' }), null)
  assert.equal(leerEstado({ archivo: 'cola/x.png' }, () => false), null)
  assert.equal(leerEstado({ archivo: 'cola/x.png' }, () => true).archivo, 'cola/x.png')
})

test('vistosPor junta contactos con número, sin repetir, y a uno mismo', () => {
  const c = { '573001@s.whatsapp.net': { nombre: 'Ana' }, '999@lid': { numero: '573001' }, '888@lid': { nombre: 'sin número' }, '573002@s.whatsapp.net': {} }
  assert.deepEqual(vistosPor(c, '573009@s.whatsapp.net').sort(), ['573001@s.whatsapp.net', '573002@s.whatsapp.net', '573009@s.whatsapp.net'])
  assert.deepEqual(vistosPor(c, '573009@s.whatsapp.net', ['+57 3005']).sort(), ['573005@s.whatsapp.net', '573009@s.whatsapp.net'])
})
