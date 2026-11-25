// [US-356 / CA6, CA7] L'onglet « Semer » — le bon moment pour semer.
//
// La bande « Le bon moment pour semer » du Parcours devient un onglet, en trois groupes :
//  · **Fenêtre ouverte · n** — « fenêtre de semis ouverte · graines en stock · aucun lot de la culture
//    en cours » : une tuile par culture (nom en Lora, « reste 7 j » en orange, barre de la part de
//    fenêtre écoulée, « 1 sept. → 30 nov. · pépinière froide », variétés, bouton **Semer**) ;
//  · **Fenêtre ouverte, mais rien à semer · n** — la culture et son motif (« Graines épuisées : à
//    racheter », « Un lot est déjà en cours (#59) ») ;
//  · **Bientôt** — les prochaines ouvertures (« Poireau d'été — semis en pépinière à partir du 1er janv.
//    — dans 45 j »).
//
// Aucune fenêtre n'est recalculée ici (RT6) : jours restants, part écoulée, motifs et ouvertures sont
// ceux du serveur (`parcours.a_semer`, `a_semer_ecartees`, `prochaines_ouvertures`). Un motif qu'il ne
// donne pas n'est pas affiché. [US-358 / CA1] Le bouton Semer ouvre Gaston sur la culture, sa variété et sa
// fenêtre, avec la phrase « Semer l'oignon blanc de Paris en pépinière froide » prête dans le champ.
import { Package, Plus, Sprout } from 'lucide-react'
import { PastilleEtape } from './ui/EtapeCulture.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { peutEnregistrer } from '../lib/gestes.js'
import { ouvrirGastonSur } from '../lib/contexteCompagnon.js'
import { sujetSemer } from '../lib/ouvertureGaston.js'
import { tuilesASemer, ecartees, prochainesOuvertures, phraseSemer } from '../lib/pepiniereSocle.js'
import { symboleDeCulture } from '../lib/pictosCultures.js'

const CRITERE = 'Fenêtre de semis ouverte · graines en stock · aucun lot de la culture en cours'

function Titre({ children, n }) {
  return (
    <h2 className="mb-2 flex items-baseline gap-2 text-[13px] font-bold text-txt2">
      {children}{n != null && <span className="text-txt3"> · {n}</span>}
    </h2>
  )
}

function TuileSemer({ t }) {
  const { potagerActif } = usePotager()
  const ecrire = peutEnregistrer(potagerActif?.role)
  return (
    <li className="flex flex-col gap-1.5 rounded-[14px] border border-border bg-card p-3 shadow-card">
      <div className="flex items-baseline justify-between gap-2">
        <b className="font-serif text-[15px] font-bold text-txt">{t.nom}</b>
        {t.reste && <span className="shrink-0 text-[12px] font-bold text-due-tx">{t.reste}</span>}
      </div>
      {t.part != null && (
        <div className="relative h-2 overflow-hidden rounded-full bg-card-alt" role="img" aria-label={`${t.part} % de la fenêtre écoulée`}>
          <i className="absolute inset-y-0 left-0 rounded-full bg-due" style={{ width: `${t.part}%` }} />
        </div>
      )}
      {t.fenetre && <small className="text-[11.5px] text-txt2">{t.fenetre}</small>}
      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <span className="min-w-0 truncate text-[12px] text-txt">{t.varietes.join(', ') || 'variété non précisée'}</span>
        {ecrire && (
          <button
            type="button" onClick={() => ouvrirGastonSur({ sujet: sujetSemer(t), champ: phraseSemer(t) })}
            aria-label={`Semer ${t.culture} en pépinière`}
            className="inline-flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-[10px] bg-brand px-3.5 text-[13px] font-semibold text-white hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
          >
            <Plus size={15} aria-hidden="true" />Semer
          </button>
        )}
      </div>
    </li>
  )
}

function Ligne({ pastille, titre, detail, droite }) {
  return (
    <li className="flex items-center gap-3 px-3 py-2.5">
      {pastille}
      <span className="min-w-0 flex-1">
        <b className="block truncate text-[13.5px] text-txt">{titre}</b>
        <small className="block text-[12px] text-txt2">{detail}</small>
      </span>
      {droite && <span className="shrink-0 text-[12px] font-bold text-txt2">{droite}</span>}
    </li>
  )
}

const Pastille = ({ Icone }) => (
  <span aria-hidden="true" className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-[9px] bg-card-alt text-txt2"><Icone size={16} /></span>
)

/** La recherche de la barre d'outils (« Culture ou variété ») : elle filtre les trois groupes. */
const repond = (q, ...champs) => {
  const t = String(q ?? '').trim().toLowerCase()
  return !t || champs.some((c) => String(c ?? '').toLowerCase().includes(t))
}

export default function OngletSemer({ data, dateRef, q = '' }) {
  const parcours = data?.parcours ?? {}
  const ref = data?.date_ref_effective ?? dateRef
  const tuiles = tuilesASemer(parcours).filter((t) => repond(q, t.culture, ...t.varietes))
  const ecartes = ecartees(parcours).filter((e) => repond(q, e.culture))
  const bientot = prochainesOuvertures(parcours).filter((o) => repond(q, o.culture))

  if (!tuiles.length && !ecartes.length && !bientot.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-txt3">
        <Sprout size={32} aria-hidden="true" />
        <p className="text-[15px]">Rien à semer pour l’instant</p>
      </div>
    )
  }

  return (
    <div className="@container/semer flex flex-col gap-5">
      {tuiles.length > 0 && (
        <section aria-label="Fenêtre ouverte">
          <Titre n={tuiles.length}>Fenêtre ouverte</Titre>
          <p className="-mt-1 mb-2 text-[12px] text-txt2">{CRITERE}</p>
          <ul className="grid grid-cols-1 gap-2.5 @[700px]/semer:grid-cols-3">
            {tuiles.map((t) => <TuileSemer key={t.culture} t={t} />)}
          </ul>
        </section>
      )}

      {ecartes.length > 0 && (
        <section aria-label="Fenêtre ouverte, mais rien à semer">
          <Titre n={ecartes.length}>Fenêtre ouverte, mais rien à semer</Titre>
          <ul className="divide-y divide-border-soft overflow-hidden rounded-[14px] border border-border bg-card">
            {ecartes.map((e) => (
              <Ligne
                key={`${e.culture}-${e.code}`}
                pastille={<Pastille Icone={e.code === 'graines_epuisees' ? Package : Sprout} />}
                titre={`${symboleDeCulture(e.culture)} ${e.nom}`} detail={e.motif}
              />
            ))}
          </ul>
        </section>
      )}

      {bientot.length > 0 && (
        <section aria-label="Bientôt">
          <Titre>Bientôt</Titre>
          <ul className="divide-y divide-border-soft overflow-hidden rounded-[14px] border border-border bg-card">
            {bientot.map((o) => (
              <Ligne
                key={`${o.culture}-${o.dans}`}
                pastille={<PastilleEtape etape="semee" prevue petite />}
                titre={o.nom} detail={o.texte} droite={o.dans}
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

