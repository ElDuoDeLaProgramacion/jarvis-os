// Funciones sin estado del puente de WhatsApp (se prueban con: node --test whatsapp/)
import { readFileSync, existsSync } from 'node:fs'

/** Lee .env (KEY=valor) sin pisar lo que ya esté en el entorno. */
export function cargarEnv(archivo) {
  if (!existsSync(archivo)) return
  for (const linea of readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '')
  }
}

export const soloDigitos = (s) => String(s ?? '').replace(/\D/g, '')

/** "57300...@s.whatsapp.net" o "57300...:12@s.whatsapp.net" -> "57300..." (vacío si es un @lid). */
export function numeroDe(jid) {
  if (!jid || !/@s\.whatsapp\.net$/.test(jid)) return ''
  return soloDigitos(jid.split('@')[0].split(':')[0])
}

const SI = /^(si|sí|sip|dale|claro|confirmo|confirmado|hazlo|envialo|envíalo|mandalo|mándalo|de una|ok|okay|listo|adelante)(?=$|[\s.,!?¡¿])/i

export function esSi(texto) {
  const plano = texto.toLowerCase().trim().replace(/^[\s.,!¡¿?]+|[\s.,!¡¿?]+$/g, '')
  return SI.test(plano) && !/\bno\b|\bespera\b|\bmejor\b/.test(plano)
}

export function esNo(texto) {
  const plano = texto.toLowerCase().trim().replace(/^[\s.,!¡¿?]+|[\s.,!¡¿?]+$/g, '')
  return /^(no|nop|nel|cancela|cancelar|cancélalo|cancelalo|olvídalo|olvidalo|déjalo|dejalo)(?=$|[\s.,!?¡¿])/.test(plano) &&
    plano.split(/\s+/).length <= 4
}

/** Órdenes de música que resuelve la voz del PC con las teclas multimedia (voz/jarvis_voz.py, accion_musica). */
export function esTeclaMusica(texto) {
  const plano = texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[.,!¡¿?]/g, '').replace(/^jarvis\s+/, '').trim()
  return /^(play|dale play|ponle play|pausa|pon pausa|para la musica|sigue|reanuda|continua|siguiente|siguiente cancion|pasa la cancion|anterior|cancion anterior|(sube|baja)( el)? volumen( un poco)?)$/.test(plano) ||
    /^(pasa|pasale|salta|saltate|adelanta|retrocede|regresa|devuelvete|devuelve|vuelve) (\d{1,2}|una?|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez) (canciones|cancion|temas|tema|rolas|rola)( atras)?$/.test(plano)
}

/** De la salida de JARVIS saca las opciones "1) ...", "2) ...", "3) ...". */
export function opcionesDe(salida) {
  const opciones = []
  for (const linea of salida.split('\n')) {
    const m = linea.match(/^\s*\*?([1-3])[).:\-]\*?\s+(.+?)\s*$/)
    if (m && Number(m[1]) === opciones.length + 1) opciones.push(m[2].replace(/^["“](.*)["”]$/, '$1'))
  }
  return opciones
}

/** "1", "la 2", "opción 3", "envía la 2" -> índice (0, 1, 2). -1 si no elige ninguna. */
export function eleccion(texto, cuantas) {
  const plano = texto.toLowerCase().trim().replace(/[.,!¡¿?]/g, '')
  const m = plano.match(/^(?:(?:envia|envía|manda|mándale|mandale|la|opcion|opción|numero|número)\s+)*([1-9])$/)
  const n = m ? Number(m[1]) : 0
  return n >= 1 && n <= cuantas ? n - 1 : -1
}

export const esPregunta = (r) => r.trim().endsWith('?') || /\?\s*s[ií] o no/i.test(r.slice(-160))

/** WhatsApp no entiende Markdown completo: dejamos *negrita* simple y quitamos lo demás. */
export function limpiar(texto) {
  return texto
    .replace(/\*\*(.+?)\*\*/g, '*$1*')
    .replace(/^#+\s*/gm, '')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)')
    .trim()
}

/** Los mensajes muy largos van en trozos, cortando por párrafos. */
export function partir(texto, largo = 3500) {
  const trozos = []
  let actual = ''
  for (let parrafo of texto.split('\n')) {
    while (parrafo.length > largo) {
      if (actual) trozos.push(actual)
      trozos.push(parrafo.slice(0, largo))
      actual = ''
      parrafo = parrafo.slice(largo)
    }
    if (actual && actual.length + parrafo.length + 1 > largo) {
      trozos.push(actual)
      actual = ''
    }
    actual += (actual ? '\n' : '') + parrafo
  }
  return actual ? [...trozos, actual] : trozos
}

/** Texto legible de un mensaje ya normalizado (normalizeMessageContent). null = no se anota. */
export function textoDe(m) {
  if (!m) return null
  if (m.conversation) return m.conversation
  if (m.extendedTextMessage?.text) return m.extendedTextMessage.text
  const con = (etiqueta, pie) => (pie ? `(${etiqueta}) ${pie}` : `(${etiqueta})`)
  if (m.imageMessage) return con('foto', m.imageMessage.caption)
  if (m.videoMessage) return con('video', m.videoMessage.caption)
  if (m.audioMessage) return m.audioMessage.ptt ? '(nota de voz)' : '(audio)'
  if (m.documentMessage) return con(`documento: ${m.documentMessage.fileName || 'sin nombre'}`, m.documentMessage.caption)
  if (m.documentWithCaptionMessage) return textoDe(m.documentWithCaptionMessage.message)
  if (m.stickerMessage) return '(sticker)'
  if (m.locationMessage || m.liveLocationMessage) return '(ubicación)'
  if (m.contactMessage || m.contactsArrayMessage) return '(contacto compartido)'
  if (m.pollCreationMessage || m.pollCreationMessageV3) return con('encuesta', (m.pollCreationMessage || m.pollCreationMessageV3).name)
  return null // reacciones, mensajes de protocolo, ediciones, etc.
}

/** Una línea del registro diario de chats:
 *  "- 14:32 · Ana: hola", "- 14:33 · yo → Ana: dale", "- 14:40 · Familia · Ana: hola". */
export function lineaChat({ hora, chat, autor, texto, grupo }) {
  const plano = texto.replace(/\s*\n\s*/g, ' / ')
  if (grupo) return `- ${hora} · ${chat} · ${autor}: ${plano}\n`
  return autor === 'yo' ? `- ${hora} · yo → ${chat}: ${plano}\n` : `- ${hora} · ${chat}: ${plano}\n`
}
