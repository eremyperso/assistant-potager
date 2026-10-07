// [US-200] Sous-onglet « Vue plan » — une carte par parcelle, un trait par rang.
//
// V1 de rendu retenue au wireframe v3 (« Plan simplifié », 19/09/2026) : aucune
// géométrie, aucune aire proportionnelle, aucune surface calculée. Une parcelle
// affiche ses rangs, un rang par culture, et la longueur d'un trait ne dit que
// la quantité relative **à unité égale** dans cette parcelle.
//
// Tout ce qui se calcule vit dans `lib/planVue.js` (CA2) ; tout ce qui se lit
// vient de la seule requête `GET /plan` (CA1) — la répartition en rangs y est
// déjà faite par `app/services/repartition_rangs.py` (US-198), la phase par le
// recalage (US-194). Cet écran ne recompte rien.
//
// [US-201] Les SORTIES : un rang occupé ouvre la fiche de sa culture, un rang
// libre propose *Semer en place* / *Planter*, l'en-tête mène à la parcelle, la
// carte d'une pépinière à la Pépinière, la barre au Journal du jour. Quelle
// destination pour quel appui ? `destinationXxx` de `lib/planVue.js` le dit
// (CA9) : cet écran ne fait que les appliquer. Pas de panneau de détail, aucun
// état de sélection, aucun geste de dessin (I1, I7) — « le Plan n'est pas un
// éditeur ». Le réordonnancement est l'objet d'US-202.
import { useState, useEffect, useMemo } from 'react'
import { Leaf, Sprout } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  vueDuPlan, palettePhases, CHOIX_AJOUT, destinationRang, destinationNonLocalisee,
  destinationFicheParcelle, destinationPepiniere,
} from '../lib/planVue.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useNavigation } from '../context/NavigationContext.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import FicheCulture from '../components/FicheCulture.jsx'
import BoutonGeste from '../components/BoutonGeste.jsx'
import { CartePlanParcelle, TraitRang, SectionLabel, Modal } from '../components/ui'
import { MarqueLibre, PictoCulture } from '../components/ui/PisteDesPlaces.jsx'
import { IconePhase } from '../components/ui/PastillePhase.jsx'
import { phase, PHASE_LIBRE } from '../lib/phases.js'

/**
 * [V13] Légende compacte : phases, échelle de la piste et numérotation.
 */
function LegendePlan() {
  return (
    <div role="group" aria-label="Légende du plan"
      className="flex flex-wrap items-center gap-x-[22px] gap-y-2.5 rounded-xl border border-border bg-card px-[18px] py-3 text-[13px] text-txt2">
      {['en_place', 'en_recolte', 'semee', 'libre'].map(cle => {
        const etat = cle === 'libre' ? PHASE_LIBRE : phase(cle)
        return (
          <span key={cle} className="inline-flex items-center gap-[7px]">
            <IconePhase phase={cle} taille={16} className={etat.teinte.split(' ')[1]} />
            {etat.libelle}
          </span>
        )
      })}
      <span aria-hidden="true" className="w-px h-[18px] bg-border" />
      <span className="inline-flex items-center gap-[7px] min-w-0">
        <PictoCulture culture="tomate" />
        <span>7 symboles = rang plein (en proportion)</span>
      </span>
      <span className="inline-flex items-center gap-[7px] min-w-0">
        <span className="w-[22px] shrink-0"><TraitRang mode="surface" longueur={100} phase="en_place" /></span>
        <span>Semis à la volée : quantité relative</span>
      </span>
      <span className="inline-flex items-center gap-[7px]"><MarqueLibre taille={12} />= place restante</span>
      <span aria-hidden="true" className="w-px h-[18px] bg-border" />
      <span>Rangs numérotés dans l’ordre d’installation</span>
    </div>
  )
}

/**
 * [V17] Les cultures dont la parcelle n'a jamais été dite : une dernière carte,
 * sans rang ni numéro, avec la phrase à prononcer pour les rattacher.
 */
function CarteNonLocalisees({ lignes, phrase, onCulture }) {
  return (
    <section
      aria-label="Cultures non localisées"
      className="rounded-xl border border-dashed border-txt3/60 bg-card p-3"
    >
      <h3 className="font-serif text-[13.5px] font-bold text-txt mb-1.5">Cultures non localisées</h3>
      <ul className="flex flex-col">
        {lignes.map((l, i) => (
          <li key={`${l.culture}-${l.variete}-${i}`}>
            {/* [US-201 / CA7] Comme un rang : la fiche de la culture, sans
                contexte de parcelle. Le libellé entier est la cible, 44 px. */}
            <button
              type="button"
              onClick={() => onCulture(l)}
              className="w-full min-h-[44px] text-left text-[13px] text-txt rounded-lg px-1
                         hover:bg-card-alt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              {l.libelle}
            </button>
          </li>
        ))}
      </ul>
      <p className="text-[10.5px] text-txt3 italic mt-2">{phrase}</p>
    </section>
  )
}

/** [V14] « Trois chiffres, pas un tableau de bord ». */
function PiedDeVue({ pied }) {
  return (
    <footer className="border-t border-border py-3 text-[13px] text-txt2 flex flex-col gap-1">
      <span>
        Total <span className="font-semibold text-txt">{pied.surface}</span> ·{' '}
        <span className="font-semibold text-txt">{pied.rangs}</span>
      </span>
      <span>{pied.libres}</span>
      {/* [US-228 / P14, RT13] Trois chiffres, toujours : jamais un total de
          places ni un taux de remplissage. */}
      {(pied.sansNbRangs || pied.sansLongueur) && (
        <span className="text-txt3">
          {[pied.sansNbRangs, pied.sansLongueur].filter(Boolean).join(' · ')}
        </span>
      )}
    </footer>
  )
}

/**
 * [US-201 / I3, CA3] « Ajouter une culture » sur un rang libre : le choix entre
 * *Semer en place* et *Planter*. Rien n'est enregistré ici — chaque bouton
 * dépose un geste pré-rempli avec la parcelle dans la file (US-196 / US-224),
 * et c'est le compagnon qui demande la culture, relit et confirme.
 */
function ModalAjoutCulture({ cible, dateRef, onClose }) {
  return (
    <Modal
      title="Ajouter une culture"
      icon={Sprout}
      sub={`${cible.nomParcelle} · rang ${cible.rang}`}
      onClose={onClose}
      disposition="basse"
    >
      <p className="text-[13px] text-txt2 leading-relaxed mb-4">
        Que voulez-vous faire sur ce rang libre ? Votre compagnon vous demandera
        la culture, puis vous relira avant d’enregistrer.
      </p>
      <div className="flex flex-col gap-4">
        {CHOIX_AJOUT.map((choix, i) => (
          <BoutonGeste
            key={choix.cle}
            geste={{ ...choix.geste, parcelleId: cible.parcelleId, parcelleNom: cible.nomParcelle }}
            dateRef={dateRef}
            ecran="plan-vue"
            libelle={choix.libelle}
            kind={i === 0 ? 'primary' : 'soft'}
          />
        ))}
      </div>
    </Modal>
  )
}

export default function PlanVue({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const { aller } = useNavigation()
  const role = potagerActif?.role
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // [I1] Aucun état « parcelle sélectionnée » : seule la fenêtre ouverte par
  // l'appui en cours se mémorise, et elle disparaît à sa fermeture.
  const [ouvert, setOuvert] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      // [CA1] UNE lecture, et une seule : tout le dessin en sort.
      setData(await api.plan(dateRef, potagerId))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [refresh, dateRef, potagerId])

  const vue = useMemo(() => vueDuPlan(data), [data])
  const palette = useMemo(() => palettePhases(), [])

  // [CA8] Chargement : un squelette, jamais des traits qui se remplissent sous
  // les yeux — une longueur qui bouge se lirait comme une quantité qui change.
  if (loading) return <LoadingSkeleton lines={4} />
  // [CA8] Échec : le message et la relance, sans aucune valeur de repli.
  if (error) return <ApiError message={error} onRetry={load} />

  const vide = vue.cartes.length === 0 && vue.nonLocalisees.length === 0
  // La date de référence que la vue a réellement servie (jamais dans le futur).
  const dateJour = vue.dateRef ?? dateRef

  // [US-201 / CA9] Une destination, appliquée : une fenêtre par-dessus la Vue
  // plan, ou un autre écran. `null` (rang libre en lecture seule) n'ouvre rien.
  function appliquer(destination) {
    if (!destination) return
    if (destination.type === 'aller') aller(destination.vue, destination.intention)
    else setOuvert(destination)
  }

  return (
    <div className="flex flex-col gap-3.5">
      {/* [V15] La phase est celle du jour de référence, jamais une projection.
          [US-223 / CA5] Le sélecteur de date et « Journal du jour » ont rejoint
          la barre de l'activité (`BarreActivitePlan`), communs aux deux onglets. */}
      {vide ? (
        // [CA8] Aucune parcelle : le message de l'onglet Parcelles, mot pour mot.
        <div className="flex flex-col items-center gap-3 mt-12 text-txt3">
          <Leaf size={36} />
          <p className="text-base">Aucune parcelle enregistrée.</p>
        </div>
      ) : (
        <>
          <LegendePlan />

          {/* [US-228 / CA5, A23] Deux colonnes à partir de 1000 px de largeur de
              CONTENEUR — le seuil de la maquette gelée, qui remplace les 720 px
              d'A1 : une carte porte désormais une piste, elle a besoin de plus
              de largeur pour rester lisible. Une colonne en dessous, jamais
              trois — container queries, jamais de breakpoint d'écran. */}
          <div className="@container/plan">
            <SectionLabel>Mes parcelles · {vue.cartes.length}</SectionLabel>
            <div className="grid grid-cols-1 gap-[18px] items-start @[1000px]/plan:grid-cols-2">
              {vue.cartes.map((carte) => (
                <CartePlanParcelle
                  key={carte.id}
                  carte={carte}
                  palette={palette}
                  // [I4] Le seul accès à la parcelle elle-même.
                  onFiche={() => appliquer(destinationFicheParcelle(carte))}
                  // [I5] La carte d'une pépinière mène à la Pépinière.
                  onPepiniere={carte.pepiniere
                    ? () => appliquer(destinationPepiniere(carte, vue.cartes))
                    : undefined}
                  // [I2, I3] Un rang occupé ouvre sa culture ; un rang libre
                  // propose d'ajouter — ou rien du tout en lecture seule.
                  onRang={(rang) => appliquer(destinationRang(rang, carte, { role }))}
                />
              ))}
              {vue.nonLocalisees.length > 0 && (
                <CarteNonLocalisees
                  lignes={vue.nonLocalisees}
                  phrase={vue.phraseNonLocalisees}
                  onCulture={(ligne) => appliquer(destinationNonLocalisee(ligne))}
                />
              )}
            </div>
          </div>

          <PiedDeVue pied={vue.pied} />
        </>
      )}

      {/* [US-201 / CA1, CA5] La fiche s'ouvre PAR-DESSUS la Vue plan, qui reste
          montée : la fermer rend l'écran dans son état exact, défilement
          compris, et le focus revient sur le rang d'origine (`Modal`,
          US-195 / CA8). */}
      {ouvert?.type === 'culture' && (
        <FicheCulture
          culture={ouvert.culture}
          dateRef={dateJour}
          potagerId={potagerId}
          parcelleId={ouvert.parcelleId}
          nomParcelle={ouvert.nomParcelle || null}
          rang={ouvert.rang}
          ecran="plan-vue"
          onClose={() => setOuvert(null)}
        />
      )}
      {ouvert?.type === 'ajout' && (
        <ModalAjoutCulture cible={ouvert} dateRef={dateJour} onClose={() => setOuvert(null)} />
      )}
    </div>
  )
}
