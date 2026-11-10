// [US-302] « Appuyer pour parler » : le micro, l'enregistrement et sa transcription.
//
// Toute décision vit dans `lib/voix.js` (états, format, messages), testée par `node --test` ; ce
// hook ne fait que brancher `getUserMedia` et `MediaRecorder` sur ces décisions :
//   appui → arrêt des lectures en cours (CA10) → demande du micro (CA2) → écoute, durée écoulée
//   → second appui ou durée maximale (CA3) → micro libéré (CA4) → transcription → `onTexte(phrase)`.
// Le micro est libéré dès l'arrêt, au démontage du panneau et à toute erreur : le voyant
// d'enregistrement du système ne reste jamais allumé.
import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../lib/api.js'
import {
  ETAT, etatSuivant, capaciteDictee, choisirTypeMime, extensionDictee, dureeAtteinte,
  issueErreurMicro, noteErreurTranscription, issueTranscription, arreterLectures,
  DUREE_DICTEE_MAX_S_DEFAUT, TEXTE_DUREE_MAX,
} from '../lib/voix.js'

const PAS_MS = 250

export default function useDictee({ actif, dureeMaxS = DUREE_DICTEE_MAX_S_DEFAUT, onTexte }) {
  const [etat, setEtat] = useState(ETAT.PRET)
  const [ecouleS, setEcouleS] = useState(0)
  const [note, setNote] = useState(null)               // { ton: 'info' | 'warn', texte }
  const [indisponible, setIndisponible] = useState(null) // texte qui remplace le 🎤 (CA8)

  const etatRef = useRef(ETAT.PRET)
  const flux = useRef(null)
  const enregistreur = useRef(null)
  const morceaux = useRef([])
  const debut = useRef(0)
  const minuterie = useRef(null)
  const vivant = useRef(true)
  const onTexteRef = useRef(onTexte)
  onTexteRef.current = onTexte

  const passer = useCallback((evenement) => {
    const suivant = etatSuivant(etatRef.current, evenement)
    etatRef.current = suivant
    if (vivant.current) setEtat(suivant)
    return suivant
  }, [])

  // [CA4] Libère le micro : chaque piste arrêtée, le voyant du système s'éteint.
  const libererMicro = useCallback(() => {
    clearInterval(minuterie.current)
    minuterie.current = null
    flux.current?.getTracks?.().forEach((piste) => { try { piste.stop() } catch { /* déjà arrêtée */ } })
    flux.current = null
  }, [])

  // [CA8] Navigateur sans MediaRecorder, page hors HTTPS : explication à la place du 🎤.
  useEffect(() => {
    if (!actif) return
    const capacite = capaciteDictee()
    if (!capacite.possible) {
      setIndisponible(capacite.message)
      etatRef.current = ETAT.INDISPONIBLE
      setEtat(ETAT.INDISPONIBLE)
    }
  }, [actif])

  useEffect(() => {
    vivant.current = true
    return () => {
      vivant.current = false
      try { if (enregistreur.current?.state === 'recording') enregistreur.current.stop() } catch { /* */ }
      libererMicro()
    }
  }, [libererMicro])

  const transcrire = useCallback(async (blob, typeMime, dureeS) => {
    try {
      const { texte } = await api.transcrireDictee(blob, `dictee.${extensionDictee(typeMime)}`, dureeS)
      const issue = issueTranscription(texte)
      passer('transcrit')
      if (!vivant.current) return
      if (issue.envoyer) onTexteRef.current?.(issue.phrase)
      else setNote(issue.note)
    } catch (e) {
      passer('echec')
      if (vivant.current) setNote(noteErreurTranscription(e))
    }
  }, [passer])

  const arreter = useCallback((motif) => {
    const rec = enregistreur.current
    if (etatRef.current !== ETAT.ECOUTE || !rec) return
    passer(motif === 'duree_max' ? 'duree_max' : 'appui')
    if (motif === 'duree_max') setNote({ ton: 'info', texte: TEXTE_DUREE_MAX })
    clearInterval(minuterie.current)
    try { rec.stop() } catch { libererMicro(); passer('echec') }
  }, [passer, libererMicro])

  const demarrer = useCallback(async () => {
    if (etatRef.current !== ETAT.PRET) return
    // [CA10] Une réponse en cours de lecture se tait AVANT que le micro s'ouvre.
    arreterLectures()
    setNote(null)
    passer('appui')
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      const issue = issueErreurMicro(e)
      passer(issue.evenement)
      if (issue.indisponible) setIndisponible(issue.indisponible)
      if (issue.note) setNote(issue.note)
      return
    }
    if (!vivant.current) { stream.getTracks().forEach((p) => p.stop()); return }
    flux.current = stream
    const typeMime = choisirTypeMime(window.MediaRecorder)
    let rec
    try {
      rec = typeMime ? new MediaRecorder(stream, { mimeType: typeMime }) : new MediaRecorder(stream)
    } catch {
      libererMicro()
      passer('micro_refuse')
      setIndisponible(null)
      setNote(issueErreurMicro(null).note)
      return
    }
    enregistreur.current = rec
    morceaux.current = []
    rec.ondataavailable = (ev) => { if (ev.data?.size) morceaux.current.push(ev.data) }
    rec.onstop = () => {
      const dureeS = (Date.now() - debut.current) / 1000
      libererMicro()
      const type = rec.mimeType || typeMime || 'audio/webm'
      const blob = new Blob(morceaux.current, { type })
      morceaux.current = []
      enregistreur.current = null
      if (etatRef.current === ETAT.TRANSCRIPTION) transcrire(blob, type, dureeS)
    }
    debut.current = Date.now()
    setEcouleS(0)
    rec.start()
    passer('micro_accorde')
    // [CA2, CA3] Durée écoulée affichée, arrêt seul à la durée maximale.
    minuterie.current = setInterval(() => {
      const s = (Date.now() - debut.current) / 1000
      if (vivant.current) setEcouleS(s)
      if (dureeAtteinte(s, dureeMaxS)) arreter('duree_max')
    }, PAS_MS)
  }, [passer, libererMicro, transcrire, arreter, dureeMaxS])

  const appuyer = useCallback(() => {
    if (etatRef.current === ETAT.ECOUTE) arreter('appui')
    else if (etatRef.current === ETAT.PRET) demarrer()
  }, [arreter, demarrer])

  return { etat, ecouleS, note, indisponible, appuyer, effacerNote: () => setNote(null) }
}
