// [US-304] Écouter la réponse de Gaston — le haut-parleur, branché sur les décisions de `lib/voix.js`.
//
// Toute règle vit dans `lib/voix.js` (lecture automatique, une lecture à la fois, cache, messages),
// testée par `node --test` ; ce hook ne fait que brancher l'élément <audio> sur ces décisions :
//   ▶ (ou réponse à une dictée) → arrêt de la lecture en cours (CA5) → MP3 du cache ou du serveur
//   (CA6) → lecture → ⏹ ou fin → rien en cours.
//
// iPhone et iPad (CA2, CA11) : Safari ne joue un son sans geste que sur un élément <audio> déjà
// joué DANS un geste. D'où UN SEUL élément pour toute la page, déverrouillé par un silence au tap
// sur 🎤 (`deverrouillerSon`) ou sur ▶ : la réponse qui arrive après la dictée y est jouée ensuite.
import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../lib/api.js'
import {
  ETAT_LECTURE_INITIAL, lectureSuivante, noteErreurLecture, creerCacheLectures, inscrireLecture,
  SILENCE_WAV, TEXTE_LECTURE_INDISPONIBLE,
} from '../lib/voix.js'

// [CA6] Le cache vit le temps de la page (la session), pas celui du panneau : rouvrir Gaston et
// réécouter une réponse ne refait pas d'appel.
const cache = creerCacheLectures()
let lecteur = null

function element() {
  if (!lecteur && typeof Audio !== 'undefined') lecteur = new Audio()
  return lecteur
}

/** [CA2] À appeler DANS le geste (tap sur 🎤 ou ▶), après l'arrêt des lectures en cours. */
export function deverrouillerSon() {
  const a = element()
  if (!a) return
  a.onended = null
  a.onerror = null
  try {
    a.src = SILENCE_WAV
    const p = a.play()
    if (p?.catch) p.catch(() => { /* pas de son : ce n'est pas une erreur (CA11) */ })
  } catch { /* navigateur sans audio */ }
}

export default function useLecture({ modeVocal, voixId }) {
  const [etat, setEtat] = useState(ETAT_LECTURE_INITIAL)
  const etatRef = useRef(ETAT_LECTURE_INITIAL)
  const vivant = useRef(true)
  const jeton = useRef(0)
  const desinscrire = useRef(null)
  const voixRef = useRef(voixId)
  voixRef.current = voixId

  const passer = useCallback((evenement) => {
    const suivant = lectureSuivante(etatRef.current, evenement)
    etatRef.current = suivant
    if (vivant.current) setEtat(suivant)
    return suivant
  }, [])

  // Coupe le son et oublie la lecture en cours (sans toucher à l'état affiché).
  const couper = useCallback(() => {
    jeton.current += 1
    const a = lecteur
    if (a) {
      a.onended = null
      a.onerror = null
      try { a.pause() } catch { /* déjà arrêté */ }
    }
    desinscrire.current?.()
    desinscrire.current = null
  }, [])

  const arreter = useCallback(() => {
    couper()
    passer({ type: 'arret' })
  }, [couper, passer])

  // [CA6] Changer de voix invalide le cache : l'ancienne voix ne se réentend plus.
  useEffect(() => { cache.voix(voixId ?? null) }, [voixId])

  const jouer = useCallback(async (echangeId, type) => {
    couper()
    const suivant = passer({ type, echangeId })
    if (suivant.enCours !== echangeId) return          // second appui sur ⏹ : arrêt
    if (type === 'appui') deverrouillerSon()             // dans le geste (iOS)
    const monJeton = jeton.current
    // [CA5] Inscrite dès maintenant : le 🎤 arrête aussi une lecture encore en chargement.
    desinscrire.current = inscrireLecture(() => { couper(); passer({ type: 'arret' }) })
    const finir = (evenement) => {
      if (jeton.current !== monJeton) return
      desinscrire.current?.()
      desinscrire.current = null
      passer(evenement)
    }

    const voix = voixRef.current ?? null
    cache.voix(voix)
    let url = cache.lire(echangeId)
    try {
      if (!url) {
        url = await api.lectureVoix(echangeId)
        // [CA6] Même interrompue, une lecture chargée est gardée : la réécouter ne coûte rien.
        if (!cache.garder(echangeId, url, voix)) url = null
        if (jeton.current !== monJeton) return
        if (!url) { finir({ type: 'arret' }); return }
      }
      const a = element()
      if (!a) { finir({ type: 'erreur', echangeId, note: TEXTE_LECTURE_INDISPONIBLE }); return }
      a.onended = () => finir({ type: 'fin', echangeId })
      a.onerror = () => finir({ type: 'erreur', echangeId, note: TEXTE_LECTURE_INDISPONIBLE })
      a.src = url
      passer({ type: 'pret', echangeId })
      await a.play()
    } catch (e) {
      if (jeton.current !== monJeton) return
      // [CA11] Lecture automatique refusée par le navigateur (aucun geste) : pas d'erreur montrée,
      // le ▶ reste là pour écouter.
      if (e?.name === 'NotAllowedError' || e?.name === 'AbortError') finir({ type: 'arret' })
      else finir({ type: 'erreur', echangeId, note: noteErreurLecture(e) })
    }
  }, [couper, passer])

  const ecouter = useCallback((echangeId) => jouer(echangeId, 'appui'), [jouer])
  const lireAutomatiquement = useCallback((echangeId) => jouer(echangeId, 'auto'), [jouer])

  // [CA5] Mode vocal éteint, panneau fermé : la lecture s'arrête.
  useEffect(() => { if (!modeVocal) arreter() }, [modeVocal, arreter])
  useEffect(() => {
    vivant.current = true
    return () => { vivant.current = false; couper() }
  }, [couper])

  return { etat, ecouter, lireAutomatiquement, arreter }
}
