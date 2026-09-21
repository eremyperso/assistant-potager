// [US-224] Le bouton d'action des épics 9 à 12 — un seul, pour tous.
//
// « Enregistrer le semis » de la fiche calendrier, « ajouter une culture » d'un
// rang libre, « Repiquer », « Noter la levée », « Mettre en terre », « Clôturer »
// d'un lot : tous passent par ici, et aucun n'écrit. Le bouton **dépose** un
// geste dans la file (`POST /gestes/intentions`, qui n'écrit aucun événement) ;
// c'est le compagnon qui présente le récapitulatif et attend « Confirmer ».
//
// Ce qui change par rapport à US-196, et qui est tout l'objet d'US-224 :
//
//   * [CA21] **Le dépôt ne dépend plus d'un compagnon activé.** On prépare sa
//     journée d'abord, on active une fois. Sans compagnon, le geste entre quand
//     même dans la file et l'application invite à l'activer — elle ne bloque
//     plus. C'est l'inverse d'US-196 / CA10, et c'est voulu.
//   * [CA3] Le geste y reste **trois jours**, pas quinze minutes, et le lien
//     n'est plus à usage unique : rouvrir redonne le même geste.
//   * [CA4] Un geste identique déjà en attente est **signalé, pas refusé** :
//     semer deux fois la même chose le même jour est un cas réel.
//
// Deux choses inchangées, et qui tiennent toujours ici :
//   * [US-196 / CA9] La phrase équivalente à dicter est proposée à côté,
//     copiable — pour qui préfère parler à son potager plutôt qu'appuyer.
//   * [CA24] Un membre en lecture seule ne voit rien du tout.
import { useState } from 'react'
import { Send, Copy, Check, Clock } from 'lucide-react'
import { Btn, Modal, SectionLabel } from './ui'
import { PanneauActivation, useCodeLiaison } from './LierTelegram.jsx'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { useFileGestes } from '../context/FileGestesContext.jsx'
import { useArmerRelecture } from '../hooks/useRelectureAuRetour.jsx'
import {
  corpsIntention, dateDuGeste, MENTION_DATE_RAMENEE, peutEnregistrer, phraseADicter,
} from '../lib/gestes.js'

/**
 * [CA21] L'invitation à activer — APRÈS le dépôt, jamais avant.
 *
 * Elle ne fabrique pas un second parcours d'activation : même crochet, même
 * panneau qu'US-091 (bouton deep-link, QR, code en clair, compte à rebours).
 * Le geste, lui, est déjà en file : c'est ce que dit la première phrase, et
 * c'est ce qui distingue cette modale de celle d'US-196, qui annonçait un
 * geste à refaire.
 */
function ModalActivationApresDepot({ nbEnAttente, onClose }) {
  const etat = useCodeLiaison(false)
  return (
    <Modal title="Activez votre compagnon" icon={Send} onClose={onClose}>
      <p className="text-[13px] text-txt2 leading-relaxed mb-3">
        <strong>
          {nbEnAttente > 1 ? `Vos ${nbEnAttente} gestes vous attendent` : 'Votre geste vous attend'}
        </strong>{' '}
        — il est en file, rien n'est perdu. Les gestes se confirment dans le
        compagnon de terrain : c'est lui qui vous relit avant d'enregistrer.
        Activez-le une fois, il vous proposera ensuite de les traiter.
      </p>
      <SectionLabel>Lien d'activation</SectionLabel>
      <PanneauActivation etat={etat} />
    </Modal>
  )
}

/** [US-196 / CA9] La phrase à dicter, copiable — le repli de qui préfère parler. */
function PhraseADicter({ phrase }) {
  const [copie, setCopie] = useState(false)
  if (!phrase) return null
  const copier = () => {
    navigator.clipboard?.writeText(phrase).then(() => {
      setCopie(true)
      setTimeout(() => setCopie(false), 1500)
    })
  }
  return (
    <button
      type="button"
      onClick={copier}
      title="Copier la phrase"
      className="inline-flex items-start gap-1.5 text-left text-[11.5px] text-txt3 leading-snug"
    >
      {copie ? <Check size={13} className="shrink-0 mt-px text-brand" aria-hidden="true" />
             : <Copy size={13} className="shrink-0 mt-px" aria-hidden="true" />}
      <span>Ou dites au compagnon : «&nbsp;{phrase}&nbsp;»</span>
    </button>
  )
}

/**
 * @param geste  { action, culture, variete, quantite, unite, parcelleId, rang,
 *                 lotId, contexteSemis } — tout facultatif sauf `action`.
 *                 Ce qui manque, le compagnon le demandera : il ne l'invente pas.
 * @param dateRef  Date de référence de l'écran (ISO). Ramenée au jour si à venir (CA26).
 * @param ecran    Origine, pour la mesure d'usage.
 * @param libelle  Texte du bouton (« Enregistrer le semis », « Repiquer »…).
 * @param onLance  Appelé une fois le geste déposé — l'écran s'en sert pour
 *                 savoir qu'il devra se relire au retour (CA22).
 */
export default function BoutonGeste({
  geste, dateRef = null, ecran = null, libelle = 'Enregistrer',
  potagerId = null, onLance, kind = 'primary', small = false, className = '',
}) {
  const { potagerActif } = usePotager()
  const { recharger } = useFileGestes()
  const armerRelecture = useArmerRelecture()
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [activation, setActivation] = useState(null)
  const [depose, setDepose] = useState(null)
  const [phraseServeur, setPhraseServeur] = useState(null)

  // [CA24] Rien à afficher pour un membre en lecture seule — pas un bouton
  // désactivé, pas une explication : rien. Le serveur refuse de son côté.
  if (!peutEnregistrer(potagerActif?.role)) return null

  const { date, ramenee } = dateDuGeste(dateRef)
  // La phrase locale s'affiche tout de suite ; celle du serveur, qui fait foi,
  // la remplace dès le premier dépôt.
  const phrase = phraseServeur ?? phraseADicter({
    action: geste?.action, culture: geste?.culture,
    contexteSemis: geste?.contexteSemis, parcelle: geste?.parcelleNom,
  })

  async function lancer() {
    setErreur(null)
    setDepose(null)
    setEnCours(true)
    try {
      // [CA21] Le dépôt D'ABORD, sans condition : la file se remplit même sans
      // compagnon activé. Plus de contrôle préalable, plus de geste à refaire.
      const res = await api.preparerGeste(corpsIntention({
        ...geste, date, ecran, potagerId: potagerId ?? potagerActif?.id,
      }))
      if (res?.phrase) setPhraseServeur(res.phrase)
      setDepose(res)
      // [CA22] Le compte affiché partout change à l'instant même.
      recharger()
      // [CA22] L'écran apprend qu'un geste est parti : il se relira au retour
      // d'onglet, une fois, sans interrogation périodique.
      armerRelecture()
      onLance?.(res)

      if (!res?.compagnon_actif) {
        // [CA21] Le geste est en file ; l'application invite à activer, elle ne
        // bloque pas. Le compagnon proposera ensuite de le traiter.
        setActivation(res?.en_attente ?? 1)
        return
      }
      if (!res?.lien) {
        // Identifiant public du bot introuvable (même repli que GET /auth/me) :
        // la phrase reste, elle, parfaitement utilisable — et le geste attend.
        setErreur("Le compagnon n'a pas pu être ouvert. Votre geste attend dans la file.")
        return
      }
      window.open(res.lien, '_blank', 'noopener')
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className={`flex flex-col items-end gap-1.5 ${className}`}>
      <Btn kind={kind} small={small} icon={Send} onClick={lancer} disabled={enCours}>
        {enCours ? 'Préparation…' : libelle}
      </Btn>
      {/* [CA26] La règle se dit avant d'appuyer, jamais après coup. */}
      {ramenee && <span className="text-[11px] text-txt3">{MENTION_DATE_RAMENEE}</span>}
      {/* [CA4] Signalé, pas interdit : le geste est bien en file, et on le dit. */}
      {depose?.doublon && (
        <span className="inline-flex items-center gap-1 text-[11.5px] text-amber text-right">
          <Clock size={12} aria-hidden="true" />
          Un geste identique attend déjà — celui-ci a été ajouté aussi.
        </span>
      )}
      <PhraseADicter phrase={phrase} />
      {erreur && <span className="text-[11.5px] text-red text-right">{erreur}</span>}
      {activation !== null && (
        <ModalActivationApresDepot
          nbEnAttente={activation}
          onClose={() => setActivation(null)}
        />
      )}
    </div>
  )
}
