// [US-301] Régler la voix de son compagnon — la logique de la section « Voix », sans React.
//
// Tout ce qui se décide ici peut se vérifier sans écran (`npm test`) : la dictée est-elle
// possible sur ce navigateur (CA6), quelle voix est cochée, que devient un changement refusé
// par le serveur (CA5), un seul extrait à la fois (CA3).

export const TEXTE_ENREGISTRE = 'Enregistré'
export const TEXTE_ERREUR_RESEAU = 'Non enregistré : pas de réseau'
export const TEXTE_MODE_VOCAL_ETEINT = 'Activez-le pour dicter vos phrases à Gaston et écouter ses réponses.'
// « Enregistré » reste affiché 2 s à droite du titre (maquette).
export const DUREE_RETOUR_MS = 2000
export const TEXTE_EXTRAIT_INDISPONIBLE = 'L’extrait n’est pas disponible pour le moment.'

export const MESSAGE_CONNEXION_NON_SECURISEE = 'La dictée demande une connexion sécurisée'
export const MESSAGE_DICTEE_NON_SUPPORTEE = 'Ce navigateur ne permet pas la dictée'

/** [CA6] L'encadré d'information de la maquette : la raison, puis ce qui reste possible. */
export function texteEmpechementDictee(message) {
  return `${message}. La lecture des réponses reste disponible.`
}

// Un silence de 0,1 s (WAV 8 bits mono) : joué DANS le tap sur ▶, il déverrouille l'élément audio
// sur iPhone/iPad ; l'extrait réel, qui demande un aller-retour réseau, y est ensuite chargé (CA3).
export const SILENCE_WAV =
  'data:audio/wav;base64,UklGRkQDAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YSADAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgA=='

export const REGLAGES_PAR_DEFAUT = { mode_vocal: false, voix_id: null, lecture_auto: true }

/**
 * [CA6] Ce navigateur peut-il enregistrer la voix ?
 * `env` = { isSecureContext, MediaRecorder, mediaDevices } ; par défaut, le navigateur courant.
 * Rend { possible, message } : `message` n'est renseigné que si la dictée est impossible.
 * La connexion non sécurisée passe avant : c'est ce que le jardinier peut corriger.
 */
export function capaciteDictee(env = navigateur()) {
  if (!env.isSecureContext) return { possible: false, message: MESSAGE_CONNEXION_NON_SECURISEE }
  if (!env.MediaRecorder || !env.mediaDevices) return { possible: false, message: MESSAGE_DICTEE_NON_SUPPORTEE }
  return { possible: true, message: null }
}

function navigateur() {
  if (typeof window === 'undefined') return {}
  return {
    isSecureContext: window.isSecureContext,
    MediaRecorder: window.MediaRecorder,
    mediaDevices: typeof navigator !== 'undefined' ? navigator.mediaDevices : undefined,
  }
}

/** [CA2] Les voix à afficher, la voix lue cochée. `voixId` = la voix EFFECTIVE du serveur. */
export function voixAffichees(catalogue, voixId) {
  return (catalogue?.voix ?? []).map((v) => ({ ...v, cochee: v.id === voixId }))
}

/** [CA7] Le catalogue de secours s’affiche sans alerte : rien à signaler à l’écran. */
export function alerteCatalogue() {
  return null
}

/** [CA5] Les réglages après un changement demandé (optimiste) ; `precedents` si le serveur refuse. */
export function appliquerChangement(reglages, changement) {
  return { ...reglages, ...changement }
}

/** [CA5] Le message qui suit un enregistrement : « Enregistré », ou l’erreur réseau + l’état d’avant. */
export function issueEnregistrement(reussite, precedents, serveur) {
  return reussite
    ? { reglages: { ...REGLAGES_PAR_DEFAUT, ...serveur }, message: TEXTE_ENREGISTRE, erreur: false }
    : { reglages: precedents, message: TEXTE_ERREUR_RESEAU, erreur: true }
}

/** [CA3] Lancer un extrait arrête le précédent : rend l’identifiant à jouer, ou null pour arrêter. */
export function extraitSuivant(enCours, demande) {
  return enCours === demande ? null : demande
}

/** [CA1, CA2, CA4] Ce que la section montre, selon le mode vocal et la capacité du navigateur. */
export function sectionVisible(reglages, capacite) {
  return {
    interrupteurMode: true,
    listeDesVoix: Boolean(reglages.mode_vocal),
    interrupteurLecture: Boolean(reglages.mode_vocal),
    avertissementDictee: Boolean(reglages.mode_vocal) && !capacite.possible ? capacite.message : null,
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// [US-302] Dicter une phrase au compagnon — « appuyer pour parler », sans React (CA11)
// ═════════════════════════════════════════════════════════════════════════════
// Un appui démarre l'enregistrement, un second l'arrête ; le fichier part en transcription
// (`POST /compagnon/voix/transcrire`), puis la phrase part à Gaston comme une phrase tapée (D4).

export const DUREE_DICTEE_MAX_S_DEFAUT = 60

/** [CA11] Formats essayés dans l'ordre : Opus (Chrome, Edge, Firefox, Android), puis AAC (Safari), puis Ogg. */
export const TYPES_MIME_DICTEE = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg']

export const MESSAGE_MICRO_ABSENT = 'Aucun micro détecté sur cet appareil'
export const TEXTE_MICRO_REFUSE =
  'Le micro est bloqué. Autorisez-le dans les réglages du navigateur (icône à gauche de l’adresse ; sur iPhone : Réglages › Safari › Micro), puis réessayez.'
export const TEXTE_MICRO_OCCUPE = 'Le micro est déjà utilisé par une autre application. Fermez-la, puis réessayez.'
export const TEXTE_DUREE_MAX = 'Durée maximale atteinte.'
export const TEXTE_RIEN_ENTENDU = 'Je n’ai rien entendu, réessayez.'
export const TEXTE_TROP_LONG = 'Message trop long, découpez-le.'
export const TEXTE_DICTEE_INDISPONIBLE = 'La dictée est indisponible pour le moment, écrivez votre message.'
export const TEXTE_LIMITE_DICTEES = 'Limite de dictées du jour atteinte.'
export const TEXTE_INDICE_ECOUTE = 'Touchez de nouveau pour envoyer à Gaston'
// La même borne qu'une phrase tapée (`LONGUEUR_MAX` de lib/compagnon.js).
export const LONGUEUR_MAX_DICTEE = 1000

/** Les états du bouton 🎤 (maquette « Compagnon - Voix », §2). */
export const ETAT = Object.freeze({
  INDISPONIBLE: 'indisponible',   // explication à la place du 🎤 (CA8)
  PRET: 'pret',                   // 🎤 à côté d'Envoyer
  DEMANDE: 'demande',             // le navigateur demande l'accès au micro (CA2)
  ECOUTE: 'ecoute',               // enregistrement, durée écoulée, ⏹ (CA2)
  TRANSCRIPTION: 'transcription', // 🎤 et Envoyer inactifs, micro libéré (CA4)
})

/**
 * [CA11] Le premier format que ce navigateur sait enregistrer ; '' = laisser le navigateur choisir
 * (iOS anciens : `isTypeSupported` absent, MediaRecorder rend du MP4 de lui-même).
 */
export function choisirTypeMime(MediaRecorderCtor) {
  if (!MediaRecorderCtor || typeof MediaRecorderCtor.isTypeSupported !== 'function') return ''
  return TYPES_MIME_DICTEE.find((t) => {
    try { return MediaRecorderCtor.isTypeSupported(t) } catch { return false }
  }) ?? ''
}

/** L'extension du fichier envoyé, d'après le type réellement produit (le serveur lit le format dessus). */
export function extensionDictee(typeMime) {
  const t = (typeMime || '').toLowerCase()
  if (t.includes('mp4') || t.includes('m4a') || t.includes('aac')) return 'mp4'
  if (t.includes('ogg')) return 'ogg'
  if (t.includes('wav')) return 'wav'
  return 'webm'
}

/** « 0:07 », « 1:00 » : la durée écoulée du bandeau d'écoute. */
export function formaterDuree(secondes) {
  const s = Math.max(0, Math.floor(secondes || 0))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** [CA3] La dictée doit-elle s'arrêter seule ? */
export const dureeAtteinte = (ecouleS, maxS = DUREE_DICTEE_MAX_S_DEFAUT) => ecouleS >= maxS

/**
 * [CA2, CA4] La machine d'états du bouton. Un événement sans effet dans l'état courant le laisse
 * tel quel : un appui pendant la transcription ne relance rien (CA4).
 */
export function etatSuivant(etat, evenement) {
  switch (etat) {
    case ETAT.PRET:
      return evenement === 'appui' ? ETAT.DEMANDE : etat
    case ETAT.DEMANDE:
      if (evenement === 'micro_accorde') return ETAT.ECOUTE
      if (evenement === 'micro_refuse') return ETAT.PRET
      if (evenement === 'micro_absent') return ETAT.INDISPONIBLE
      return etat
    case ETAT.ECOUTE:
      if (evenement === 'appui' || evenement === 'duree_max') return ETAT.TRANSCRIPTION
      if (evenement === 'echec') return ETAT.PRET
      return etat
    case ETAT.TRANSCRIPTION:
      return evenement === 'transcrit' || evenement === 'echec' ? ETAT.PRET : etat
    default:
      return etat
  }
}

/** [CA1, CA4, CA8] Ce que montre le pied du panneau pour un état donné. */
export function affichageMicro(etat, { modeVocal, occupe = false } = {}) {
  if (!modeVocal) return { bouton: false, saisie: true, envoiActif: true, boutonActif: false, libelle: '' }
  return {
    bouton: etat !== ETAT.INDISPONIBLE,
    saisie: etat !== ETAT.ECOUTE && etat !== ETAT.TRANSCRIPTION,
    boutonActif: etat === ETAT.ECOUTE || (!occupe && etat === ETAT.PRET),
    envoiActif: etat !== ETAT.TRANSCRIPTION && etat !== ETAT.ECOUTE,
    libelle: etat === ETAT.ECOUTE ? 'Arrêter la dictée et envoyer'
      : etat === ETAT.TRANSCRIPTION ? 'Transcription en cours' : 'Dicter un message',
  }
}

/**
 * [CA8] Ce que dit un refus de `getUserMedia` : `note` au-dessus de la saisie (le 🎤 reste pour
 * réessayer), ou `indisponible` (le 🎤 est remplacé par l'explication).
 */
export function issueErreurMicro(err) {
  const nom = err?.name ?? ''
  if (['NotAllowedError', 'PermissionDeniedError', 'SecurityError'].includes(nom)) {
    return { evenement: 'micro_refuse', note: { ton: 'warn', texte: TEXTE_MICRO_REFUSE } }
  }
  if (['NotFoundError', 'DevicesNotFoundError', 'OverconstrainedError'].includes(nom)) {
    return { evenement: 'micro_absent', indisponible: MESSAGE_MICRO_ABSENT }
  }
  if (['NotReadableError', 'TrackStartError', 'AbortError'].includes(nom)) {
    return { evenement: 'micro_refuse', note: { ton: 'warn', texte: TEXTE_MICRO_OCCUPE } }
  }
  return { evenement: 'micro_refuse', note: { ton: 'warn', texte: TEXTE_DICTEE_INDISPONIBLE } }
}

/** [CA5, CA9, CA12] Ce que dit un refus de `/compagnon/voix/transcrire`. */
export function noteErreurTranscription(err) {
  switch (err?.statut) {
    case 429: return { ton: 'warn', texte: TEXTE_LIMITE_DICTEES }
    case 422: return err.code === 'message_trop_long'
      ? { ton: 'warn', texte: TEXTE_TROP_LONG } : { ton: 'info', texte: TEXTE_RIEN_ENTENDU }
    case 413:
    case 403: return { ton: 'warn', texte: err.message || TEXTE_DICTEE_INDISPONIBLE }
    default: return { ton: 'warn', texte: TEXTE_DICTEE_INDISPONIBLE }
  }
}

/** [CA7] Après la transcription : la phrase part à Gaston, ou une note dit pourquoi rien n'est parti. */
export function issueTranscription(texte) {
  const phrase = (texte ?? '').trim()
  if (!phrase) return { envoyer: false, phrase: '', note: { ton: 'info', texte: TEXTE_RIEN_ENTENDU } }
  if (phrase.length > LONGUEUR_MAX_DICTEE) return { envoyer: false, phrase: '', note: { ton: 'warn', texte: TEXTE_TROP_LONG } }
  return { envoyer: true, phrase, note: null }
}

// ── [CA10] Une lecture en cours s'arrête AVANT que le micro s'ouvre ─────────────
// Toute lecture audio du compagnon (US-304) s'inscrit ici ; la dictée les arrête toutes, de façon
// synchrone, dans le geste de l'appui sur 🎤.
const lecteurs = new Set()

/** Inscrit une fonction d'arrêt ; rend de quoi la désinscrire. */
export function inscrireLecture(arreter) {
  lecteurs.add(arreter)
  return () => lecteurs.delete(arreter)
}

/** Arrête toutes les lectures inscrites ; rend leur nombre. */
export function arreterLectures() {
  const n = lecteurs.size
  for (const arreter of [...lecteurs]) {
    try { arreter() } catch { /* une lecture déjà finie ne gêne pas */ }
  }
  lecteurs.clear()
  return n
}

/** [US-302] Nom de l'événement émis par la section « Voix » quand les réglages changent. */
export const EVENEMENT_PREFERENCES_VOIX = 'potager:preferences-voix'

// ═════════════════════════════════════════════════════════════════════════════
// [US-304] Écouter la réponse de Gaston — la règle de lecture, sans React (CA10)
// ═════════════════════════════════════════════════════════════════════════════
// Ce qui est lu est le résumé parlé de l'échange (US-303), demandé PAR SON IDENTIFIANT à
// `POST /compagnon/voix/lecture/{echange_id}` : la PWA n'envoie jamais de texte à dire.

export const LIBELLE_ECOUTER = 'Écouter la réponse'
export const LIBELLE_ARRETER = 'Arrêter la lecture'
export const LIBELLE_ANNULER = 'Annuler la lecture'
// Ce que dit la ligne d'écoute sous la bulle (maquette « Compagnon - Voix », §3).
export const TEXTE_ECOUTER = 'Écouter'
export const TEXTE_EN_LECTURE = 'Lecture…'
export const TEXTE_PREPARATION = 'Préparation…'
export const TEXTE_LECTURE_INDISPONIBLE = 'Lecture indisponible pour le moment'
export const TEXTE_LIMITE_LECTURES = 'Limite de lectures du jour atteinte'

/**
 * [CA2, CA3, CA7] La réponse qui vient d'arriver doit-elle être lue sans autre geste ?
 * Oui seulement si le mode vocal et la lecture automatique sont actifs, que la phrase a été
 * DICTÉE, et que la réponse n'est pas un message spontané (veilleur) et porte un échange.
 */
export function lectureAutomatique({ modeVocal, lectureAuto, dictee, spontane = false, echangeId }) {
  return Boolean(modeVocal && lectureAuto && dictee && !spontane && echangeId != null)
}

/**
 * [CA4, CA7] Cette entrée du fil porte-t-elle le ▶ ? Toute réponse de Gaston rattachée à un
 * échange, ancienne comprise ; un message spontané seulement s'il est rattaché à un échange.
 */
export function porteLecture(entree, modeVocal) {
  if (!modeVocal || !entree) return false
  if (entree.role !== 'compagnon' && entree.role !== 'spontane') return false
  return entree.echangeId != null && Boolean(entree.texte)
}

/**
 * [CA4, CA8, CA12] La ligne d'écoute d'une réponse : ▶ « Écouter la réponse », ⏹ « Arrêter la
 * lecture » pendant la lecture, « Annuler la lecture » pendant la préparation ; une note d'échec
 * (« Lecture indisponible pour le moment ») remplace « Écouter » à côté du ▶.
 */
export function boutonLecture(etat, echangeId) {
  const actif = etat.enCours === echangeId
  const enLecture = actif && !etat.chargement
  const chargement = actif && etat.chargement
  const note = actif ? null : (etat.notes?.[echangeId] ?? null)
  return {
    enLecture,
    chargement,
    libelle: enLecture ? LIBELLE_ARRETER : chargement ? LIBELLE_ANNULER : LIBELLE_ECOUTER,
    texte: enLecture ? TEXTE_EN_LECTURE : chargement ? TEXTE_PREPARATION : (note ?? TEXTE_ECOUTER),
    note,
  }
}

/** [CA2] Le statut de l'en-tête : « Parle… » pendant qu'une réponse est lue. */
export const gastonParle = (etat) => etat.enCours != null && !etat.chargement

/** L'état de départ : rien en cours, aucune note. */
export const ETAT_LECTURE_INITIAL = Object.freeze({ enCours: null, chargement: false, notes: {} })

/**
 * [CA4, CA5] « Une lecture à la fois » : l'état après un événement.
 *  - `appui` (▶/⏹ sur `echangeId`) : la même réponse s'arrête ; une autre remplace la première ;
 *  - `auto` (lecture automatique de `echangeId`) : remplace toujours ce qui est en cours ;
 *  - `pret` : le MP3 de `echangeId` est chargé, il joue ;
 *  - `fin` / `arret` : plus rien en cours ;
 *  - `erreur` : plus rien en cours, la note `note` s'affiche sous la réponse `echangeId` (CA8, CA9).
 * Un `pret`, une `fin` ou une `erreur` d'une lecture déjà remplacée ne change rien.
 */
export function lectureSuivante(etat, evenement) {
  const { type, echangeId = null, note = null } = evenement
  const sansNote = (id) => {
    if (id == null || !(id in (etat.notes ?? {}))) return etat.notes ?? {}
    const { [id]: _efface, ...reste } = etat.notes
    return reste
  }
  switch (type) {
    case 'appui':
      if (etat.enCours === echangeId) return { ...etat, enCours: null, chargement: false }
      return { enCours: echangeId, chargement: true, notes: sansNote(echangeId) }
    case 'auto':
      return { enCours: echangeId, chargement: true, notes: sansNote(echangeId) }
    case 'pret':
      return etat.enCours === echangeId ? { ...etat, chargement: false } : etat
    case 'fin':
      return echangeId == null || etat.enCours === echangeId ? { ...etat, enCours: null, chargement: false } : etat
    case 'arret':
      return etat.enCours == null ? etat : { ...etat, enCours: null, chargement: false }
    case 'erreur': {
      if (echangeId != null && etat.enCours != null && etat.enCours !== echangeId) return etat
      return { enCours: null, chargement: false, notes: note ? { ...(etat.notes ?? {}), [echangeId]: note } : (etat.notes ?? {}) }
    }
    default:
      return etat
  }
}

/** [CA8, CA9] Ce que dit un refus de la lecture : la limite du jour, sinon l'indisponibilité. */
export function noteErreurLecture(err) {
  return err?.statut === 429 ? TEXTE_LIMITE_LECTURES : TEXTE_LECTURE_INDISPONIBLE
}

/**
 * [CA6] Les MP3 déjà lus, gardés pour la session : la clé tient la voix, si bien qu'un changement
 * de voix ne relit jamais l'ancien enregistrement. `vider()` libère tout (changement de voix).
 * `liberer` (par défaut `URL.revokeObjectURL`) est injectable pour les tests.
 */
export function creerCacheLectures(liberer = (url) => { try { URL.revokeObjectURL(url) } catch { /* */ } }) {
  const urls = new Map()
  let voix = null
  const cle = (echangeId) => `${voix ?? ''}|${echangeId}`
  return {
    /** Fixe la voix courante ; une voix différente vide le cache (CA6). Rend true si vidé. */
    voix(voixId) {
      if (voixId === voix) return false
      const avaitDesLectures = urls.size > 0
      this.vider()
      voix = voixId
      return avaitDesLectures
    },
    lire: (echangeId) => urls.get(cle(echangeId)) ?? null,
    /** Garde le MP3 ; un MP3 demandé avec une autre voix que la courante est libéré, pas gardé. */
    garder(echangeId, url, voixId = voix) {
      if (voixId !== voix) { liberer(url); return false }
      const ancienne = urls.get(cle(echangeId))
      if (ancienne && ancienne !== url) liberer(ancienne)
      urls.set(cle(echangeId), url)
      return true
    },
    get voixCourante() { return voix },
    vider() { for (const url of urls.values()) liberer(url); urls.clear() },
    get taille() { return urls.size },
  }
}
