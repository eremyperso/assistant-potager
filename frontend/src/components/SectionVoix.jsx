// [US-301] Section « Voix » de la fenêtre « Mon compagnon » — d'après la maquette
// « Compagnon - Voix » (§1 Réglages), projet Claude Design.
//
// Le mode vocal est ÉTEINT par défaut : sans lui, ni micro ni lecture n'apparaissent dans le
// panneau. Allumé, la section liste les voix françaises du catalogue (US-300) en vrais boutons
// radio, laisse écouter un extrait de chacune (▶ devient ⏹, un seul à la fois) et choisir celle de
// Gaston. Chaque changement est enregistré aussitôt, « Enregistré » à droite du titre pendant 2 s ;
// une erreur réseau le dit et remet l'état précédent (CA5).
//
// Le contenu suit la largeur de la fenêtre (container query du parent `@container/compagnon`) :
// cibles tactiles à 44 px dans une fenêtre étroite (plein écran mobile), 40 px au-delà.
import { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Square, Check, AlertTriangle, Info } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  REGLAGES_PAR_DEFAUT, capaciteDictee, voixAffichees, sectionVisible, appliquerChangement,
  issueEnregistrement, extraitSuivant, texteEmpechementDictee, TEXTE_EXTRAIT_INDISPONIBLE,
  TEXTE_MODE_VOCAL_ETEINT, SILENCE_WAV, DUREE_RETOUR_MS, EVENEMENT_PREFERENCES_VOIX,
} from '../lib/voix.js'

const TAILLE_CIBLE = 'w-11 h-11 @[420px]/compagnon:w-10 @[420px]/compagnon:h-10'

function Interrupteur({ actif, onChange, libelle, aide, disabled }) {
  return (
    <div className="flex items-center gap-3.5 py-3">
      <div className="flex-1 min-w-0">
        <b className="block text-[14.5px] text-txt">{libelle}</b>
        {aide && <small className="block text-[12.5px] text-txt2 mt-0.5">{aide}</small>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={actif}
        aria-label={libelle}
        disabled={disabled}
        onClick={() => onChange(!actif)}
        className={`relative shrink-0 w-[50px] h-[30px] rounded-full transition-colors disabled:opacity-60 ${
          actif ? 'bg-brand' : 'bg-[#7D8873]'}`}
      >
        <span className={`absolute top-[3px] w-6 h-6 rounded-full bg-white shadow transition-[left] ${
          actif ? 'left-[23px]' : 'left-[3px]'}`} />
      </button>
    </div>
  )
}

function Egaliseur() {
  return (
    <span className="voix-eq" aria-hidden="true"><i /><i /><i /><i /><i /></span>
  )
}

function Encadre({ ton, icone: Icone, children }) {
  const teintes = ton === 'info' ? 'bg-blue-soft text-blue' : 'bg-amber-soft text-amber'
  return (
    <div role="status" className={`flex items-start gap-2 rounded-xl px-2.5 py-2 text-[12.5px] leading-snug ${teintes}`}>
      <Icone size={16} className="shrink-0 mt-px" aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export default function SectionVoix() {
  const [reglages, setReglages] = useState(null)
  const [catalogue, setCatalogue] = useState(null)
  const [retour, setRetour] = useState(null)       // { message, erreur }
  const [occupe, setOccupe] = useState(false)
  const [extraitEnCours, setExtraitEnCours] = useState(null)
  const [extraitErreur, setExtraitErreur] = useState(null)
  const audioRef = useRef(null)
  const minuteurRetour = useRef(null)
  const capacite = capaciteDictee()

  useEffect(() => {
    api.preferencesVoix().then(setReglages).catch(() => setReglages({ ...REGLAGES_PAR_DEFAUT }))
    return () => clearTimeout(minuteurRetour.current)
  }, [])

  // Le catalogue n'est lu qu'une fois le mode vocal allumé (CA2) ; la liste de secours est
  // affichée comme les autres, sans alerte (CA7).
  const modeVocal = Boolean(reglages?.mode_vocal)
  useEffect(() => {
    if (!modeVocal || catalogue) return
    api.catalogueVoix().then(setCatalogue).catch(() => setCatalogue({ voix: [], liste_de_secours: true }))
  }, [modeVocal, catalogue])

  const arreterExtrait = useCallback(() => {
    const audio = audioRef.current
    if (audio) {
      audio.pause()
      if (audio.dataset.url) URL.revokeObjectURL(audio.dataset.url)
      audioRef.current = null
    }
    setExtraitEnCours(null)
  }, [])

  useEffect(() => arreterExtrait, [arreterExtrait])

  function afficherRetour(message, erreur) {
    clearTimeout(minuteurRetour.current)
    setRetour({ message, erreur })
    minuteurRetour.current = setTimeout(() => setRetour(null), DUREE_RETOUR_MS)
  }

  async function changer(changement) {
    if (occupe) return
    const precedents = reglages
    setOccupe(true)
    setRetour(null)
    setReglages(appliquerChangement(reglages, changement))
    if (changement.mode_vocal === false) arreterExtrait()
    try {
      const serveur = await api.enregistrerPreferencesVoix(changement)
      const issue = issueEnregistrement(true, precedents, serveur)
      setReglages(issue.reglages)
      afficherRetour(issue.message, false)
      // [US-302 / CA1] Le panneau du compagnon, s'il est ouvert, montre ou retire le 🎤 aussitôt.
      window.dispatchEvent(new CustomEvent(EVENEMENT_PREFERENCES_VOIX, { detail: issue.reglages }))
    } catch {
      const issue = issueEnregistrement(false, precedents)
      setReglages(issue.reglages)
      afficherRetour(issue.message, true)
    } finally {
      setOccupe(false)
    }
  }

  // Le tap sur ▶ suffit à autoriser le son sur iPhone/iPad : l'élément <audio> est créé et
  // `play()` appelé dans le même geste, avant tout `await` long (CA3).
  async function jouer(voixId) {
    const demande = extraitSuivant(extraitEnCours, voixId)
    arreterExtrait()
    setExtraitErreur(null)
    if (demande === null) return
    const audio = new Audio(SILENCE_WAV)
    audio.play().catch(() => {})   // dans le geste : déverrouille le son sur iOS
    audioRef.current = audio
    setExtraitEnCours(demande)
    try {
      const url = await api.extraitVoix(demande)
      if (audioRef.current !== audio) { URL.revokeObjectURL(url); return }
      audio.dataset.url = url
      audio.src = url
      // La fin ne s'écoute qu'une fois l'extrait réel en place : le silence de déverrouillage
      // (0,1 s) se termine bien avant l'arrivée du réseau et arrêterait tout.
      audio.addEventListener('ended', () => { if (audioRef.current === audio) arreterExtrait() })
      await audio.play()
    } catch {
      if (audioRef.current === audio) arreterExtrait()
      setExtraitErreur(TEXTE_EXTRAIT_INDISPONIBLE)
    }
  }

  const visible = reglages ? sectionVisible(reglages, capacite) : null
  const voix = voixAffichees(catalogue, reglages?.voix_id)

  return (
    <section aria-label="Voix">
      <div className="flex items-center gap-2 min-h-6">
        <h3 className="font-serif text-[18px] font-bold text-txt">Voix</h3>
        {retour && (
          <span role="status"
            className={`ml-auto flex items-center gap-1 text-[12.5px] font-semibold ${
              retour.erreur ? 'text-amber' : 'text-brand-text'}`}>
            {retour.erreur ? <AlertTriangle size={15} aria-hidden="true" /> : <Check size={15} aria-hidden="true" />}
            {retour.message}
          </span>
        )}
      </div>

      {!reglages ? (
        <div className="text-[13px] text-txt3 py-3">Chargement…</div>
      ) : (
        <>
          <Interrupteur
            actif={reglages.mode_vocal}
            libelle="Mode vocal"
            aide="Micro et lecture des réponses de Gaston."
            disabled={occupe}
            onChange={(v) => changer({ mode_vocal: v })}
          />

          {!visible.listeDesVoix ? (
            <p className="text-[13px] text-txt2 bg-card-alt rounded-xl px-3 py-2.5">{TEXTE_MODE_VOCAL_ETEINT}</p>
          ) : (
            <>
              {visible.avertissementDictee && (
                <div className="mb-2">
                  <Encadre ton="info" icone={Info}>{texteEmpechementDictee(visible.avertissementDictee)}</Encadre>
                </div>
              )}

              <fieldset className="border-0 m-0 mt-1 mb-0.5 p-0 min-w-0">
                <legend className="text-[11.5px] font-bold tracking-wider uppercase text-txt2 mb-2">Voix de Gaston</legend>
                {!catalogue ? (
                  <div className="text-[13px] text-txt3">Chargement des voix…</div>
                ) : (
                  <div className="border border-border rounded-[14px] overflow-hidden">
                    {voix.map((v, i) => {
                      const enLecture = extraitEnCours === v.id
                      return (
                        <div key={v.id}
                          className={`flex items-center gap-2.5 pl-3.5 pr-2 min-h-[56px] ${
                            i > 0 ? 'border-t border-border' : ''} ${v.cochee ? 'bg-brand-soft' : ''}`}>
                          <label className="flex flex-1 min-w-0 items-center gap-3 min-h-[56px] cursor-pointer">
                            <input
                              type="radio"
                              name="voix-gaston"
                              value={v.id}
                              checked={v.cochee}
                              disabled={occupe}
                              onChange={() => changer({ voix_id: v.id })}
                              className="w-5 h-5 shrink-0 accent-brand"
                            />
                            <span className="text-[15px] font-semibold text-txt truncate">{v.nom}</span>
                            {v.par_defaut && (
                              <span className="text-[11.5px] text-txt2 bg-card border border-border rounded-full px-2 py-px whitespace-nowrap">
                                par défaut
                              </span>
                            )}
                          </label>
                          {enLecture && <Egaliseur />}
                          <button
                            type="button"
                            onClick={() => jouer(v.id)}
                            aria-label={enLecture ? 'Arrêter l’extrait' : `Écouter l’extrait de ${v.nom}`}
                            className={`shrink-0 inline-flex items-center justify-center rounded-full border-[1.5px] ${TAILLE_CIBLE} ${
                              enLecture
                                ? 'bg-brand-deep border-brand-deep text-white dark:text-bg'
                                : 'bg-card border-brand text-brand-deep hover:bg-brand-soft'}`}
                          >
                            {enLecture ? <Square size={13} fill="currentColor" aria-hidden="true" /> : <Play size={13} fill="currentColor" aria-hidden="true" />}
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
                {extraitErreur && <p role="status" className="text-[12.5px] text-txt2 mt-1.5">{extraitErreur}</p>}
              </fieldset>

              <Interrupteur
                actif={reglages.lecture_auto}
                libelle="Lire les réponses après une dictée"
                aide="Les phrases tapées ne sont jamais lues automatiquement."
                disabled={occupe}
                onChange={(v) => changer({ lecture_auto: v })}
              />
            </>
          )}
        </>
      )}
    </section>
  )
}
