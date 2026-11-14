// [US-327] Sous-onglet « Vue plan » — le potager vu du dessus, sans photo.
//
// Remplace la Vue plan « rangs et places » d'US-200 / US-228 (CA6) : la maquette « Plan -
// Pistes » (piste C, repli A sans fond) la déclare inadaptée, elle montrait le modèle
// de données au lieu du potager. Les places ne disparaissent pas : elles passent dans
// le suivi d'une culture (US-322, bloc S3).
//
// Une seule lecture, `GET /plan` (CA1) ; tout ce qui se calcule vit dans
// `lib/planDessus.js` (CA2). Le plan n'écrit aucune géométrie ici (US-333), un rang libre ne
// propose aucun geste — il renvoie vers Gaston.
//
// [US-330, US-331] Le plan est aussi l'écran des parcelles : le panneau de droite suit la
// sélection (rien → Aujourd'hui, une parcelle → son détail, une culture → son suivi), la bascule
// « Plan | Liste » rend la même sélection, et l'ancien onglet « Parcelles » n'existe plus.
// L'état exact (parcelle, onglet, mode, culture) survit à un aller-retour (US-195 / CA8).
import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Leaf, MapPin, ChevronLeft } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  formesDuPlan, empriseDuPlan, echelle, roseDesVents, enteteDuPlan, filtresDuPlan,
  parcellesAPlacer, tuilesParZones, modeDuPlan, selectionDeSegment,
  MODE_PLAN, MODE_ZONES, MODE_VIDE, FILTRE_TOUT, MESSAGE_RANG_LIBRE,
} from '../lib/planDessus.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useNavigation, useIntention, useEtatEcran } from '../context/NavigationContext.jsx'
import { useMedia } from '../hooks/useMedia.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import SuiviCulture from '../components/SuiviCulture.jsx'
import { ParcellePlan, RoseDesVents, EchellePlan } from '../components/PlanDessin.jsx'
import { LegendeEtapes, LegendeRepliable, Modal } from '../components/ui'
import { publierSelection, ouvrirGastonPourPlacer, ouvrirGastonAvec, ouvrirGastonPourPlan } from '../lib/contexteCompagnon.js'  // [US-325, US-328, US-330]
import { tachesDuPlan, meteoDuJour, propositionDePlacement, annonceCarteEnMain } from '../lib/aujourdhui.js'  // [US-328]
import { parcellesDuChemin, estCheminMobile } from '../lib/planMobile.js'  // [US-329]
import AujourdhuiPotager from '../components/AujourdhuiPotager.jsx'
import PlanMobile from '../components/PlanMobile.jsx'
import DetailParcelle, { ListeParcelles } from '../components/DetailParcelle.jsx'  // [US-330]
import { peutEnregistrer } from '../lib/gestes.js'
import EditeurPlan from '../components/EditeurPlan.jsx'  // [US-333]
import { peutModifierLePlan } from '../lib/editeurPlan.js'  // [US-333 / CA7]
import { encartMiseEnPlace, estPremiereOuverture, TEXTE_SUR_ORDINATEUR } from '../lib/miseEnPlace.js'  // [US-334]
import { RelectureAuRetourProvider } from '../hooks/useRelectureAuRetour.jsx'  // [US-196 / CA12]
import {
  AFFICHAGES, AFFICHAGE_PLAN, AFFICHAGE_LISTE, ONGLET_EN_PLACE, ONGLET_LOTS,
  parcelleParId, parcellesDeListe, annonceParcelle, TEXTE_PARCELLE_INTROUVABLE, ONGLET_CARACTERISTIQUES,
} from '../lib/parcelleDansPlan.js'  // [US-330]

/** [P8] Les filtres : quatre boutons à bascule, compteurs du serveur (CA4). */
function FiltresPlan({ filtres, actif, onChange }) {
  return (
    <div role="group" aria-label="Filtrer le plan"
      className="flex flex-wrap gap-[3px] rounded-[10px] bg-card-alt p-[3px]">
      {filtres.map((f) => (
        <button key={f.cle} type="button" aria-pressed={actif === f.cle ? 'true' : 'false'}
          aria-label={f.nomAccessible} onClick={() => onChange(f.cle)}
          className={`min-h-[34px] rounded-lg px-[11px] text-[12.5px] font-semibold whitespace-nowrap
            focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand
            ${actif === f.cle ? 'bg-card text-txt shadow-sm' : 'text-txt2 hover:text-txt'}`}>
          {f.texte}
        </button>
      ))}
    </div>
  )
}

/** [US-330 / CA4] La bascule « Plan | Liste » : le même écran, la même sélection. */
function BasculeAffichage({ actif, onChange }) {
  return (
    <div role="group" aria-label="Affichage" className="flex gap-[3px] rounded-[10px] bg-card-alt p-[3px]">
      {AFFICHAGES.map((a) => (
        <button key={a.id} type="button" aria-pressed={actif === a.id ? 'true' : 'false'} onClick={() => onChange(a.id)}
          className={`min-h-[34px] rounded-lg px-[11px] text-[12.5px] font-semibold whitespace-nowrap
            focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand
            ${actif === a.id ? 'bg-card text-txt shadow-sm' : 'text-txt2 hover:text-txt'}`}>
          {a.label}
        </button>
      ))}
    </div>
  )
}

/**
 * [P10] Les PARCELLES sans position sur le plan (≠ les cultures « À placer » d'US-328) : le plan
 * ne leur invente aucune place.
 */
function ParcellesSansPosition({ aPlacer }) {
  if (!aPlacer.length) return null
  return (
    <div className="flex flex-col gap-3 text-[13px] text-txt2">
      {aPlacer.length > 0 && (
        <section aria-label="Parcelles sans position" className="mt-1">
          <h4 className="text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2 mb-2">
            Parcelles sans position · {aPlacer.length}
          </h4>
          <ul className="flex flex-col gap-1.5">
            {aPlacer.map((p) => (
              <li key={p.id} className="flex items-center gap-2 rounded-[10px] border border-dashed border-border px-3 py-2 text-txt">
                <MapPin size={14} aria-hidden="true" className="text-txt3" />{p.nom}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[12px] text-txt3">Une parcelle sans position n’est pas dessinée : le plan ne lui invente aucune place.</p>
        </section>
      )}
    </div>
  )
}

/**
 * [US-334 / M1, M2] L'encart « Mettre en place le plan » (aucune parcelle posée) ou « N parcelles à placer »
 * (quelques-unes). Il ne mémorise rien : il disparaît quand tout est posé et revient dès qu'une parcelle ne l'est plus (M5).
 * Sans éditeur — téléphone, lecteur — il dit ce qu'il faut faire au lieu d'offrir un bouton qui ne mène nulle part.
 */
function EncartMiseEnPlace({ encart, onOuvrir, peutEditer, peutEcrire }) {
  if (!encart) return null
  return (
    <section aria-label={encart.titre} data-encart-mise-en-place={encart.type}
      className="@container flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand bg-brand-soft/40 px-4 py-3">
      <div className="min-w-0 flex-1 basis-[260px]">
        <h3 className="font-serif text-[15px] font-semibold text-txt">
          {encart.titre}{encart.duree ? <span className="font-sans text-[12.5px] font-normal text-txt2"> · {encart.duree}</span> : null}
        </h3>
        <p className="mt-0.5 text-[12.5px] text-txt2">{encart.texte}</p>
        {!peutEditer && peutEcrire && <p className="mt-1 text-[12.5px] font-semibold text-txt">{TEXTE_SUR_ORDINATEUR}</p>}
      </div>
      {peutEditer && (
        <button type="button" onClick={onOuvrir}
          className="min-h-[36px] rounded-[10px] bg-brand px-3.5 text-[12.5px] font-semibold text-white hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
          {encart.libelleBouton}
        </button>
      )}
    </section>
  )
}

export default function PlanDessus({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const { aller, annoncer, signaler } = useNavigation()
  const role = potagerActif?.role
  const ordinateur = useMedia('(min-width: 1024px)')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filtre, setFiltre] = useState(FILTRE_TOUT)
  // [US-330 / CA6, US-195 / CA8] L'état exact de l'écran : la parcelle ouverte, son onglet, le mode
  // Plan ou Liste, la culture choisie. Tenu par la coquille, rendu tel quel au retour.
  const intention = useIntention('plan-vue', (recue) => {
    if (recue.parcelle) {
      setEtat({ parcelle: recue.parcelle, culture: null })
      setFeuilleParcelle(true)
    }
    // [US-334 / M3] « Mettre en place le plan maintenant », en sortie de l'assistant « Premier potager ».
    if (recue.editeur) setOuvrirApresChargement(true)
  })
  const [etat, setEtat] = useEtatEcran('plan-vue',
    { parcelle: null, onglet: ONGLET_EN_PLACE, affichage: AFFICHAGE_PLAN, culture: null }, intention)
  const choix = etat.culture
  const setChoix = useCallback((c) => setEtat({ culture: c }), [setEtat])
  const [feuilleParcelle, setFeuilleParcelle] = useState(Boolean(etat.parcelle))
  // [US-333] L'éditeur du plan : un mode de l'écran, jamais mémorisé (on ne rouvre pas un brouillon).
  const [edition, setEdition] = useState({ ouverte: false, parcelle: null, guide: false })
  const [ouvrirApresChargement, setOuvrirApresChargement] = useState(false)
  const ancreDetail = useRef(null)
  // [US-325 / CA3] Mobile : fermer la feuille du suivi garde la culture choisie — elle reste
  // marquée sur le plan et en pastille sur « Noter » de la barre basse, que la feuille recouvre.
  const [feuille, setFeuille] = useState(false)
  const [message, setMessage] = useState('')
  const cadre = useRef(null)
  // [US-322 / CA1] Le segment qui a ouvert le suivi reprend le focus à sa fermeture.
  const declencheur = useRef(null)
  const [largeurCadre, setLargeurCadre] = useState(0)
  // [US-329 / CA1] La largeur du CONTENEUR de l'écran (container query), jamais celle de l'écran.
  const racine = useRef(null)
  const [largeurRacine, setLargeurRacine] = useState(0)
  // [US-328 / CA6] La météo des prévisions existantes ; absente, la ligne disparaît sans erreur.
  const [meteo, setMeteo] = useState(null)
  // [US-328 / CA4] La carte « À placer » prise au clavier, ou en cours de glisser.
  const [carteEnMain, setCarteEnMain] = useState(null)
  const [carteGlissee, setCarteGlissee] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // [CA1] UNE lecture : tout le dessin en sort.
      setData(await api.plan(dateRef, potagerId))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [dateRef, potagerId])

  useEffect(() => { load() }, [load, refresh])
  useEffect(() => {
    let actif = true
    api.meteo().then((m) => { if (actif) setMeteo(m) }).catch(() => { if (actif) setMeteo(null) })
    return () => { actif = false }
  }, [potagerId])
  // [US-328 / CA4] Échap repose la carte en main.
  useEffect(() => {
    if (!carteEnMain) return undefined
    const surTouche = (e) => { if (e.key === 'Escape') { setCarteEnMain(null); annoncer('Carte reposée') } }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [carteEnMain, annoncer])
  // Changer de date ou de potager efface la sélection — mais pas au montage, qui rend l'état exact.
  const cleContexte = useRef(`${dateRef}|${potagerId}`)
  useEffect(() => {
    const cle = `${dateRef}|${potagerId}`
    if (cleContexte.current === cle) return   // robuste au double montage du mode strict
    cleContexte.current = cle
    setEtat({ culture: null, parcelle: null })
  }, [dateRef, potagerId]) // eslint-disable-line react-hooks/exhaustive-deps
  // [US-325 / CA3] La sélection courante devient le contexte du bouton « Noter » de la barre basse ;
  // quitter le plan l'efface. [US-330] Une parcelle ouverte sans culture est le contexte « cette parcelle ».
  const parcelleOuverte = useMemo(() => parcelleParId(data, etat.parcelle), [data, etat.parcelle])
  useEffect(() => {
    publierSelection(choix ?? (parcelleOuverte ? { parcelleId: parcelleOuverte.id, parcelle: parcelleOuverte.nom } : null))
  }, [choix, parcelleOuverte])
  useEffect(() => () => publierSelection(null), [])
  // [US-330 / CA5] Un lien vers une parcelle qui n'existe plus : on le dit, jamais une erreur.
  useEffect(() => {
    if (!data || etat.parcelle == null || parcelleOuverte) return
    setEtat({ parcelle: null })
    // [US-332 / R5] Une parcelle devenue inactive reste sur le plan, grisée : ce n'est pas une parcelle disparue.
    const inactive = (data.parcelles_inactives || []).find((p) => p.id === etat.parcelle)
    signaler(inactive ? `${inactive.nom} est inactive : elle reste sur le plan, grisée, avec son historique.` : TEXTE_PARCELLE_INTROUVABLE)
  }, [data, etat.parcelle, parcelleOuverte]) // eslint-disable-line react-hooks/exhaustive-deps
  // [US-330 / CA2] Une intention qui désigne une parcelle existante : annoncée, focus sur son détail.
  useEffect(() => {
    if (!intention?.parcelle || !parcelleOuverte) return
    annoncer(annonceParcelle(parcelleOuverte))
    ancreDetail.current?.focus?.()
  }, [intention, parcelleOuverte?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  /** [US-230 / CA9] La nouvelle valeur est posée dans l'état déjà chargé, le serveur recalcule le reste. */
  const majParcelle = (maj) => {
    setData((d) => (d ? {
      ...d,
      parcelles: d.parcelles.map((p) => (p.id === maj.id ? {
        ...p, ...maj, disposition: { ...p.disposition, rangs_declares: maj.nb_rangs },
      } : p)),
    } : d))
    load()
  }

  // [CA5] L'échelle suit la largeur du cadre ; sous le plancher, le plan défile dedans.
  useEffect(() => {
    const el = cadre.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const obs = new ResizeObserver(([e]) => setLargeurCadre(Math.floor(e.contentRect.width)))
    obs.observe(el)
    return () => obs.disconnect()
  }, [data, edition.ouverte])
  useEffect(() => {
    const el = racine.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const obs = new ResizeObserver(([e]) => setLargeurRacine(Math.floor(e.contentRect.width)))
    obs.observe(el)
    return () => obs.disconnect()
  }, [data, loading, error, edition.ouverte])

  const formes = useMemo(() => formesDuPlan(data), [data])
  const emprise = useMemo(() => empriseDuPlan(data, formes), [data, formes])
  const u = echelle(emprise, largeurCadre)
  const mode = modeDuPlan(data)
  const entete = enteteDuPlan(data, emprise)
  const filtres = useMemo(() => filtresDuPlan(data), [data])
  const rose = roseDesVents(data)
  const aPlacer = useMemo(() => parcellesAPlacer(data), [data])
  const angle = Number(data?.potager_geometrie?.angle_deg) || 0
  const taches = useMemo(() => tachesDuPlan(data), [data])
  const chemin = useMemo(() => parcellesDuChemin(data), [data])
  const liste = useMemo(() => parcellesDeListe(data), [data])
  const meteoJour = meteoDuJour(meteo)
  // [US-329 / CA1] Sous 720 px de conteneur : le chemin mobile. Avant la première mesure, la
  // largeur de la fenêtre en tient lieu (pas de clignotement sur téléphone).
  const mobile = estCheminMobile(largeurRacine || (typeof window !== 'undefined' ? window.innerWidth : 0))
  const panneauDroit = ordinateur && !mobile
  // [US-333 / CA7, E7] L'éditeur : un membre éditeur, sur un conteneur de 720 px et plus.
  const peutEditer = !mobile && peutModifierLePlan(role, largeurRacine || (typeof window !== 'undefined' ? window.innerWidth : 0))

  const encart = useMemo(() => encartMiseEnPlace(data), [data])
  // [US-334 / M3] L'intention `editeur` attend le plan : ouvre l'éditeur s'il est possible ici, sinon l'encart parle.
  useEffect(() => {
    if (!ouvrirApresChargement || !data || !potagerActif) return   // le rôle n'est connu qu'avec le potager actif
    setOuvrirApresChargement(false)
    if (peutEditer) setEdition({ ouverte: true, parcelle: null, guide: estPremiereOuverture(data) })
  }, [ouvrirApresChargement, data, potagerActif, peutEditer])

  if (loading && !data) return <LoadingSkeleton lines={5} />
  if (error) return <ApiError message={error} onRetry={load} />

  const ouvrirSegment = (forme, segment) => {
    const s = selectionDeSegment(forme, segment)
    declencheur.current = typeof document !== 'undefined' ? document.activeElement : null
    setChoix(s)
    setFeuille(true)
    setMessage('')
  }
  // [US-330 / CA2] Le nom d'une parcelle, « Voir la parcelle » ou « Détail » : son détail, D1 à D6.
  const ouvrirParcelle = (forme) => {
    declencheur.current = typeof document !== 'undefined' ? document.activeElement : null
    setEtat({ parcelle: forme.id, culture: null })
    setFeuilleParcelle(true)
    setMessage('')
    const p = parcelleParId(data, forme.id)
    if (p) annoncer(annonceParcelle(p))
  }
  const fermerParcelle = () => {
    setEtat({ parcelle: null })
    setFeuilleParcelle(false)
    const el = declencheur.current
    if (el?.isConnected) requestAnimationFrame(() => el.focus?.())
  }
  // « ‹ Planche centrale » : de la culture à sa parcelle.
  const retourParcelle = () => {
    if (choix) setEtat({ parcelle: choix.parcelleId, culture: null })
    setFeuille(false)
  }
  // [US-334 / M4] Le potager encore vierge : l'éditeur déroule l'assistant de première mise en place.
  const ouvrirEditeur = (parcelle = null) => { setEdition({ ouverte: true, parcelle, guide: estPremiereOuverture(data) }); setMessage('') }
  const fermerEditeur = () => setEdition({ ouverte: false, parcelle: null, guide: false })
  const rangLibre = () => { setMessage(MESSAGE_RANG_LIBRE); annoncer(MESSAGE_RANG_LIBRE) }
  // [US-328 / A2, A3] Une ligne de tâche ouvre le suivi de sa culture (US-322).
  const ouvrirLigne = (selection) => {
    declencheur.current = typeof document !== 'undefined' ? document.activeElement : null
    setChoix(selection)
    setFeuille(true)
    setMessage('')
  }
  // [US-328 / CA4] Prendre une carte au clavier (ou la reposer), l'annoncer.
  const prendre = (carte) => {
    setCarteEnMain(carte)
    annoncer(carte ? annonceCarteEnMain(carte) : 'Carte reposée')
  }
  // [US-328 / CA4, CA5] Déposer la carte sur un rang libre : Gaston propose, rien n'est écrit.
  const deposer = (forme, segment) => {
    const carte = carteEnMain || carteGlissee
    if (!carte) return
    setCarteEnMain(null)
    setCarteGlissee(null)
    setMessage('')
    ouvrirGastonPourPlacer(propositionDePlacement(carte.carte, forme, segment))
  }
  const ouvrirLot = (lot) => aller('pepiniere', lot.intention)
  const fermer = () => {
    if (panneauDroit) setChoix(null)
    setFeuille(false)
    const el = declencheur.current
    if (el?.isConnected) requestAnimationFrame(() => el.focus?.())
  }

  const handlers = {
    onSegment: ouvrirSegment, onParcelle: ouvrirParcelle, onRangLibre: rangLibre, onLot: ouvrirLot,
    onDeposer: deposer, accueillant: Boolean(carteEnMain || carteGlissee),
  }

  const suivi = choix && (
    <SuiviCulture
      key={`${choix.parcelleId}|${choix.culture}|${choix.variete || ''}`}
      selection={choix} dateRef={dateRef} potagerId={potagerId} role={role}
      compact={!panneauDroit}
      onClose={fermer}
      onParcelle={() => { retourParcelle(); setFeuilleParcelle(true) }}
      onLot={(numero) => aller('pepiniere', { onglet: 'parcours', lot: String(numero) })}
    />
  )

  const entreeChemin = parcelleOuverte ? chemin.find((c) => c.id === parcelleOuverte.id) : null
  // [US-196 / CA12] Un geste lancé depuis la carte du sol relit le plan UNE FOIS au retour sur l'onglet.
  const detail = parcelleOuverte && (
    <RelectureAuRetourProvider relire={load}>
    <DetailParcelle
      key={parcelleOuverte.id} ancre={ancreDetail} parcelle={parcelleOuverte} entree={entreeChemin}
      onglet={parcelleOuverte.est_pepiniere && etat.onglet === ONGLET_EN_PLACE ? ONGLET_LOTS : etat.onglet}
      onOnglet={(o) => setEtat({ onglet: o })}
      dateRef={data?.date_ref_effective} vocabulaires={data?.vocabulaires} gestesSol={data?.gestes_sol}
      lectureSeule={!peutEnregistrer(role)} ordinateur={panneauDroit}
      onFermer={fermerParcelle}
      onCulture={ouvrirLigne}
      onVoirCulture={(culture) => aller('cultures', { culture })}
      onLot={ouvrirLot}
      onPepiniere={() => aller('pepiniere')}
      onJournalSol={() => aller('journal', { parcelle: parcelleOuverte.nom, gestes: (data?.gestes_sol ?? []).join(',') })}
      onNoter={() => ouvrirGastonAvec({ parcelleId: parcelleOuverte.id, parcelle: parcelleOuverte.nom })}
      onAjuster={peutEditer ? () => ouvrirEditeur(parcelleOuverte.id) : undefined}
      onRetirer={() => ouvrirGastonPourPlan({
        phrase: `Rendre inactive ou supprimer ${parcelleOuverte.nom}`,
        contexte: { parcelleId: parcelleOuverte.id, parcelle: parcelleOuverte.nom },
        plan: { action: 'retirer', parcelle_id: parcelleOuverte.id },
      })}
      onParcelleMaj={majParcelle}
    />
    </RelectureAuRetourProvider>
  )

  if (mode === MODE_VIDE) {
    // [CA7] Aucune parcelle : l'invitation à mettre en place le plan (US-334).
    return (
      <div className="flex flex-col items-center gap-3 mt-12 text-center text-txt2">
        <Leaf size={36} className="text-txt3" aria-hidden="true" />
        <p className="text-base text-txt">Votre potager n’a encore aucune parcelle.</p>
        <p className="max-w-[44ch] text-[13px]">Pour mettre en place le plan, dites à Gaston : « crée une planche de 4 mètres sur 1,20 ».</p>
      </div>
    )
  }

  const feuilleSuivi = choix && feuille && (
    <Modal title={`Suivi · ${choix.culture}`} onClose={fermer} disposition="basse" entete={false}
      bodyClassName="p-4 overflow-y-auto min-h-0">
      {suivi}
    </Modal>
  )
  // [US-330] Mobile et écrans moyens : le détail d'une parcelle en feuille plein écran ; la culture
  // s'ouvre par-dessus (la feuille du suivi vient après dans le DOM).
  const feuilleDetail = !panneauDroit && detail && feuilleParcelle && (
    <Modal title={parcelleOuverte.nom} onClose={fermerParcelle} disposition="plein_mobile" entete={false}
      bodyClassName="p-4 overflow-y-auto min-h-0">
      {detail}
    </Modal>
  )
  const panneauAujourdhui = (
    <AujourdhuiPotager taches={taches} meteo={meteoJour} dateRef={data?.date_ref_effective}
      carteEnMain={carteEnMain} onOuvrir={ouvrirLigne} onPrendre={prendre}
      onGlisser={setCarteGlissee} onLacher={() => setCarteGlissee(null)} />
  )

  if (mobile) {
    // [US-329] Un seul écran : mini-plan, légende, tâches, puis le chemin.
    return (
      <div ref={racine} className="@container min-w-0 flex flex-col gap-3">
        <EncartMiseEnPlace encart={encart} peutEditer={false} peutEcrire={peutEnregistrer(role)} />
        <PlanMobile entete={entete} formes={mode === MODE_PLAN ? formes : []} emprise={emprise} angle={angle}
          chemin={chemin} taches={taches} largeur={largeurRacine || 343}
          onOuvrir={ouvrirLigne}
          onDetail={(p) => ouvrirParcelle({ id: p.id, nom: p.nom })}
          onLot={(lot) => aller('pepiniere', lot.intention)}
          onPepiniere={() => aller('pepiniere')}
          annoncer={annoncer} />
        {feuilleDetail}
        {feuilleSuivi}
      </div>
    )
  }

  if (edition.ouverte && peutEditer) {
    // [US-333] « Modifier le plan » prend tout l'écran ; Gaston reste ouvrable pour les formes nouvelles.
    return (
      <div ref={racine} className="@container min-w-0">
        <EditeurPlan plan={data} emprise={emprise} selectionInitiale={edition.parcelle} guide={edition.guide}
          annoncer={annoncer}
          onQuitter={fermerEditeur}
          onEnregistre={() => { fermerEditeur(); load(); setMessage('Plan enregistré.') }}
          onCaracteristiques={(id) => { fermerEditeur(); setEtat({ parcelle: id, culture: null, onglet: ONGLET_CARACTERISTIQUES }); setFeuilleParcelle(true) }} />
      </div>
    )
  }

  return (
    <div ref={racine} className="@container flex flex-col gap-3 lg:flex-row lg:items-start lg:gap-0">
      <div className="flex-1 min-w-0 flex flex-col gap-3 lg:pr-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-serif text-[18px] font-semibold text-txt">
              {mode === MODE_ZONES ? 'Plan par zones' : entete.titre}
            </h2>
            <p className="text-[12.5px] text-txt2 mt-0.5">
              {mode === MODE_ZONES
                ? 'Aucune parcelle n’est encore placée : chacune en tuile, dans l’ordre du chemin'
                : [entete.fond, entete.dimension].filter(Boolean).join(' · ')}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {peutEditer && (
              <button type="button" onClick={() => ouvrirEditeur(null)}
                className="min-h-[34px] rounded-[10px] border border-border bg-card px-3 text-[12.5px] font-semibold text-txt hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
                Modifier le plan
              </button>
            )}
            <BasculeAffichage actif={etat.affichage} onChange={(a) => setEtat({ affichage: a })} />
            {etat.affichage === AFFICHAGE_PLAN && <FiltresPlan filtres={filtres} actif={filtre} onChange={setFiltre} />}
          </div>
        </div>

        <EncartMiseEnPlace encart={encart} peutEditer={peutEditer} peutEcrire={peutEnregistrer(role)}
          onOuvrir={() => ouvrirEditeur(null)} />

        <div ref={cadre} className="min-w-0">
          {etat.affichage === AFFICHAGE_LISTE ? (
            // [US-330 / CA4] La liste : toutes les parcelles, posées ou non — même sélection que le plan.
            <ListeParcelles parcelles={liste} choisie={etat.parcelle}
              onChoisir={(id) => ouvrirParcelle({ id })} />
          ) : mode === MODE_PLAN ? (
            // [CA5] Le plan défile dans son cadre, jamais la page.
            <div className="overflow-auto rounded-xl" tabIndex={-1}>
              <div className="plan-cadre plan-grille relative rounded-xl"
                style={{ width: emprise.longueur * u, height: emprise.largeur * u, backgroundSize: `${u}px ${u}px` }}>
                <div className="absolute inset-0" style={angle ? { transform: `rotate(${angle}deg)` } : undefined}>
                  {formes.map((forme) => (
                    <ParcellePlan key={`${forme.actif ? 'a' : 'i'}-${forme.id}`} forme={forme} u={u} filtre={filtre}
                      choix={choix} parcelleChoisie={etat.parcelle} {...handlers} />
                  ))}
                </div>
                <RoseDesVents rose={rose} />
                <EchellePlan u={u} />
              </div>
            </div>
          ) : (
            // [P10] Le plan par zones : une tuile par parcelle, dans l'ordre du chemin.
            <div className="plan-cadre rounded-xl p-5 pt-6 flex flex-wrap gap-x-4 gap-y-6 items-start">
              {tuilesParZones(data).map((t) => (
                <ParcellePlan key={t.id} forme={t} u={u} filtre={filtre} choix={choix} parcelleChoisie={etat.parcelle} positionnee={false}
                  largeurPx={t.largeurPx} hauteurPx={t.hauteurPx} {...handlers} />
              ))}
            </div>
          )}
        </div>

        {message && (
          <p role="status" className="rounded-[10px] border border-border bg-card px-3 py-2 text-[12.5px] text-txt2">{message}</p>
        )}
        {!rose && mode === MODE_PLAN && (
          <p className="text-[12px] text-txt3">Le nord du potager n’est pas encore posé : la rose des vents s’affichera dès qu’il le sera.</p>
        )}
        {/* [P9] La légende des étapes (US-321), sous le plan. */}
        <LegendeRepliable className="mt-1"><LegendeEtapes /></LegendeRepliable>
      </div>

      {/* [CA5] Ordinateur : le panneau de droite. Mobile : le suivi en feuille basse. */}
      {panneauDroit ? (
        <aside aria-label={choix ? 'Suivi de la culture' : parcelleOuverte ? 'Détail de la parcelle' : 'Aujourd’hui au potager'}
          className="w-[360px] shrink-0 self-stretch border-l border-border bg-card px-5 py-[18px] rounded-r-xl">
          {suivi ? (
            <>
              {/* [US-330] Le retour vers la parcelle d'où l'on vient. */}
              <button type="button" onClick={retourParcelle}
                className="mb-2 inline-flex min-h-[44px] items-center gap-1 rounded-lg text-[13px] font-semibold text-brand-text hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
                <ChevronLeft size={15} aria-hidden="true" />{choix.parcelle}
              </button>
              {suivi}
            </>
          ) : detail || (
            <div className="flex flex-col gap-5">
              {panneauAujourdhui}
              <ParcellesSansPosition aPlacer={mode === MODE_ZONES ? [] : aPlacer} />
            </div>
          )}
        </aside>
      ) : (
        <>
          {/* Conteneur de 720 px et plus, écran sous l'ordinateur : le panneau sous le plan. */}
          <section aria-label="Aujourd’hui au potager"
            className="flex flex-col gap-5 rounded-xl border border-border bg-card px-4 py-4">
            {panneauAujourdhui}
            <ParcellesSansPosition aPlacer={mode === MODE_ZONES ? [] : aPlacer} />
          </section>
          {feuilleDetail}
          {feuilleSuivi}
        </>
      )}
    </div>
  )
}
