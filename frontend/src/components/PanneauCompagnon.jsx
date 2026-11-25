// [US-271] Le chat de Gaston, ouvert depuis n'importe quel écran — d'après la maquette « Compagnon.html ».
//
// Le portail parle au MÊME compagnon que Telegram : la phrase part à `POST /compagnon/messages`
// (US-270), qui la lit par le même orchestrateur que le bot. Ce panneau ne décide de RIEN — il
// envoie, il montre, il clique. Un geste compris revient en carte et se confirme ici ; une commande
// se confirme dans Telegram (la carte le dit) ; en mode Support (le casque de l'en-tête), l'aide de
// l'application répond et rien n'est écrit.
//
// Placement : c'est la PAGE qui décide (voir `App.jsx`) — plein écran au téléphone, panneau droit de
// 400 px sur ordinateur (US-353 / CA12). Ce composant remplit la boîte qu'on lui donne ; `plein` ne
// change que la marge haute et le pied de la maquette mobile. Son contenu vit dans un conteneur
// (`@container/compagnon`), comme la règle de frontend/CLAUDE.md l'exige.
//
// [US-357] L'écran est celui de la maquette « Socle commun » : en-tête clair (visage de 38 px, Gaston
// en Lora), bandeau de contexte, bulle de Gaston sur fond `alt`, bulle du jardinier sur papier crème
// en Kalam (« Dicté · 0:06 » ou « Écrit »), UNE carte « À enregistrer » par tour, rangée de pilules,
// saisie en pilule et micro rond de 54 px. Le moteur et le chemin d'écriture ne changent pas.
import { useState, useEffect, useRef, useCallback } from 'react'
import { Headset, RotateCcw, X, Send, Lock, Loader2, Microscope, Mic, MicOff, Square, AlertTriangle, Info, Play, Pencil } from 'lucide-react'
import { api } from '../lib/api.js'
import useDictee from '../hooks/useDictee.js'
import useLecture, { deverrouillerSon } from '../hooks/useLecture.js'
import {
  ETAT as ETAT_DICTEE, affichageMicro, formaterDuree, EVENEMENT_PREFERENCES_VOIX,
  DUREE_DICTEE_MAX_S_DEFAUT, TEXTE_INDICE_ECOUTE,
  lectureAutomatique, porteLecture, boutonLecture, gastonParle,
} from '../lib/voix.js'
import { VisageGaston } from './Gaston.jsx'
import CarteAEnregistrer from './CarteAEnregistrer.jsx'
import {
  cartesDuTour, confirmerEnSerie, metaBulle, retenirOrigine, origineDesPhrases, TEXTE_PHOTO_BIENTOT,
} from '../lib/carteAEnregistrer.js'
import {
  GASTON, MODE_DEFAUT, ACCUEIL, SUGGESTIONS, PLACEHOLDER, questionDeSuggestion, messageErreur,
  carteDefinitivementFermee, carteFermee, carteApresIssue, filDepuisHistorique, filApresRecommencer,
  ajouterEchange, ajouterErreur, ajouterPhrase, cleDePhrase, remplacerCarte, remplacerLesAnciennes, peutEnvoyer, texteACorriger,
  aEnregistre, LONGUEUR_MAX, fusionnerEtat, INTERVALLE_OUVERT_MS,
  MODE_ANALYSE, TEXTE_ANALYSE_EN_COURS, peutApprofondir, peutApprofondirEntree, analyseBornee,
} from '../lib/compagnon.js'
import { ThumbsUp, ThumbsDown } from 'lucide-react'
import {
  TEXTE_CONTEXTE_INTROUVABLE, barreDeContexte, contexteAEnvoyer, contexteIntrouvable, SUJET,
} from '../lib/contexteCompagnon.js'
import {
  SORTE, TEXTE_RETOUR_PLAN, PLACEHOLDER_QUANTITE, apresConfirmation,
} from '../lib/noter.js'
import { phraseOuverture, suggestionsDe, propositionDeReport } from '../lib/ouvertureGaston.js'  // [US-358]

const ETAGES_AVEC_AVIS = ['savoir', 'raisonnement']

/** Le stockage de l'appareil, ou `null` quand le navigateur le refuse (l'origine d'une phrase est alors « Écrit »). */
const stockageLocal = () => {
  try { return window.localStorage } catch { return null }
}

/** Une bulle de Gaston [US-357 / CA4] : fond `alt`, coin bas-gauche à 5 px, 88 % de large au plus, sans avatar. */
function Bulle({ children, etiquette = null, teinte = '' }) {
  return (
    <div className="max-w-[88%] self-start">
      {etiquette && <div className="mb-1 text-[11.5px] font-semibold text-brand-text">{etiquette}</div>}
      <p className={`whitespace-pre-wrap break-words rounded-[16px] rounded-bl-[5px] bg-card-alt px-3 py-[9px] text-[13.5px] leading-[1.45] text-txt ${teinte}`}>
        {children}
      </p>
    </div>
  )
}

/**
 * [US-304 / CA4, CA8, CA12] La ligne d'écoute sous une réponse (maquette « Compagnon - Voix », §3) :
 * ▶ « Écouter », ⏹ et l'égaliseur pendant la lecture, la roue pendant la préparation ; une lecture
 * impossible le dit à côté du ▶, la réponse écrite restant affichée. Bouton de 30 px, zone tactile
 * de 44 px.
 */
function LigneEcoute({ echangeId, lecture, onEcouter, bloque = false }) {
  const b = boutonLecture(lecture, echangeId)
  return (
    <div className={`-mt-1 flex min-h-[30px] items-center gap-2 pl-0.5 text-[12px] font-semibold ${b.note ? 'text-[var(--gst-alerte-texte)]' : b.enLecture ? 'text-brand-text' : 'text-txt2'}`}>
      <button
        type="button"
        onClick={() => onEcouter(echangeId)}
        disabled={bloque}
        aria-label={b.libelle}
        title={b.libelle}
        className={`relative inline-flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border-[1.5px] after:absolute after:-inset-[7px] after:content-[''] ${b.enLecture
          ? 'border-[var(--brand-deep)] bg-[var(--brand-deep)] text-white dark:text-bg'
          : 'border-brand bg-[var(--gst-bulle)] text-[var(--brand-deep)] hover:bg-brand-soft'} disabled:opacity-40`}
      >
        {b.chargement ? <Loader2 size={13} className="animate-spin" aria-hidden="true" />
          : b.enLecture ? <Square size={11} fill="currentColor" aria-hidden="true" />
            : <Play size={12} fill="currentColor" aria-hidden="true" />}
      </button>
      {b.enLecture && <span className="voix-eq" aria-hidden="true"><i /><i /><i /><i /><i /></span>}
      <span role={b.note ? 'status' : undefined}>{b.texte}</span>
    </div>
  )
}

function Entree({ entree, occupe, onCorriger, onConfirmer, onAbandonner, onAvis, avisDonnes, onApprofondir, modeVocal, lecture, onEcouter, microOuvert }) {
  const { role, texte } = entree

  if (role === 'jardinier') {
    return (
      <div className="flex justify-end">
        {/* [US-357 / CA4] Papier crème, texte en Kalam (la porte est `.note-carnet-texte`), coin bas-droit à 5 px,
            et la méta « Dicté · 0:06 » ou « Écrit ». */}
        <div className="max-w-[88%] rounded-[16px] rounded-br-[5px] border border-paper-bd bg-paper px-3 py-[9px]">
          <span className="mb-0.5 flex items-center gap-1.5 text-[11px] text-txt2">
            {/* [US-302 / CA6] Une phrase dictée porte le micro devant son texte. */}
            {entree.dictee && (
              <Mic size={12} strokeWidth={2.2} role="img" aria-label="Phrase dictée" />
            )}
            {!entree.dictee && <Pencil size={12} strokeWidth={2.2} aria-hidden="true" />}
            {metaBulle({ dictee: Boolean(entree.dictee), dureeS: entree.dureeS })}
          </span>
          <span className="note-carnet-texte block whitespace-pre-wrap break-words !text-[15px]">{texte}</span>
        </div>
      </div>
    )
  }

  if (role === 'erreur') {
    return (
      <div role="alert" className="rounded-[12px] border-[1.5px] border-red bg-red-soft px-3 py-2 text-[12.5px] text-red break-words">
        {texte}
      </div>
    )
  }

  const spontane = role === 'spontane'
  const peutNoter = entree.routageLogId && ETAGES_AVEC_AVIS.includes(entree.etage)
  const cartes = cartesDuTour(entree)
  return (
    <div className="space-y-2">
      {texte && (
        <Bulle
          etiquette={spontane ? `Message de ${GASTON.nom}` : entree.vers === 'analyse' ? (analyseBornee(entree) ? 'Analyse partielle' : 'Analyse approfondie') : null}
          teinte={entree.resume ? 'italic text-txt2' : ''}
        >
          {texte}
        </Bulle>
      )}
      {/* [US-304 / CA4, CA7] ▶ sous chaque réponse rattachée à un échange, historique compris. */}
      {porteLecture(entree, modeVocal) && (
        <LigneEcoute echangeId={entree.echangeId} lecture={lecture} onEcouter={onEcouter} bloque={microOuvert} />
      )}
      {entree.sources?.length > 0 && (
        <p className="text-[12px] text-txt3">Sources : {entree.sources.join(' · ')}</p>
      )}
      {/* [US-342 / CA5] Le lien vers un écran rendu par la boucle à capacités. */}
      {(entree.liens ?? []).map((lien) => (
        <p key={lien.url} className="text-[12.5px]">
          <a href={lien.url} className="font-semibold text-brand-text underline underline-offset-2">{lien.libelle}</a>
        </p>
      ))}
      {peutApprofondirEntree(entree) && (
        <div>
          <button
            type="button"
            disabled={occupe}
            onClick={() => onApprofondir(entree.phrase)}
            className="inline-flex items-center gap-1.5 rounded-full border-[1.5px] border-brand bg-card px-3 py-1.5 text-[12.5px] font-semibold text-brand-text hover:bg-brand-soft disabled:opacity-40"
          >
            <Microscope size={14} aria-hidden="true" />
            Approfondir
          </button>
        </div>
      )}
      {/* [US-357 / CA5] Les propositions d'un même tour : UNE carte, une ligne chacune. */}
      {cartes.length > 0 && (
        <CarteAEnregistrer
          cartes={cartes} occupe={occupe}
          onCorriger={onCorriger} onConfirmer={onConfirmer} onAbandonner={onAbandonner}
        />
      )}
      {peutNoter && (
        <div className="flex items-center gap-1.5 text-[12px] text-txt3">
          <span>Cette réponse vous a aidé ?</span>
          {avisDonnes[entree.routageLogId] ? (
            <span aria-live="polite">Merci.</span>
          ) : (
            <>
              <button type="button" aria-label="Utile" onClick={() => onAvis(entree.routageLogId, 'positif')} className="rounded p-1 hover:bg-brand-soft">
                <ThumbsUp size={14} />
              </button>
              <button type="button" aria-label="Pas utile" onClick={() => onAvis(entree.routageLogId, 'negatif')} className="rounded p-1 hover:bg-brand-soft">
                <ThumbsDown size={14} />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

/** [US-302] Une note de la dictée, au-dessus de la saisie : orange clair = empêchement, bleu = information. */
function NoteDictee({ note }) {
  const alerte = note.ton === 'warn'
  const Icone = alerte ? AlertTriangle : Info
  return (
    <div
      role="status"
      className={`mb-2 flex items-start gap-2 rounded-[12px] border px-2.5 py-2 text-[12.5px] leading-[1.4] ${alerte
        ? 'border-[var(--gst-alerte-bord)] bg-[var(--gst-alerte-fond)] text-[var(--gst-alerte-texte)]'
        : 'border-[var(--gst-info-bord)] bg-[var(--gst-info-fond)] text-[var(--gst-info-texte)]'}`}
    >
      <Icone size={16} className="mt-px shrink-0" aria-hidden="true" />
      <span>{note.texte}</span>
    </div>
  )
}

/**
 * [US-323 / C2, US-357 / CA3] Le bandeau de contexte, sous l'en-tête : « 🫘 Fève · Planche centrale ·
 * rang 6 » sur fond `alt`, et une croix pour le retirer. Sans contexte, il n'est pas affiché.
 */
function BarreContexte({ contexte, sujet, onContexte, plein, occupe }) {
  const barre = barreDeContexte(contexte, sujet)
  if (!barre.retirable) return null
  const cible = plein ? 'min-h-[44px] min-w-[44px]' : 'min-h-[32px] min-w-[32px]'

  return (
    <div className="mx-3.5 mt-2.5 flex items-center gap-2 rounded-[11px] bg-card-alt px-2.5 py-1 text-[12.5px] font-semibold text-txt" aria-label="Contexte de la conversation">
      {barre.emoji && <span className="text-[16px]" aria-hidden="true">{barre.emoji}</span>}
      <span className="min-w-0 flex-1 truncate">{barre.texte}</span>
      <button
        type="button"
        onClick={() => onContexte?.(null)}
        disabled={occupe}
        aria-label="Retirer le contexte"
        title="Retirer le contexte : parler de tout le potager"
        className={`${cible} -mr-1.5 inline-flex shrink-0 items-center justify-center rounded-full text-txt3 hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-40`}
      >
        <X size={14} aria-hidden="true" />
      </button>
    </div>
  )
}

export default function PanneauCompagnon({
  onFermer, onEnregistre, onVu, plein = false, vue = null,
  barreContexte = false, contexte = null, sujet = null, champ = null, onContexte,
  noter = false, onRetourPlan, placement = null,
}) {
  const [mode, setMode] = useState(MODE_DEFAUT)
  const [fil, setFil] = useState([])
  const [texte, setTexte] = useState('')
  const [occupe, setOccupe] = useState(false)
  const [charge, setCharge] = useState(false)
  const [analyse, setAnalyse] = useState(false)
  const [avisDonnes, setAvisDonnes] = useState({})
  const bas = useRef(null)
  const saisie = useRef(null)
  // [US-302 / CA1] Le 🎤 n'existe que si le mode vocal est allumé (réglage « Mon compagnon »).
  const [modeVocal, setModeVocal] = useState(false)
  const [dureeMaxS, setDureeMaxS] = useState(DUREE_DICTEE_MAX_S_DEFAUT)
  // [US-304 / CA2, CA6] La lecture automatique et la voix (dont dépend le cache des MP3).
  const [lectureAuto, setLectureAuto] = useState(true)
  const [voixId, setVoixId] = useState(null)
  const lecture = useLecture({ modeVocal, voixId })

  const support = mode === 'support'
  // [US-324] Ouvert par « Noter » : l'accueil « Je vous écoute… » et les pastilles, jusqu'à la
  // première phrase ; une pastille « Récolte » attend la quantité (`attente`) ; après confirmation,
  // ce qui a changé et « Retour au plan » (`suite`).
  const [noterEnCours, setNoterEnCours] = useState(noter)
  const [attente, setAttente] = useState(null)
  const [suite, setSuite] = useState(null)
  // [US-358 / CA4] « Pas encore » propose le report de l'étape ; il s'écrit au « Confirmer », jamais avant.
  const [report, setReport] = useState(null)
  // [US-358 / CA3] Les messages envoyés depuis l'ouverture : après le premier, Gaston a répondu et un
  // sujet du catalogue propose ses variétés.
  const [envoyesDepuisOuverture, setEnvoyesDepuisOuverture] = useState(0)
  const accueil = charge && fil.length === 0 && !noterEnCours
  // « Noter » retouché alors que le panneau est ouvert : l'accueil et les pastilles reviennent.
  useEffect(() => {
    if (noter) { setNoterEnCours(true); setAttente(null); setSuite(null); setReport(null); setEnvoyesDepuisOuverture(0) }
  }, [noter, contexte, sujet, champ])
  // [US-358 / CA2] Une phrase pré-écrite (« Ajouter le céleri-rave à mon potager ») : dans le champ, pas envoyée.
  useEffect(() => {
    if (!champ?.texte) return
    setTexte(champ.texte)
    saisie.current?.focus?.()
  }, [champ])

  // CA3 : à l'ouverture, ce que le compagnon a dit de lui-même, la conversation récente et les cartes en cours.
  useEffect(() => {
    let vivant = true
    api.historiqueCompagnon()
      // [US-357 / CA4] Les phrases déjà au fil gardent leur origine, dictée ou écrite.
      .then((h) => { if (vivant) { setFil(origineDesPhrases(filDepuisHistorique(h), stockageLocal())); onVu?.(h) } })
      .catch((e) => { if (vivant) setFil((f) => ajouterErreur(f, e)) })
      .finally(() => { if (vivant) setCharge(true) })
    return () => { vivant = false }
  }, [onVu])

  // [US-272 / CA5] Le panneau ouvert se relit à intervalle court, sans WebSocket : une carte confirmée
  // dans Telegram y passe « Confirmé depuis Telegram », une proposition ou un message nouveaux s'ajoutent.
  useEffect(() => {
    if (!charge) return undefined
    let vivant = true
    const relire = () => {
      if (typeof document !== 'undefined' && document.hidden) return
      api.etatCompagnon()
        .then((etat) => { if (vivant) { setFil((f) => fusionnerEtat(f, etat)); onVu?.(etat) } })
        .catch(() => { /* hors ligne un instant : la prochaine relecture rattrapera */ })
    }
    const minuterie = setInterval(relire, INTERVALLE_OUVERT_MS)
    return () => { vivant = false; clearInterval(minuterie) }
  }, [charge, onVu])

  // [US-324] L'accueil de « Noter », ses pastilles et la suite d'une confirmation restent en vue.
  useEffect(() => { bas.current?.scrollIntoView?.({ block: 'end' }) }, [fil, occupe, noterEnCours, suite, contexte])

  // [US-302 / CA1] Le mode vocal, lu à l'ouverture et suivi quand la section « Voix » le change.
  useEffect(() => {
    let vivant = true
    api.preferencesVoix()
      .then((p) => {
        if (!vivant) return
        setModeVocal(Boolean(p?.mode_vocal))
        setLectureAuto(p?.lecture_auto !== false)
        setVoixId(p?.voix_id ?? null)
        if (Number.isFinite(p?.dictee_duree_max_s)) setDureeMaxS(p.dictee_duree_max_s)
      })
      .catch(() => { /* réglages illisibles : clavier seul */ })
    const surChangement = (e) => {
      setModeVocal(Boolean(e.detail?.mode_vocal))
      if (e.detail && 'lecture_auto' in e.detail) setLectureAuto(e.detail.lecture_auto !== false)
      if (e.detail && 'voix_id' in e.detail) setVoixId(e.detail.voix_id ?? null)
    }
    window.addEventListener(EVENEMENT_PREFERENCES_VOIX, surChangement)
    return () => { vivant = false; window.removeEventListener(EVENEMENT_PREFERENCES_VOIX, surChangement) }
  }, [])

  // [US-304 / CA5] Changer de page arrête la lecture (fermer le panneau l'arrête au démontage).
  const arreterLecture = lecture.arreter
  const vuePrecedente = useRef(vue)
  useEffect(() => {
    if (vuePrecedente.current !== vue) arreterLecture()
    vuePrecedente.current = vue
  }, [vue, arreterLecture])

  // Échap referme le chat, comme la croix.
  useEffect(() => {
    const surTouche = (e) => { if (e.key === 'Escape') onFermer?.() }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [onFermer])

  // [US-357 / CA4] La durée de la dernière dictée : « Dicté · 0:06 » sur la bulle de la phrase.
  const derniereDuree = useRef(0)

  const envoyer = useCallback(async (brut, modeForce, dictee = false, raccourciForce = null, carteAPlacer = null, demandeDuPlan = null, echangeRef = null) => {
    const phrase = (brut ?? texte).trim()
    if (!peutEnvoyer(phrase, occupe)) return
    // [US-324 / CA2] La pastille touchée, ou celle qui attend sa quantité (« Récolte » → « 800 g »).
    const raccourci = raccourciForce ?? attente
    setNoterEnCours(false)
    setAttente(null)
    setSuite(null)
    setReport(null)
    setEnvoyesDepuisOuverture((n) => n + 1)
    // La phrase s'affiche tout de suite : la saisie se vide, elle ne doit pas disparaître pendant
    // que Gaston réfléchit. Sa clé la désigne au retour de la réponse, pour ne pas la remettre.
    // [US-302 / CA6, CA9] Une phrase DICTÉE suit le même chemin, mais laisse telle quelle la
    // saisie au clavier en cours.
    const cleJ = cleDePhrase()
    setOccupe(true)
    setAnalyse(modeForce === MODE_ANALYSE)
    if (!dictee) setTexte('')
    const dureeS = dictee ? derniereDuree.current || null : null
    if (dictee) retenirOrigine(stockageLocal(), phrase, { dictee: true, dureeS })
    setFil((f) => ajouterPhrase(f, phrase, cleJ, dictee, dureeS))
    try {
      // [US-323 / C4] Le contexte d'écran part avec la phrase, en identifiants (sans barre : aucun).
      const reponse = await api.messageCompagnon(
        phrase, modeForce ?? mode, barreContexte ? contexteAEnvoyer(contexte) : undefined, raccourci || undefined,
        carteAPlacer || undefined, demandeDuPlan || undefined, echangeRef || undefined,
      )
      setFil((f) => ajouterEchange(remplacerLesAnciennes(f, reponse.propositions), phrase, reponse, cleJ))
      // [US-304 / CA2, CA3] Une phrase DICTÉE, lecture automatique active : la réponse est lue
      // aussitôt (le tap sur 🎤 a déverrouillé le son sur iPhone et iPad). Jamais une phrase tapée.
      if (lectureAutomatique({ modeVocal, lectureAuto, dictee, echangeId: reponse.echange_id })) {
        lecture.lireAutomatiquement(reponse.echange_id)
      }
    } catch (e) {
      // CA4 : réseau coupé, modèle indisponible, lecteur… dit en clair ; la phrase reste à reprendre.
      const erreur = contexteIntrouvable(e) ? new Error(TEXTE_CONTEXTE_INTROUVABLE) : e
      setFil((f) => ajouterErreur(f, erreur, phrase, cleJ))
      if (dictee) setTexte((t) => t || phrase)
      else setTexte(phrase)
    } finally {
      setOccupe(false)
      setAnalyse(false)
      saisie.current?.focus()
    }
  }, [texte, occupe, mode, modeVocal, lectureAuto, lecture.lireAutomatiquement, barreContexte, contexte, attente])

  // [US-328 / CA4] Une carte « À placer » posée sur un rang : la proposition part aussitôt, une
  // fois la conversation chargée (sinon la relecture du fil l'effacerait). Rien n'est écrit :
  // le serveur répond par une carte de plantation à confirmer.
  const placementEnvoye = useRef(null)
  useEffect(() => {
    if (!placement || !charge || placementEnvoye.current === placement.jeton) return
    placementEnvoye.current = placement.jeton
    envoyer(placement.phrase, undefined, false, null, placement.carte, placement.plan)
  }, [placement, charge, envoyer])

  // [US-302 / D4] La phrase transcrite part aussitôt, dans le mode courant du panneau.
  const dictee = useDictee({
    actif: modeVocal,
    dureeMaxS,
    onTexte: (phrase, echangeRef) => envoyer(phrase, undefined, true, null, null, null, echangeRef),
  })
  useEffect(() => { if (dictee.ecouleS > 0) derniereDuree.current = dictee.ecouleS }, [dictee.ecouleS])
  const micro = affichageMicro(dictee.etat, { modeVocal, occupe })
  // [US-304 / CA2, CA5] Le tap sur 🎤 arrête d'abord la lecture en cours (dans `useDictee`), puis
  // déverrouille le son : la réponse à la dictée pourra être lue sans autre geste sur iOS.
  const appuyerDictee = dictee.appuyer
  const appuyerMicro = useCallback(() => {
    appuyerDictee()
    deverrouillerSon()
  }, [appuyerDictee])
  // [US-324 / CA1] Ouvert par « Noter », voix activée : le micro s'ouvre seul — le toucher de
  // « Noter » vaut autorisation. Une seule fois par ouverture.
  const microOuvertSeul = useRef(false)
  useEffect(() => {
    if (!noter || champ || !modeVocal || microOuvertSeul.current || !micro.boutonActif) return
    microOuvertSeul.current = true
    appuyerMicro()
  }, [noter, champ, modeVocal, micro.boutonActif, appuyerMicro])

  // [US-324 / CA2, US-358 / CA3, CA4] Une suggestion : envoyer le raccourci, attendre la quantité, pré-écrire
  // une note, ou proposer le report de l'étape (« Pas encore » — à confirmer, jamais écrit d'emblée).
  const toucherPastille = useCallback((pastille) => {
    if (pastille.sorte === SORTE.ENVOYER) {
      envoyer(pastille.libelle, undefined, false, pastille.raccourci)
      return
    }
    if (pastille.sorte === SORTE.SAISIR) {
      setAttente(pastille.raccourci)
      saisie.current?.focus()
      return
    }
    if (pastille.sorte === SORTE.REDIGER) {
      setTexte(pastille.debut || '')
      saisie.current?.focus()
      return
    }
    const proposition = propositionDeReport(contexte)
    if (!proposition) { onFermer?.(); return }
    setReport(proposition)
  }, [envoyer, contexte, onFermer])

  const confirmerReport = useCallback(async () => {
    if (!report) return
    setOccupe(true)
    try {
      await api.pasEncoreEtape(report.serieId, report.etape)
      setReport(null)
      onEnregistre?.()
      onFermer?.()
    } catch (e) {
      setFil((f) => ajouterErreur(f, e))
    } finally {
      setOccupe(false)
    }
  }, [report, onEnregistre, onFermer])

  const parle = modeVocal && gastonParle(lecture.etat)
  const ecoute = modeVocal && dictee.etat === ETAT_DICTEE.ECOUTE
  const transcription = modeVocal && dictee.etat === ETAT_DICTEE.TRANSCRIPTION

  // [US-273 / CA1] « Approfondir » : la même phrase, lue en profondeur et sans rien écrire.
  const approfondir = useCallback((phrase) => envoyer(phrase, MODE_ANALYSE), [envoyer])

  // [US-357 / CA6] « Corriger » rend la main au champ de saisie, la carte restant visible.
  const corrigerCarte = useCallback((carte) => {
    setMode('normal')
    setTexte(texteACorriger(carte))
    saisie.current?.focus()
  }, [])

  // [US-357 / CA6] « Confirmer » confirme chaque proposition de la carte PAR LE CHEMIN EXISTANT
  // (`POST /compagnon/propositions/{id}/confirmer`), une par une et dans l'ordre. Un échec est dit sur
  // la ligne concernée (la carte reçoit son `erreur`), les lignes déjà confirmées le restent, et la
  // série s'arrête là : rien n'est tenté après la ligne qui a échoué.
  const confirmerCartes = useCallback(async (cartes) => {
    setOccupe(true)
    let derniereIssue = null
    let aEcrit = false
    try {
      const { echec } = await confirmerEnSerie(cartes, (carte) => api.confirmerProposition(carte.id), (carte, issue, erreur) => {
        if (erreur) {
          // Déjà traitée ou disparue : la ligne se ferme avec la raison. Sinon, on peut réessayer.
          setFil((f) => remplacerCarte(
            f, carteDefinitivementFermee(erreur) ? carteFermee(carte, erreur) : { ...carte, erreur: messageErreur(erreur) },
          ))
          return
        }
        setFil((f) => remplacerCarte(f, carteApresIssue(carte, issue)))
        if (aEnregistre(issue)) aEcrit = true
        derniereIssue = issue
      })
      if (aEcrit) onEnregistre?.()
      // [US-324 / CA5] Ce qui a changé sur le plan, et « Retour au plan » quand on venait de « Noter ».
      if (!echec && derniereIssue) setSuite(apresConfirmation(derniereIssue, { noter }))
    } finally {
      setOccupe(false)
    }
  }, [onEnregistre, noter])

  const abandonnerCartes = useCallback(async (cartes) => {
    setOccupe(true)
    try {
      for (const carte of cartes) {
        try {
          const issue = await api.abandonnerProposition(carte.id)
          setFil((f) => remplacerCarte(f, carteApresIssue(carte, issue)))
        } catch (e) {
          setFil((f) => remplacerCarte(
            f, carteDefinitivementFermee(e) ? carteFermee(carte, e) : { ...carte, erreur: messageErreur(e) },
          ))
        }
      }
    } finally {
      setOccupe(false)
    }
  }, [])

  const donnerAvis = useCallback(async (id, avis) => {
    setAvisDonnes((a) => ({ ...a, [id]: true }))
    try { await api.retourReponse(id, avis) } catch { /* un avis déjà donné (409) ou perdu ne gêne personne */ }
  }, [])

  // « Recommencer » : l'écran repart d'un accueil (la mémoire du compagnon, elle, reste la même).
  const recommencer = useCallback(async () => {
    setMode(MODE_DEFAUT)
    setTexte('')
    try {
      setFil(filApresRecommencer(await api.historiqueCompagnon()))
    } catch {
      setFil([])
    }
  }, [])

  const bouton = plein ? 'h-11 w-11' : 'h-9 w-9'
  // [US-357 / CA8] Le micro rond de la maquette : 54 px, en dégradé, sur mobile comme sur ordinateur.
  const tailleRonde = 'h-[54px] w-[54px]'
  const degrade = 'bg-[linear-gradient(145deg,#5E9A2E,#2F5416)] text-white shadow-[0_6px_14px_rgba(47,84,22,.35)]'

  // [US-357 / CA7] La rangée de pilules au-dessus de la saisie : les raccourcis de « Noter » (US-324)
  // tant que la première phrase n'est pas partie, sinon les suggestions de l'accueil. Le contenu
  // selon le contexte vient d'US-358. « Photo · bientôt » est toujours en dernier, désactivée.
  const varietesAProposer = sujet?.type === SUJET.CATALOGUE && !noterEnCours && envoyesDepuisOuverture === 1 && !occupe
  const pastillesDuContexte = report || !barreContexte || !(noterEnCours || varietesAProposer) ? [] : suggestionsDe({
    contexte, sujet, repondu: varietesAProposer,
  })
  const suggestions = pastillesDuContexte.length > 0
    ? pastillesDuContexte.map((pastille) => ({
      cle: pastille.libelle, libelle: pastille.libelle, onClick: () => toucherPastille(pastille),
      appuye: pastille.sorte === SORTE.SAISIR ? attente === pastille.raccourci : undefined,
      actif: Boolean(attente && attente === pastille.raccourci),
    }))
    : accueil
      ? SUGGESTIONS[mode].map((s) => ({ cle: s, libelle: s, onClick: () => envoyer(questionDeSuggestion(s)) }))
      : []

  return (
    <div
      className="@container/compagnon flex h-full w-full flex-col overflow-hidden bg-surface text-txt"
      role="dialog"
      aria-label={`Discuter avec ${GASTON.nom}`}
    >
      {/* [US-357 / CA2] En-tête : visage de 38 px cerclé `brand`, « Gaston » en Lora 17 px, sous-titre en
          `brand-text`, et les boutons ronds (Support, Recommencer, ×). Plus de Kalam ici. */}
      <div className={`flex items-center gap-2.5 border-b border-border px-3.5 pb-3 ${plein ? 'pt-[max(48px,env(safe-area-inset-top))]' : 'pt-3.5'}`}>
        <span className="h-[38px] w-[38px] shrink-0 overflow-hidden rounded-full bg-[var(--gst-visage)] shadow-[0_0_0_2px_var(--brand)]">
          <VisageGaston />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-serif text-[17px] font-semibold leading-tight">{GASTON.nom}</div>
          <div className="flex items-center gap-1.5 truncate text-[12px] font-medium text-brand-text">
            {ecoute ? (
              <><i className="dicte-statut" aria-hidden="true" />Vous écoute…</>
            ) : parle ? (
              /* [US-304 / CA2] Une réponse est lue : « Parle… » (maquette §3). */
              <><i className="h-2 w-2 rounded-full bg-[#7BD87F]" aria-hidden="true" />Parle…</>
            ) : support ? (
              'En ligne · mode Support'
            ) : (
              'connaît votre potager et la météo'
            )}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={() => setMode(support ? 'normal' : 'support')}
            aria-pressed={support}
            aria-label={support ? 'Revenir au mode Normal' : 'Passer en mode Support'}
            title={support ? 'Revenir au mode Normal' : 'Mode Support : l’aide de l’application'}
            className={`${bouton} inline-flex items-center justify-center rounded-full ${support ? 'bg-brand-soft text-brand-text' : 'text-txt2 hover:bg-card-alt'}`}
          >
            <Headset size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={recommencer}
            aria-label="Recommencer"
            title="Recommencer"
            className={`${bouton} inline-flex items-center justify-center rounded-full text-txt2 hover:bg-card-alt`}
          >
            <RotateCcw size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onFermer}
            aria-label="Fermer"
            title="Fermer"
            className={`${bouton} inline-flex items-center justify-center rounded-full text-txt2 hover:bg-card-alt`}
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* [US-323 / C2, C3, C6, US-357 / CA3] Ce que le jardinier a sous les yeux ; absent d'une conversation libre. */}
      {barreContexte && <BarreContexte contexte={contexte} sujet={sujet} onContexte={onContexte} plein={plein} occupe={occupe} />}

      {/* Fil de la conversation */}
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-3.5 py-4" aria-live="polite">
        <div className="mt-auto" />
        {support && (
          <div className="rounded-[12px] border-[1.5px] border-dashed border-brand bg-card px-3 py-2.5 text-[12.5px] text-txt2">
            <b className="font-serif text-[14px] font-semibold text-txt">Mode Support</b><br />
            L’aide de l’application répond ; rien n’est écrit.{' '}
            <button type="button" onClick={() => setMode('normal')} className="font-semibold text-brand-text underline">
              Revenir au mode Normal
            </button>
          </div>
        )}
        {!charge && <p className="text-[12.5px] text-txt3">Je relis notre conversation…</p>}
        {accueil && <Bulle>{ACCUEIL[mode]}</Bulle>}
        {fil.map((entree) => (
          <Entree key={entree.cle} entree={entree} occupe={occupe}
            onCorriger={corrigerCarte} onConfirmer={confirmerCartes} onAbandonner={abandonnerCartes}
            onAvis={donnerAvis} avisDonnes={avisDonnes} onApprofondir={approfondir}
            modeVocal={modeVocal} lecture={lecture.etat} onEcouter={lecture.ecouter}
            microOuvert={ecoute || dictee.etat === ETAT_DICTEE.DEMANDE} />
        ))}
        {noterEnCours && charge && (
          /* [US-324 / temps 2] « Je vous écoute. Dites ce que vous voyez, je le note sur cette culture. » */
          <Bulle>{phraseOuverture({ contexte, sujet, champ: champ?.texte })}</Bulle>
        )}
        {report && (
          /* [US-358 / CA4] « Pas encore » : le report de l'étape se propose, il ne s'écrit qu'au Confirmer. */
          <div className="rounded-[14px] border border-border bg-card px-3.5 py-3 text-[13px] text-txt" role="group" aria-label="Report à confirmer">
            <p>{report.texte}</p>
            <div className="mt-2.5 flex gap-2">
              <button
                type="button" disabled={occupe} onClick={confirmerReport}
                className={`rounded-full bg-brand px-4 text-[13px] font-semibold text-white hover:opacity-95 disabled:opacity-40 dark:text-bg ${plein ? 'min-h-[44px]' : 'py-2'}`}
              >
                Confirmer
              </button>
              <button
                type="button" disabled={occupe} onClick={() => setReport(null)}
                className={`rounded-full border border-border px-4 text-[13px] font-semibold text-txt2 hover:bg-card-alt disabled:opacity-40 ${plein ? 'min-h-[44px]' : 'py-2'}`}
              >
                Annuler
              </button>
            </div>
          </div>
        )}
        {suite && !occupe && (
          /* [US-324 / CA5] « La fève passe à « Levé » sur le plan. » — puis « Retour au plan ». */
          <>
            <Bulle>{suite.texte}</Bulle>
            {suite.retourPlan && (
              <div>
                <button
                  type="button"
                  onClick={() => onRetourPlan?.()}
                  className={`rounded-full bg-brand px-4 text-[13px] font-semibold text-white hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand dark:text-bg ${plein ? 'min-h-[44px]' : 'py-2'}`}
                >
                  {TEXTE_RETOUR_PLAN}
                </button>
              </div>
            )}
          </>
        )}
        {occupe && (
          /* [US-357 / CA9] La réflexion en cours, au nouveau style : une bulle `alt` aux trois points. */
          <div className="flex items-center gap-2" role="status" aria-label={analyse ? TEXTE_ANALYSE_EN_COURS : 'Gaston réfléchit'}>
            <div className="gst-tape flex gap-1 rounded-[16px] rounded-bl-[5px] bg-card-alt p-3.5"><i /><i /><i /></div>
            {analyse && <span className="text-[12.5px] text-txt3">{TEXTE_ANALYSE_EN_COURS}</span>}
          </div>
        )}
        <div ref={bas} />
      </div>

      {/* [US-357 / CA7] Les pilules de 34 px au-dessus de la saisie ; « Photo · bientôt » toujours en dernier. */}
      <div className="flex gap-2 overflow-x-auto px-3.5 pb-2 pt-1" role="group" aria-label="Suggestions">
        {suggestions.map((sg) => (
          <button
            key={sg.cle}
            type="button"
            disabled={occupe}
            onClick={sg.onClick}
            aria-pressed={sg.appuye}
            className={`h-[34px] shrink-0 whitespace-nowrap rounded-full border-[1.5px] border-brand px-3.5 text-[12.5px] font-semibold hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-40 ${sg.actif ? 'bg-brand text-white dark:text-bg' : 'bg-card text-brand-text'}`}
          >
            {sg.libelle}
          </button>
        ))}
        <button
          type="button"
          disabled
          className="h-[34px] shrink-0 whitespace-nowrap rounded-full border-[1.5px] border-border bg-card px-3.5 text-[12.5px] font-semibold text-txt3 opacity-60"
        >
          {TEXTE_PHOTO_BIENTOT}
        </button>
      </div>

      {/* Saisie : champ pilule de 44 px et micro rond de 54 px (CA8) */}
      <div className={`border-t border-border bg-surface px-3.5 pt-2.5 ${plein ? 'pb-[max(14px,env(safe-area-inset-bottom))]' : 'pb-3.5'}`}>
        {modeVocal && dictee.note && <NoteDictee note={dictee.note} />}
        {ecoute ? (
          /* [CA2] Écoute : bandeau orange, durée écoulée sur la durée maximale, niveau animé, ⏹ */
          <div className="flex min-h-[54px] items-center gap-1.5 rounded-full border-[1.5px] border-[var(--gst-rec)] bg-[var(--gst-rec-doux)] py-0.5 pl-3.5 pr-0.5">
            <span className="flex min-w-0 flex-1 items-center gap-[7px] whitespace-nowrap text-[13.5px] font-semibold text-[var(--gst-rec-fonce)]" role="status">
              <i className="dicte-point" aria-hidden="true" />
              Écoute… <b className="tabular-nums">{formaterDuree(dictee.ecouleS)}</b>
              <small className="text-[12px] font-normal">/ {formaterDuree(dureeMaxS)}</small>
            </span>
            <span className="dicte-niveau" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></span>
            <button
              type="button"
              onClick={appuyerMicro}
              aria-label={micro.libelle}
              className={`${tailleRonde} dicte-sonne inline-flex shrink-0 items-center justify-center rounded-full bg-[var(--gst-rec)] text-white`}
            >
              <Square size={14} fill="currentColor" aria-hidden="true" />
            </button>
          </div>
        ) : transcription ? (
          /* [CA4] Transcription : 🎤 et Envoyer inactifs, le micro est déjà libéré */
          <div className="flex min-h-[54px] items-center gap-1.5 rounded-full border-[1.5px] border-border bg-[var(--gst-saisie-occupee)] py-0.5 pl-4 pr-0.5">
            <span className="flex flex-1 items-center gap-2 text-[13.5px] font-semibold text-txt2" role="status">
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              Transcription…
            </span>
            <button type="button" disabled aria-label={micro.libelle}
              className={`${tailleRonde} inline-flex shrink-0 items-center justify-center rounded-full ${degrade} opacity-50`}>
              <Mic size={24} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <form
            className="@container/saisie flex items-center gap-2"
            onSubmit={(e) => { e.preventDefault(); envoyer() }}
          >
            <div className="flex h-11 min-w-0 flex-1 items-center rounded-full border border-border bg-card pl-3.5 pr-1 focus-within:border-brand">
              <label htmlFor="compagnon-saisie" className="sr-only">Votre message à {GASTON.nom}</label>
              <input
                id="compagnon-saisie"
                ref={saisie}
                value={texte}
                onChange={(e) => setTexte(e.target.value)}
                maxLength={LONGUEUR_MAX}
                placeholder={attente ? PLACEHOLDER_QUANTITE : PLACEHOLDER[mode]}
                autoComplete="off"
                className="min-w-0 flex-1 border-0 bg-transparent text-[13.5px] text-txt outline-none placeholder:text-txt3"
              />
              <button
                type="button"
                disabled={!peutApprofondir(texte, occupe)}
                onClick={() => envoyer(undefined, MODE_ANALYSE)}
                aria-label="Approfondir"
                title="Approfondir : une analyse qui croise vos données, sans rien modifier"
                className="inline-flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full text-brand-text hover:bg-brand-soft disabled:opacity-40"
              >
                <Microscope size={17} aria-hidden="true" />
              </button>
            </div>
            {micro.bouton && (
              <button
                type="button"
                onClick={appuyerMicro}
                disabled={!micro.boutonActif}
                aria-label={micro.libelle}
                title="Dicter : touchez, parlez, retouchez pour envoyer"
                className={`${tailleRonde} inline-flex shrink-0 items-center justify-center rounded-full ${degrade} disabled:opacity-50`}
              >
                {dictee.etat === ETAT_DICTEE.DEMANDE
                  ? <Loader2 size={24} className="animate-spin" aria-hidden="true" />
                  : <Mic size={24} aria-hidden="true" />}
              </button>
            )}
            {(!micro.bouton || texte.trim() !== '' || occupe) && (
              <button
                type="submit"
                disabled={!peutEnvoyer(texte, occupe)}
                aria-label="Envoyer"
                className={`${tailleRonde} inline-flex shrink-0 items-center justify-center rounded-full ${degrade} disabled:opacity-40`}
              >
                {occupe ? <Loader2 size={22} className="animate-spin" aria-hidden="true" /> : <Send size={22} fill="currentColor" aria-hidden="true" />}
              </button>
            )}
          </form>
        )}
        {ecoute ? (
          <div className="mt-2 text-center text-[11.5px] font-semibold text-[var(--gst-rec-fonce)]">{TEXTE_INDICE_ECOUTE}</div>
        ) : (
          <>
            {/* [CA8] Micro absent, page hors HTTPS, navigateur sans MediaRecorder : l'explication à la place du 🎤 */}
            {modeVocal && dictee.indisponible && (
              <div className="mt-2 flex items-center justify-center gap-1.5 text-[12px] font-semibold text-txt">
                <MicOff size={15} className="text-txt2" aria-hidden="true" />
                {dictee.indisponible}
              </div>
            )}
            <div className="mt-2 flex items-center justify-center gap-[5px] text-[11px] text-txt3">
              <Lock size={12} className="text-brand" aria-hidden="true" />
              <span>Agent dédié <b className="font-semibold text-brand-text">Les bons gestes</b> · échanges protégés · Version bêta : les conseils peuvent être approximatifs</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
