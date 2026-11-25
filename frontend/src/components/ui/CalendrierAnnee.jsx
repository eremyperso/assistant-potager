import { casesCalendrier, INITIALES_MOIS, NOM_CALENDRIER } from '../../lib/calendrierAnnee.js'

/**
 * Calendrier de l'année [US-352 / CA3] : douze cases de 9 px, gouttière de 2 px, aux couleurs
 * semis / levée-plantation / croissance / floraison / récolte, le mois courant cerclé, initiales
 * des mois en option. Remplace `MonthStrip` dans Cultures, le catalogue et la fiche Référence.
 *
 * `mois` : douze clés de geste (`lib/calendrierAnnee.js`, `moisDeFrise`). `frise` (facultatif) :
 * la frise d'origine, pour que l'infobulle d'un mois dise TOUS ses gestes. Chaque case porte
 * `data-tip` : survol à la souris, appui long de 380 ms au doigt (CA4). Les couleurs sont celles
 * des étapes (tokens `etape-*`) et ne changent pas en mode sombre (CA1b).
 */
export function CalendrierAnnee({ mois, moisCourant = null, frise = null, initiales = false, className = '' }) {
  const cases = casesCalendrier(mois, { moisCourant, frise })
  return (
    <div className={className}>
      <div className="cal-annee" role="img" aria-label={NOM_CALENDRIER}>
        {cases.map((c) => (
          <i key={c.i} data-tip={c.info} data-geste={c.cle || undefined}
            className={`${c.classe} ${c.courant ? 'maintenant' : ''}`} />
        ))}
      </div>
      {initiales && (
        <div className="cal-annee" aria-hidden="true">
          {INITIALES_MOIS.map((m, i) => <span key={i} className={i === moisCourant ? 'maintenant' : ''}>{m}</span>)}
        </div>
      )}
    </div>
  )
}

export default CalendrierAnnee
