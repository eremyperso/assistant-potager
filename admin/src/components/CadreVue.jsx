import { CloudOff } from 'lucide-react'
import { estVueDuJour } from '../lib/periode.js'
import { heure } from '../lib/format.js'

function Panne({ erreur }) {
  return (
    <section role="alert" className="flex items-start gap-2.5 rounded-xl border border-amber bg-amber-soft px-3 py-2.5 text-[13px] text-txt">
      <CloudOff size={18} className="mt-px shrink-0 text-amber" aria-hidden="true" />
      <span>
        <b className="block">{erreur.statut === 0 ? 'API indisponible' : erreur.statut === 403 ? 'Accès réservé' : 'Lecture impossible'}</b>
        {erreur.statut === 0 ? "Aucune valeur n'a encore pu être lue : il n'y a pas de données à montrer." : erreur.message}
      </span>
    </section>
  )
}

/**
 * Le cadre commun des vues Coût, Fiabilité et Dérives : chargement, panne d'API sans valeur, dernières
 * valeurs connues avec leur heure (grisées) — exactement ce que la vue Consommation fait pour elle-même
 * [US-311 / CA5, CA6]. `children(ancien, hhmm)` rend le corps de la vue.
 */
export default function CadreVue({ donnees, erreur, enCours, misAJour, periode, children }) {
  if (!donnees) {
    if (erreur) return <Panne erreur={erreur} />
    return <p className="py-10 text-center text-sm text-txt2" role="status">Chargement des chiffres…</p>
  }
  const ancien = Boolean(erreur)
  const hhmm = misAJour ? heure(misAJour) : ''
  const corps = children(ancien, hhmm)
  return (
    <div className="flex flex-col gap-3 tab:gap-3.5" aria-busy={enCours}>
      {ancien ? (
        <div role="status" className="flex items-start gap-2.5 rounded-xl border border-amber bg-amber-soft px-3 py-2.5 text-[13px] text-txt">
          <CloudOff size={18} className="mt-px shrink-0 text-amber" aria-hidden="true" />
          <span>
            <b className="block">API indisponible</b>
            Dernières valeurs connues, données de {hhmm}.{' '}
            {estVueDuJour(periode) ? 'Nouvel essai automatique dans 1 min.' : 'Rafraîchissez pour réessayer.'}
          </span>
        </div>
      ) : null}
      {ancien
        ? <div className="flex flex-col gap-3 tab:gap-3.5 opacity-55 grayscale-[.7]" style={{ filter: 'grayscale(.7)' }}>{corps}</div>
        : corps}
    </div>
  )
}
