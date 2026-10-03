import { test } from 'node:test'
import assert from 'node:assert/strict'
import { esNo, esSi, limpiar, lineaChat, numeroDe, partir, textoDe } from './util.mjs'

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
