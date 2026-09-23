import { RangPlan } from './RangPlan.jsx'
import { palettePhases } from '../../lib/planVue.js'

function IconeIndicateur({ type }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      {type === 'surface' && <>
        <rect x="3.5" y="3.5" width="17" height="17" rx="2" />
        <path d="M3.5 9.5h17M3.5 14.5h17" strokeDasharray="2 2.5" />
      </>}
      {type === 'longueur' && <path d="M2 7v10M22 7v10M5 12h14M8 9l-3 3 3 3M16 9l3 3-3 3" />}
      {type === 'largeur' && <path d="M7 2h10M7 22h10M12 5v14M9 8l3-3 3 3M9 16l3 3 3-3" />}
      {type === 'rangs' && <path d="M3 5.5h18M3 12h18M3 18.5h18" strokeWidth="3" />}
    </svg>
  )
}

/**
 * La carte d'une parcelle dans la Vue plan [US-200 / V1, V8, V9, V10, V11].
 *
 * Une carte par parcelle, de largeur égale : pas d'aire proportionnelle, pas de
 * position, pas de forme. La hauteur vient du **nombre de rangs**, et d'eux
 * seuls (V2) — c'est ce qui rend lisible une petite planche comme une grande.
 *
 * Trois cas particuliers vivent ici, et une parcelle ne disparaît dans aucun :
 * la **pépinière** se compte en lots, pas en rangs (V8) ; la parcelle **sans
 * nombre de rangs** garde ses cultures et porte la mention du champ manquant
 * (V9) ; le **dépassement** affiche toutes les lignes et porte l'écart (V10).
 *
 * [CA4] `palette` et `taille` sont passées telles quelles aux rangs : l'onglet
 * Rotation et l'onglet Parcelles (US-222) reprendront cette carte sans la
 * modifier.
 */
export function CartePlanParcelle({
  carte,
  palette = palettePhases(),
  taille = 'normale',
  onRang = undefined,
  onFiche = undefined,
  onPepiniere = undefined,
}) {
  return (
    <section
      aria-label={`Parcelle ${carte.nom}`}
      // [V9] Sans nombre de rangs NI culture, la carte est en pointillé et ne
      // dessine rien — mais elle est là.
      className={`@container/carte min-w-0 rounded-xl border p-[18px] pb-2.5 ${
        carte.vide ? 'border-dashed border-txt3/60 bg-card' : 'border-border bg-card shadow-card'
      } ${carte.pepiniere ? 'trame-pepiniere border-dashed' : ''}`}
    >
      {/* [V11] En-tête : nom · superficie · rangs · sortie vers la fiche.
          Aucun pourcentage sur la carte (A3) : il est au pied de vue. */}
      <header className="flex flex-wrap items-baseline justify-between gap-2 mb-1.5">
        <h3 className="min-w-0 font-serif text-[18px] font-semibold text-txt [overflow-wrap:anywhere]">{carte.nom}</h3>
        <button
          type="button"
          onClick={onFiche}
          className="text-[13px] font-semibold underline text-txt2 whitespace-nowrap shrink-0
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
        >
          Fiche parcelle →
        </button>
      </header>

      <div className="text-[13px] text-txt2 mt-2 mb-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {carte.indicateurs.map(indicateur => (
          <span key={indicateur.cle} data-indicateur={indicateur.cle}
            title={indicateur.titre} aria-label={`${indicateur.titre} : ${indicateur.texte}`}
            className={`inline-flex items-center gap-1.5 min-w-0 ${indicateur.alerte ? 'text-red font-semibold' : indicateur.cle === 'rangs' && carte.depassement > 0 ? 'text-amber font-semibold' : ''}`}>
            <span className={indicateur.alerte ? 'text-red' : 'text-txt3'}><IconeIndicateur type={indicateur.cle} /></span>
            <span>{indicateur.texte.split(/(\d+(?:,\d+)?(?: m²| m)?)/).map((fragment, index) => (
              /^\d/.test(fragment) ? <strong key={index} className={`font-semibold ${indicateur.alerte ? '' : 'text-txt'}`}>{fragment}</strong> : fragment
            ))}</span>
          </span>
        ))}
        {carte.pepiniere && (
          <>
            {/* [V8] Ce qu'une pépinière sait dire d'elle-même : son type et ses
                lots en cours. Le type vient d'US-208 — « non renseigné » d'ici là. */}
            <span>pépinière {carte.typePepiniere}</span>
            <span>{carte.nbLots} lot{carte.nbLots > 1 ? 's' : ''} en cours</span>
          </>
        )}
      </div>

      {carte.mentionLongueur && (
        <p className="text-[12.5px] text-txt2 bg-card-alt rounded-lg px-2.5 py-2 mb-2 [overflow-wrap:anywhere]">
          {carte.mentionLongueur}. <em className="text-txt">{carte.phraseLongueur}</em>
        </p>
      )}

      {carte.mention && (
        <p className="text-[12.5px] text-txt2 bg-card-alt rounded-lg px-2.5 py-2 mb-2 [overflow-wrap:anywhere]">
          {carte.mention}. <em className="text-txt">{carte.phrase}</em>
        </p>
      )}

      {/* [V8] La pépinière n'affiche aucun rang de semis : ses semis sont des
          lots, qui se lisent ailleurs. Une PLANTATION qui y a été faite reste
          dessinée en rang, sous le compte des lots. */}
      {carte.pepiniere && (
        <button
          type="button"
          onClick={onPepiniere}
          className="text-[10.5px] font-bold underline text-txt2 mb-1.5
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
        >
          Voir Pépinière →
        </button>
      )}

      {/* [V2] Un rang = une ligne, du rang 1 au dernier. */}
      {carte.rangs.length > 0 && (
        <div className="flex flex-col divide-y divide-border-soft">
          {carte.rangs.map((rang) => (
            <RangPlan
              key={rang.numero}
              rang={rang}
              palette={palette}
              taille={taille}
              onSelect={onRang ? () => onRang(rang) : undefined}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default CartePlanParcelle
