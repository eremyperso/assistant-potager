// [US-061] Écran Pépinière — portage de `ScreenPep` (`web-screens.jsx`, maquette
// 2026) sur les données réelles par lot de semis exposées par `GET /pepiniere/lots`
// (US-065). La mise en forme suit la maquette ; les fonctions qu'elle ne connaît
// pas (date de référence, panneau de traçabilité, états de germination) sont
// conservées et logées dans ses composants plutôt que réinventées.
import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Sprout, CalendarDays, Map as IconeCarte } from 'lucide-react'
import { Lot as IconeDuLot } from '../components/ui/IconeLot.jsx'
import { api } from '../lib/api.js'
import { etatDuLot } from '../lib/ficheLot.js'
import { tauxTint, libelleNumeroLot, lireNumeroLot, messageLotInconnu } from '../lib/pepiniere.js'
import { fragmentsDuLot } from '../lib/parcours.js'   // [US-218]
import {
  ongletPepiniere, ongletDeLIntention, ongletsPepiniere, CONTEXTE_ONGLET, alertesDesLots, nbASemer,
  motDuParcours, motDeSemer, motDesLots, emplacementDuLot, statutPepiniere,
} from '../lib/pepiniereSocle.js'   // [US-356]
import { filtreInitial } from '../lib/lotsJournal.js'
import { ouvrirGastonSur } from '../lib/contexteCompagnon.js'
import { sujetLot } from '../lib/ouvertureGaston.js'  // [US-358]
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useIntention, useEtatEcran, useNavigation } from '../context/NavigationContext.jsx'
import { useCoquille, useDeclarerEcran, HotePanneau } from '../context/CoquilleContext.jsx'   // [US-353, US-356]
import { useMedia } from '../hooks/useMedia.js'
import { peutEnregistrer } from '../lib/gestes.js'
import FicheLot, { FicheLotInconnu } from '../components/FicheLot.jsx'   // [US-216]
import FicheLotCommune from '../components/FicheLotCommune.jsx'   // [US-356 / CA11]
import FicheCulture from '../components/FicheCulture.jsx'
import OngletParcours from '../components/OngletParcours.jsx'   // [US-218, US-356]
import OngletSemer from '../components/OngletSemer.jsx'   // [US-356]
import OngletLots from '../components/OngletLots.jsx'   // [US-242, US-356]
import { RelectureAuRetourProvider } from '../hooks/useRelectureAuRetour.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import {
  Badge, Modal,
} from '../components/ui'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(dateStr) {
  if (!dateStr) return '—'
  const [y, m, d] = dateStr.split('-')
  return `${d}/${m}/${y}`
}

const pluriel = (n, mot, suffixe = 's') => `${n} ${mot}${n > 1 ? suffixe : ''}`

// ── Panneau de détail : cycle de vie du lot ───────────────────────────────────

function TimelineRow({ icon, tint, isLast, children }) {
  const PASTILLE = {
    brand: 'bg-brand-soft', amber: 'bg-amber-soft', red: 'bg-red-soft', neutre: 'bg-border',
  }
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-base shrink-0 ${PASTILLE[tint]}`}>
          {icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-border mt-1 min-h-6" />}
      </div>
      <div className="pb-4 flex-1 min-w-0">{children}</div>
    </div>
  )
}

function buildRows(detail, lot) {
  const rows = []
  if (detail.semis.length > 0) detail.semis.forEach(s => rows.push({ type: 'semis', data: s }))
  else rows.push({ type: 'semis_absent' })
  // [US-212] Les comptages de levée suivent le semis, avant le repiquage.
  ;(detail.levees ?? []).forEach(l => rows.push({ type: 'levee', data: l }))

  detail.godets.forEach((g, i) => rows.push({ type: 'godet', data: g, idx: i, total: detail.godets.length }))
  if (detail.taux_germination != null) rows.push({ type: 'taux', val: detail.taux_germination })

  if (detail.plantations.length > 0) detail.plantations.forEach(p => rows.push({ type: 'plantation', data: p }))
  else rows.push({ type: 'plantation_absent' })

  // [US-211 / CA8] Les déplacements du lot, à leur date, avec origine et destination.
  ;(detail.deplacements ?? []).forEach(d => rows.push({ type: 'deplacement', data: d }))
  ;(detail.ventes ?? []).forEach(v => rows.push({ type: 'vente', data: v }))
  ;(detail.pertes_godet ?? []).forEach(p => rows.push({ type: 'perte_godet', data: p }))
  // [US-216] La clôture ferme le fil : plus rien ne se passe sur le lot après elle.
  ;(detail.clotures ?? []).forEach(c => rows.push({ type: 'cloture', data: c }))
  // [US-216 / CA13] Un lot terminé (tout mis en terre, vendu ou perdu) n'a pas
  // d'événement propre : c'est un état. Le fil le dit en dernière ligne, à la date
  // du dernier geste — la même que la fiche (« Lot terminé le 17 octobre »).
  if (lot && etatDuLot(lot) === 'termine') rows.push({ type: 'termine', data: { date: lot.date_dernier_geste } })
  return rows
}

function DetailModal({ lot, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // [CA10] Le détail est ciblé sur le lot de la carte ouverte, pas sur l'agrégat
  // culture + variété.
  useEffect(() => {
    setLoading(true); setError(null)
    api.godetsDetail(lot.culture, lot.variete, {
      semisId: lot.semis_id,
      sansSemisRattache: lot.sans_semis_rattache,
    })
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [lot.lot_id])

  const base = lot.variete ? `${lot.culture} · ${lot.variete}` : lot.culture
  const titre = libelleNumeroLot(lot) ? `${libelleNumeroLot(lot)} · ${base}` : base   // [US-209 / CA10]
  const sousTitre = lot.sans_semis_rattache
    ? 'Cycle de vie — godets sans semis rattaché'
    : `Cycle de vie — semis du ${fmt(lot.date_semis)}`

  return (
    <Modal title={titre} sub={sousTitre} icon={Sprout} onClose={onClose} width={520}>
      {loading && <LoadingSkeleton lines={3} />}
      {error && <p className="text-sm text-red">{error}</p>}
      {detail && (
        <div>
          {buildRows(detail, lot).map((row, i, tous) => {
            const isLast = i === tous.length - 1

            if (row.type === 'semis') return (
              <TimelineRow key={`semis-${row.data.id}`} icon="🌱" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Semis <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  {row.data.nb_graines} {row.data.unite || 'graines'}
                  {row.data.parcelle && <span className="text-brand-text"> · {row.data.parcelle}</span>}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'semis_absent') return (
              <TimelineRow key="semis-absent" icon="🌱" tint="neutre" isLast={isLast}>
                <p className="text-sm italic text-txt3">Semis non lié</p>
              </TimelineRow>
            )

            if (row.type === 'godet') return (
              <TimelineRow key={`godet-${row.data.id}`} icon="🪴" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Lot godet <span className="font-normal text-txt3">#{row.data.id}</span>
                  {row.total > 1 && <span className="ml-1 text-[12px] text-txt3">· {row.idx + 1}/{row.total}</span>}
                </p>
                <p className="text-sm text-txt3">
                  {pluriel(row.data.nb_plants, 'plant')}
                  {row.data.nb_graines_lot != null && <span> sur {row.data.nb_graines_lot} graines</span>}
                  <span className="text-brand-text"> · {row.data.parcelle ?? 'emplacement non précisé'}</span>
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'taux') return (
              <div key="taux" className="mb-3 rounded-xl px-3 py-2.5 flex items-center justify-between bg-card-alt">
                <span className="text-sm text-txt3">Taux de germination</span>
                <Badge tint={tauxTint(row.val)}>{row.val} %</Badge>
              </div>
            )

            if (row.type === 'plantation') return (
              <TimelineRow key={`plant-${row.data.id}`} icon="🌿" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Plantation <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  {pluriel(row.data.quantite, 'plant')}
                  {row.data.parcelle && (
                    <span> → <span className="font-medium capitalize text-txt">{row.data.parcelle}</span></span>
                  )}
                </p>
                {row.data.source_godet_ids.length > 0 && (
                  <p className="text-[12px] mt-0.5 text-txt3">Lots : #{row.data.source_godet_ids.join(', #')}</p>
                )}
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'plantation_absent') return (
              <TimelineRow key="plant-absent" icon="🌿" tint="neutre" isLast={isLast}>
                <p className="text-sm italic text-txt3">Pas encore planté</p>
              </TimelineRow>
            )

            if (row.type === 'deplacement') return (
              <TimelineRow key={`deplacement-${row.data.id}`} icon="🚚" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  {/* [US-241 / CA11] Un déplacement chiffré dit combien de godets sont partis. */}
                  {row.data.quantite != null
                    ? `${row.data.quantite} godet${row.data.quantite > 1 ? 's' : ''} déplacé${row.data.quantite > 1 ? 's' : ''}`
                    : 'Déplacement'}{' '}
                  <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  <span>{row.data.origine ?? 'emplacement non renseigné'}</span>
                  {' → '}
                  <span className="font-medium text-txt">{row.data.destination ?? '—'}</span>
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'vente') return (
              <TimelineRow key={`vente-${row.data.id}`} icon="🏷️" tint="amber" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Vente <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  {pluriel(row.data.quantite, 'pied')} vendu{row.data.quantite > 1 ? 's' : ''}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'perte_godet') return (
              <TimelineRow key={`perte-${row.data.id}`} icon="💀" tint="red" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Perte pépinière <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-red">
                  {pluriel(row.data.quantite, 'plant')} perdu{row.data.quantite > 1 ? 's' : ''}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'levee') return (
              <TimelineRow key={`levee-${row.data.id}`} icon="🌾" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Levée <span className="font-normal text-txt3">#{row.data.id}</span>
                  {row.data.terminee && <span className="ml-1.5 text-[12px] font-medium text-brand-text">· terminée</span>}
                </p>
                <p className="text-sm text-txt3">
                  {row.data.nb_leves} levé{row.data.nb_leves > 1 ? 's' : ''}
                  {row.data.sur != null && <span> sur {row.data.sur}</span>}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'termine') return (
              <TimelineRow key="termine" icon="✅" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">Lot terminé</p>
                <p className="text-sm text-txt3">Tout est mis en terre, vendu ou perdu.</p>
                {row.data.date && <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>}
              </TimelineRow>
            )

            if (row.type === 'cloture') {
              const soldes = [
                row.data.godets_soldes > 0 && pluriel(row.data.godets_soldes, 'godet'),
                row.data.graines_soldees > 0 && `${pluriel(row.data.graines_soldees, 'graine')} non levée${row.data.graines_soldees > 1 ? 's' : ''}`,
              ].filter(Boolean)
              return (
                <TimelineRow key={`cloture-${row.data.id}`} icon="🔒" tint="neutre" isLast={isLast}>
                  <p className="text-sm font-semibold text-txt">
                    Clôture du lot <span className="font-normal text-txt3">#{row.data.id}</span>
                  </p>
                  <p className="text-sm text-txt3">
                    {soldes.length ? `Soldé : ${soldes.join(' et ')}` : 'Lot soldé'}
                  </p>
                  <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
                </TimelineRow>
              )
            }

            return null
          })}
        </div>
      )}
    </Modal>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

/**
 * Les icônes des onglets d'en-tête (tuiles sur ordinateur, pastilles sur mobile) : la carte pliante
 * pour le Parcours — la même que « Voir au Parcours » —, le calendrier pour Semer, l'étiquette de lot.
 */
const ICONES_ONGLETS = { parcours: IconeCarte, semer: CalendarDays, lots: IconeDuLot }

export default function Pepiniere({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const { annoncer, signaler } = useNavigation()
  // [US-353 / CA12, D7] Un panneau droit de 400 px à partir de 900 px ; en dessous, la mise en page mobile.
  const bureau = useMedia('(min-width: 900px)')
  const { ouvrirPanneau, fermerPanneau, occupant: occupantPartage, hote } = useCoquille()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lotOuvert, setLotOuvert] = useState(null)        // le cycle de vie (DetailModal)
  // [US-356 / CA11] Le lot dont la fiche est ouverte (panneau droit ou feuille) ; `toutes` : la fiche
  // complète d'US-216 (« Toutes les actions du lot »), dont les gestes restent joignables.
  const [fiche, setFiche] = useState(null)
  const [toutes, setToutes] = useState(false)
  const [numeroInconnu, setNumeroInconnu] = useState(null)
  const [cultureOuverte, setCultureOuverte] = useState(null)
  // [US-195 / CA2] Une étiquette scannée ou un lien partagé ouvrent CE lot (`/?vue=pepiniere&lot=128`).
  // [US-356 / CA1] `onglet` (parcours, semer, lots), `emplacement` et `filtreLots` viennent du Plan
  // (US-201 / I5) et du mot de Gaston. [RT12] L'état exact de l'écran est rendu tel quel au retour.
  const [etat, setEtat] = useEtatEcran('pepiniere', {
    q: '', onglet: 'parcours', filtre: null, stade: null, filtreLots: 'en_cours',
  })
  const intention = useIntention('pepiniere', (i) => {
    const onglet = ongletDeLIntention(i)
    if (onglet || i?.emplacement || i?.filtreLots) {
      setEtat({
        onglet: onglet ?? 'parcours', filtre: i.emplacement ?? null, q: '',
        ...(i.filtreLots ? { filtreLots: filtreInitial(i.filtreLots) } : {}),
      })
    }
  })

  async function load() {
    setLoading(true); setError(null)
    try { setData(await api.pepiniereLots(dateRef, potagerId)) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh, dateRef, potagerId])

  // [US-216 / CA14] Au retour d'un geste envoyé au compagnon, UNE relecture : la liste et le lot
  // ouvert. Silencieuse — pas de squelette, la fiche reste ouverte.
  const relire = useCallback(async () => {
    try {
      const [liste, lotFrais] = await Promise.all([
        api.pepiniereLots(dateRef, potagerId),
        fiche?.numero_lot != null ? api.pepiniereLot(fiche.numero_lot, potagerId) : Promise.resolve(null),
      ])
      setData(liste)
      if (lotFrais) setFiche(lotFrais)
    } catch { /* la fiche garde ce qu'elle montre : rien ne disparaît en silence */ }
  }, [dateRef, potagerId, fiche?.numero_lot])

  const tousLots = data?.lots ?? []
  const parcours = data?.parcours ?? {}
  const aujourdhui = data?.date_ref_effective ?? null
  const onglet = ongletPepiniere(etat.onglet)
  const alertes = useMemo(() => alertesDesLots(tousLots, parcours, aujourdhui), [data]) // eslint-disable-line react-hooks/exhaustive-deps
  const ecriture = peutEnregistrer(potagerActif?.role)

  // [US-195 / CA3, CA4] Le lot désigné par l'intention, une fois les lots chargés : sa fiche s'ouvre et son
  // arrivée est annoncée. Lot inconnu — sorti de pépinière, supprimé, d'un autre potager — l'écran s'ouvre
  // quand même, et le dit. L'intention ne déclenche aucune écriture : elle ne fait qu'ouvrir.
  // [US-209 / CA11] `lot=128` désigne le NUMÉRO court écrit sur l'étiquette ; un identifiant technique
  // (`semis-12`) reste reconnu pour les liens déjà partagés.
  useEffect(() => {
    if (!intention?.lot || loading) return
    const numero = lireNumeroLot(intention.lot)
    const cible = tousLots.find((l) =>
      (numero != null && l.numero_lot === numero) || String(l.lot_id) === String(intention.lot))
    if (cible) {
      // [US-216 / CA2] Ouverte par l'adresse : UNE lecture, celle du lot par son numéro — c'est elle qui
      // porte échéances et action suggérée à jour.
      if (cible.numero_lot != null) ouvrirParNumero(cible.numero_lot)
      else setFiche(cible)
      annoncer(`Lot ${cible.culture}${cible.variete ? ` · ${cible.variete}` : ''} ouvert.`)
    } else {
      if (numero != null) setNumeroInconnu(numero)   // [US-216 / CA13] la fiche s'ouvre et le dit
      signaler(numero != null ? messageLotInconnu(numero) : "Ce lot de semis n'existe plus.")
    }
  }, [loading, data, intention])

  /** [US-216 / CA2, CA13] Une seule lecture ; un numéro inconnu ouvre quand même la fiche, qui le dit. */
  async function ouvrirParNumero(numero) {
    try {
      const lot = await api.pepiniereLot(numero, potagerId)
      setNumeroInconnu(null)
      setFiche(lot)
      return true
    } catch (err) {
      if (err.statut === 404 || /404/.test(err.message)) {
        setFiche(null)
        setNumeroInconnu(numero)
        signaler(messageLotInconnu(numero))
      } else {
        signaler(err.message)
      }
      return false
    }
  }

  const fermerFiche = useCallback(() => { setFiche(null); setToutes(false) }, [])

  // ── Le socle (US-353) : l'en-tête, le mot de Gaston, la barre d'outils ─────────────────────────
  const nbSemer = nbASemer(parcours)
  const mot = useMemo(() => {
    if (!data) return null
    if (onglet === 'semer') return motDeSemer(parcours)
    if (onglet === 'lots') return motDesLots({ lots: tousLots, alertes })
    return motDuParcours({ lots: tousLots, alertes })
  }, [data, onglet, alertes, bureau]) // eslint-disable-line react-hooks/exhaustive-deps
  const placeholder = onglet === 'semer' ? 'Culture ou variété' : onglet === 'lots' ? 'Lot n°, culture ou variété' : 'Lot, culture ou variété'
  useDeclarerEcran({
    entete: {
      contexte: CONTEXTE_ONGLET[onglet],
      onglets: ongletsPepiniere({ nbSemer, nbLots: tousLots.length }).map((o) => ({ ...o, icon: ICONES_ONGLETS[o.id] })),
      actif: onglet,
      onChoisir: (id) => { setEtat({ onglet: id }); fermerFiche() },
    },
    mot,
    barre: { recherche: { placeholder, valeur: etat.q ?? '', onChange: (q) => setEtat({ q }) } },
  }, [onglet, JSON.stringify(mot), etat.q, nbSemer, tousLots.length])

  // [US-356 / CA11] La fiche d'un lot sur ordinateur : le panneau droit partagé (un seul occupant), dessiné par
  // portail — l'état de l'écran reste ici. Sur mobile, une feuille.
  const dansPanneau = bureau && fiche != null && !toutes
  const panneauOuvertParMoi = useRef(false)
  const titreFiche = fiche ? `Lot ${fiche.numero_lot != null ? `#${fiche.numero_lot} · ` : ''}${fiche.culture ?? ''}` : ''
  useEffect(() => {
    if (dansPanneau) {
      panneauOuvertParMoi.current = true
      ouvrirPanneau({ cle: 'fiche', titre: titreFiche, contenu: <HotePanneau /> })
    } else if (panneauOuvertParMoi.current) {
      panneauOuvertParMoi.current = false
      fermerPanneau()
    }
  }, [dansPanneau, titreFiche]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => {
    if (panneauOuvertParMoi.current) { panneauOuvertParMoi.current = false; fermerPanneau() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // Le panneau fermé de l'extérieur (×, Gaston qui s'ouvre) : la fiche suit.
  useEffect(() => {
    if (occupantPartage || !panneauOuvertParMoi.current) return
    panneauOuvertParMoi.current = false
    setFiche(null)
  }, [occupantPartage]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />

  const nbPepinieres = Array.isArray(data?.pepinieres) ? data.pepinieres.length : null
  const alerteDeLaFiche = fiche ? alertes.get(fiche.lot_id) ?? null : null

  // Le contenu de la fiche : le même dans le panneau et dans la feuille.
  const contenuFiche = fiche && (
    <FicheLotCommune
      lot={fiche} parcours={parcours} alerte={alerteDeLaFiche} ecriture={ecriture}
      onNoter={() => ouvrirGastonSur({ sujet: sujetLot({ numero: fiche.numero_lot, culture: fiche.culture, variete: fiche.variete, emplacement: emplacementDuLot(fiche, parcours).texte }) })}
      onVoirParcours={() => { setEtat({ onglet: 'parcours' }); setToutes(false) }}
      // [US-358] Depuis le Parcours, la fiche mène au registre des Lots, sur la colonne de ce lot (le lot est amené en vue).
      onglet={onglet}
      onVoirLots={() => { setEtat({ onglet: 'lots', q: '', filtreLots: statutPepiniere(fiche, alertes) }); setToutes(false) }}
      onToutesLesActions={() => setToutes(true)}
    />
  )

  const ouvrirLot = (lot) => { setNumeroInconnu(null); setToutes(false); setFiche(lot) }

  return (
    <RelectureAuRetourProvider relire={relire}>
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-3.5 min-w-0">
        {onglet === 'parcours' && (
          <OngletParcours
            data={recherche(data, etat.q)} etat={etat} setEtat={setEtat} bureau={bureau} alertes={alertes}
            lotSelectionne={fiche?.lot_id} onOuvrirLot={ouvrirLot}
          />
        )}
        {onglet === 'semer' && <OngletSemer data={data} dateRef={dateRef} q={etat.q} />}
        {onglet === 'lots' && (
          <OngletLots
            data={data} etat={etat} setEtat={setEtat} bureau={bureau} alertes={alertes} aujourdhui={aujourdhui}
            lotOuvert={fiche?.lot_id} onOuvrirLot={ouvrirLot}
          />
        )}
      </div>

      {/* [US-356 / CA11] Ordinateur : le panneau droit (portail). Mobile : la feuille de la fiche commune. */}
      {dansPanneau && hote && createPortal(<div className="pt-12">{contenuFiche}</div>, hote)}
      {!bureau && fiche != null && !toutes && (
        <Modal title={titreFiche} onClose={fermerFiche} disposition="basse" entete={false} bodyClassName="p-0 overflow-y-auto min-h-0">
          <div className="pt-1">{contenuFiche}</div>
        </Modal>
      )}
      {/* « Toutes les actions du lot » : la fiche complète d'US-216 — repiquer, mettre en terre, clôturer, ranger… */}
      {fiche != null && toutes && (
        <FicheLot
          lot={fiche} forme="modale" nbPepinieres={nbPepinieres} dateRef={dateRef}
          fragments={fragmentsDuLot(data?.parcours, fiche.lot_id)}
          onClose={fermerFiche}
          onOuvrirDetail={() => setLotOuvert(fiche)}
          onOuvrirCulture={setCultureOuverte}
        />
      )}
      {numeroInconnu != null && <FicheLotInconnu numero={numeroInconnu} onClose={() => setNumeroInconnu(null)} />}
      {lotOuvert && <DetailModal lot={lotOuvert} onClose={() => setLotOuvert(null)} />}
      {cultureOuverte && (
        <FicheCulture
          culture={cultureOuverte} dateRef={dateRef} potagerId={potagerId}
          ecran="pepiniere" onClose={() => setCultureOuverte(null)}
        />
      )}
    </div>
    </RelectureAuRetourProvider>
  )
}

/**
 * [US-356 / CA1] La recherche du Parcours (« Lot, culture ou variété ») : ne garde que les étiquettes qui
 * y répondent — les compteurs des colonnes suivent. Sans recherche, la lecture telle quelle.
 */
function recherche(data, q) {
  const t = String(q ?? '').trim().toLowerCase().replace(/^#/, '')
  if (!t || !data?.parcours) return data
  const garde = (e) => `${e.lot?.numero ?? ''} ${e.lot?.culture ?? ''} ${e.lot?.variete ?? ''}`.toLowerCase().includes(t)
  return { ...data, parcours: { ...data.parcours, etiquettes: (data.parcours.etiquettes ?? []).filter(garde) } }
}
