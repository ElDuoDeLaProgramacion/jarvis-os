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

/** Los dígitos de un @lid ("1234:5@lid" -> "1234"); vacío si no es un @lid. */
export function digitosLid(jid) {
  if (!jid || !/@lid$/.test(jid)) return ''
  return soloDigitos(jid.split('@')[0].split(':')[0])
}

/**
 * ¿Este chat es David, decidido sin preguntarle a la red? WhatsApp no siempre manda el número de quien
 * escribe (sobre todo al cambiar de red o de configuración): llega un @lid pelado. Reconocemos a David por
 * lo que ya sabemos: su número (david.pn), su @lid de la cuenta (david.lid), los @lid que ya aprendimos que
 * son suyos (lidsDavid, un Set de dígitos), o un número ya resuelto a su lado (pnResuelto, de sender_pn o del
 * mapa lid->pn). Así un @lid conocido se reconoce al instante, aunque esta vez no venga su número.
 */
export function esDavidConocido(david, lidsDavid, chat, pnResuelto) {
  if (!chat || !david || !david.pn) return false
  const suNumero = numeroDe(david.pn)
  const lidChat = digitosLid(chat)
  if (david.lid && lidChat && lidChat === digitosLid(david.lid)) return true
  if (lidsDavid && lidChat && lidsDavid.has(lidChat)) return true
  if (pnResuelto && numeroDe(pnResuelto) && numeroDe(pnResuelto) === suNumero) return true
  return false
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
    .replace(/[.,!¡¿?]/g, '').replace(/^(jarvis|ori[oó]n)\s+/, '').trim()
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

/** "opciones", "dame opciones", "qué le respondo": David pide respuestas propuestas para el último aviso. */
export function pideOpciones(texto) {
  const t = texto.trim().toLowerCase().replace(/[¿?¡!.,]/g, '')
  if (t.length > 40) return false
  return /^(dame |dime |mu[eé]strame |prop[oó]n(me)? )?(las |unas )?(opciones|respuestas)( de respuesta)?$/.test(t) ||
    /^qu[eé] le (respondo|contesto|digo|puedo responder|puedo decir)$/.test(t)
}

const TIPOS = {
  pdf: 'application/pdf', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  xls: 'application/vnd.ms-excel', csv: 'text/csv', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', txt: 'text/plain', md: 'text/markdown',
  html: 'text/html', json: 'application/json', zip: 'application/zip',
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif',
}

/** Tipo MIME por la extensión del archivo. */
export function tipoDe(nombre) {
  return TIPOS[(nombre.split('.').pop() || '').toLowerCase()] || 'application/octet-stream'
}

/** Extensión que corresponde a un tipo MIME (para guardar lo que manda David). */
export function extensionDe(mime, nombre = '') {
  const propia = /\.([a-z0-9]{1,5})$/i.exec(nombre)?.[1]
  if (propia) return propia.toLowerCase()
  const base = (mime || '').split(';')[0].trim()
  return Object.keys(TIPOS).find((e) => TIPOS[e] === base) || 'bin'
}

/** Nombre de archivo seguro: sin rutas ni caracteres raros. */
export function nombreSeguro(nombre) {
  return (nombre || 'archivo').split(/[\\/]/).pop().replace(/[^\w.\- áéíóúñÁÉÍÓÚÑ]/g, '_').slice(-80) || 'archivo'
}

/**
 * El motivo que scripts/jarvis.sh deja como "ERROR=..." en stderr, traducido a algo que David pueda arreglar.
 * Vacío si no hay motivo (entonces el puente usa el aviso genérico).
 */
export function explicarError(stderr) {
  const linea = String(stderr ?? '').split('\n').reverse().find((l) => l.startsWith('ERROR='))
  const motivo = linea ? linea.slice(6).trim() : ''
  if (!motivo) return ''
  const m = motivo.toLowerCase()
  let consejo = ''
  if (/\/login|not logged in|invalid api key|authentication|401|oauth|token (has )?expired|credit balance/.test(m)) {
    consejo = 'La sesión o la clave de Claude en el servidor ya no vale. Entra por SSH, escribe claude y usa /login ' +
      '(si en ~/jarvis-os/.env hay una ANTHROPIC_API_KEY vencida, bórrala o cámbiala).'
  } else if (/usage limit|rate limit|429|limit reached|overloaded|529/.test(m)) {
    consejo = 'Claude llegó a su límite de uso o está saturado; vuelve a funcionar solo en un rato.'
  } else if (/no encuentro el programa claude|command not found|enoent/.test(m)) {
    consejo = 'El servidor no encuentra el programa claude; reinstálalo o revisa el PATH.'
  } else if (/no space left|enospc/.test(m)) {
    consejo = 'El disco del servidor está lleno.'
  }
  return `Hubo un error al ejecutar el pedido: ${motivo.slice(0, 300)}${consejo ? `\n${consejo}` : ''}`
}

// ---------- Reenvíos: el contenido real de lo que te escriben, no solo "(sticker)" ----------

export const MODOS_REENVIO = ['todo', 'texto', 'nada']

/**
 * Órdenes para encender o apagar los reenvíos (los avisos de "Te escribió X" con lo que mandó).
 * Devuelve 'todo' | 'texto' | 'nada' | 'consulta', o null si no es una de esas órdenes.
 */
export function ordenReenvios(texto) {
  const t = String(texto ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[¿?¡!.,]/g, '').replace(/^(jarvis|orion)\s+/, '').replace(/\s+/g, ' ').trim()
  if (t.length > 60) return null
  const que = '(?:los |las )?(?:reenvios|reenvio|avisos|aviso|notificaciones|alertas)(?: de (?:whatsapp|mensajes|los mensajes|chats))?'
  if (new RegExp(`^(?:como (?:estan|van|esta|va) |estado de )${que}$`).test(t)) return 'consulta'
  if (new RegExp(`^${que} (?:solo|solamente|nada mas que|nomas) (?:de |con |el |en )?texto$`).test(t) ||
      new RegExp(`^${que} sin (?:archivos|stickers|fotos|medios|multimedia)$`).test(t) ||
      /^(?:reenviame|mandame) solo (?:el )?texto$/.test(t)) return 'texto'
  if (new RegExp(`^(?:desactiva|apaga|pausa|para|deten|detén|quita|silencia|cancela|suspende)(?:me)? ${que}$`).test(t) ||
      new RegExp(`^${que} (?:off|apagados?|desactivados?)$`).test(t) ||
      /^no me (?:reenvies|mandes|avises) (?:nada|mas|los mensajes)$/.test(t)) return 'nada'
  if (new RegExp(`^(?:activa|enciende|prende|reanuda|vuelve a activar|pon|devuelveme)(?:me)? ${que}(?: completos?)?$`).test(t) ||
      new RegExp(`^${que} (?:on|encendidos?|activados?)$`).test(t) ||
      /^(?:reenviame|mandame) todo$/.test(t)) return 'todo'
  return null
}

/** Qué tipo de contenido trae un mensaje que vale la pena reenviar tal cual (null si es solo texto o nada). */
export function medioDe(m) {
  if (!m) return null
  if (m.documentWithCaptionMessage) return medioDe(m.documentWithCaptionMessage.message)
  for (const [clave, tipo] of [['stickerMessage', 'sticker'], ['imageMessage', 'imagen'], ['videoMessage', 'video'],
    ['audioMessage', 'audio'], ['documentMessage', 'documento'], ['locationMessage', 'ubicacion'],
    ['liveLocationMessage', 'ubicacion'], ['contactMessage', 'contacto'], ['contactsArrayMessage', 'contactos']]) {
    if (m[clave]) return tipo
  }
  return null
}

/**
 * El contenido para sendMessage que reproduce el mensaje recibido. `datos` es el archivo ya bajado
 * (sticker, foto, video, audio o documento); ubicaciones y contactos no necesitan bajar nada.
 * null si no se puede rehacer (entonces el puente prueba con un reenvío normal).
 */
export function copiaDe(m, datos) {
  if (!m) return null
  if (m.documentWithCaptionMessage) return copiaDe(m.documentWithCaptionMessage.message, datos)
  if (m.locationMessage || m.liveLocationMessage) {
    const l = m.locationMessage || m.liveLocationMessage
    return { location: { degreesLatitude: l.degreesLatitude, degreesLongitude: l.degreesLongitude, name: l.name || undefined, address: l.address || undefined } }
  }
  if (m.contactMessage) return { contacts: { displayName: m.contactMessage.displayName, contacts: [{ vcard: m.contactMessage.vcard }] } }
  if (m.contactsArrayMessage) {
    return { contacts: { displayName: m.contactsArrayMessage.displayName, contacts: (m.contactsArrayMessage.contacts || []).map((c) => ({ vcard: c.vcard })) } }
  }
  if (!datos) return null
  if (m.stickerMessage) return { sticker: datos }
  if (m.imageMessage) return { image: datos, mimetype: m.imageMessage.mimetype || undefined, caption: m.imageMessage.caption || undefined }
  if (m.videoMessage) {
    return { video: datos, mimetype: m.videoMessage.mimetype || undefined, caption: m.videoMessage.caption || undefined, gifPlayback: !!m.videoMessage.gifPlayback }
  }
  if (m.audioMessage) return { audio: datos, mimetype: m.audioMessage.mimetype || 'audio/ogg; codecs=opus', ptt: !!m.audioMessage.ptt }
  if (m.documentMessage) {
    return { document: datos, mimetype: m.documentMessage.mimetype || 'application/octet-stream', fileName: m.documentMessage.fileName || 'archivo', caption: m.documentMessage.caption || undefined }
  }
  return null
}

/** Peso declarado del archivo de un mensaje (0 si no trae). */
export function pesoDe(m) {
  if (!m) return 0
  if (m.documentWithCaptionMessage) return pesoDe(m.documentWithCaptionMessage.message)
  const x = m.stickerMessage || m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage
  return Number(x?.fileLength || 0)
}

// ---------- Estados de WhatsApp ----------

const COLORES = { negro: '#111111', azul: '#1e3a8a', verde: '#065f46', morado: '#5b21b6', rojo: '#9f1239', naranja: '#c2410c', gris: '#374151', rosado: '#be185d', rosa: '#be185d', cafe: '#78350f' }

/**
 * Lo que Orión dejó en cola/whatsapp/estado.json, revisado: { texto, archivo, color, fuente }.
 * Texto solo: estado de texto con fondo de color. Con archivo (foto o video): el texto va de pie.
 * `dentro(ruta)` dice si la ruta del archivo es una que el puente puede leer. null si no sirve.
 */
export function leerEstado(datos, dentro = () => true) {
  if (!datos || typeof datos !== 'object') return null
  const texto = typeof datos.texto === 'string' ? datos.texto.trim().slice(0, 700) : ''
  let archivo = typeof datos.archivo === 'string' ? datos.archivo.trim() : ''
  if (archivo && (!/\.(jpe?g|png|webp|mp4|mov|3gp)$/i.test(archivo) || !dentro(archivo))) return null
  if (!texto && !archivo) return null
  let color = typeof datos.color === 'string' ? datos.color.trim().toLowerCase() : ''
  color = COLORES[color] || (/^#[0-9a-f]{6}$/.test(color) ? color : '#111111')
  const fuente = Number.isInteger(datos.fuente) && datos.fuente >= 0 && datos.fuente <= 9 ? datos.fuente : 0
  return { texto, archivo, color, fuente }
}

/** A quién se le muestra un estado: los contactos con número (jid @s.whatsapp.net), sin repetir, y uno mismo. */
export function vistosPor(contactos, yo, soloNumeros = []) {
  const lista = new Set()
  if (soloNumeros.length) {
    for (const n of soloNumeros) if (soloDigitos(n)) lista.add(`${soloDigitos(n)}@s.whatsapp.net`)
  } else {
    for (const [jid, c] of Object.entries(contactos || {})) {
      const n = numeroDe(jid) || soloDigitos(c?.numero)
      if (n) lista.add(`${n}@s.whatsapp.net`)
    }
  }
  if (yo && numeroDe(yo)) lista.add(`${numeroDe(yo)}@s.whatsapp.net`)
  return [...lista]
}
