// ── Bandeau d'indicateurs (3 zones fixes) ─────────────────────────────────────
// [US-059 CA2] Chaque zone est une tuile `Stat` du design system : le bandeau ne
// redéfinit plus son propre habillage, il ne fait qu'agencer des tuiles.
//
// Le découpage occupe toujours `slots` zones égales (3 par défaut), même si
// `metrics` en fournit moins : les zones restantes sont laissées vides, prêtes
// à accueillir un futur indicateur sans changer la mise en page.
//
// [US-059 CA4] `@container/strip` : la répartition en colonnes suit la largeur du
// bandeau, pas celle de l'écran — un conteneur plus étroit que 20rem empile les
// tuiles au lieu de les écraser.
import { Stat } from './ui'

/** Classes écrites en entier : Tailwind ne peut pas les composer à l'exécution. */
const COLONNES = {
  1: '@[20rem]/strip:grid-cols-1',
  2: '@[20rem]/strip:grid-cols-2',
  3: '@[20rem]/strip:grid-cols-3',
  4: '@[20rem]/strip:grid-cols-4',
}

// [US-059 CA5] Les quatre écrans passent encore la couleur du chiffre sous forme
// de couleur CSS. Elle est relayée telle quelle à `Stat` via `valueColor`, sans
// que le bandeau ait à connaître les anciens alias : leurs paramètres restent
// inchangés, et ils passeront `tone` quand leur propre US les migrera.
export default function MetricStrip({ metrics, slots = 3, className = '' }) {
  const items = [...metrics]
  while (items.length < slots) items.push(null)

  return (
    <div className={`@container/strip mb-3 ${className}`}>
      <div className={`grid grid-cols-1 gap-2 ${COLONNES[slots] ?? COLONNES[3]}`}>
        {items.map((m, i) =>
          m ? (
            <Stat
              key={m.label}
              value={m.value}
              unit={m.unit}
              label={m.label}
              icon={m.icon}
              tint={m.tint}
              tip={m.tip}
              tone={m.tone}
              valueColor={m.color}
            />
          ) : (
            <div key={`empty-${i}`} aria-hidden="true" />
          )
        )}
      </div>
    </div>
  )
}
