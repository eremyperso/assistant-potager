import { EyeOff } from 'lucide-react'
import { PROVENANCES, TOUTES_LES_PROVENANCES, perimetreParDefaut } from '../lib/filtres.js'

/** Rappel de périmètre [US-312 / CA7], discret et toujours visible : par défaut seules les
 *  provenances `usage` et `fond` sont comptées. Hors défaut, il dit ce qui est compté à la place. */
export default function RappelPerimetre({ filtres, surChangement }) {
  const parDefaut = perimetreParDefaut(filtres)
  const libelles = filtres.provenance.map((id) => PROVENANCES.find((p) => p.id === id)?.libelle.toLowerCase() || id)
  const lien = 'font-bold text-brand-text underline underline-offset-2'
  return (
    <p className="flex items-center gap-2 text-[12.5px] text-txt2" role="note">
      <EyeOff size={15} className="shrink-0" aria-hidden="true" />
      {parDefaut ? (
        <span>Usage réel uniquement — mesures et tests masqués · {' '}
          <button type="button" className={lien} onClick={() => surChangement({ ...filtres, provenance: [...TOUTES_LES_PROVENANCES] })}>Afficher</button>
        </span>
      ) : (
        <span>Provenances comptées : {libelles.join(', ')} · {' '}
          <button type="button" className={lien} onClick={() => surChangement({ ...filtres, provenance: [] })}>Revenir à l'usage réel</button>
        </span>
      )}
    </p>
  )
}
