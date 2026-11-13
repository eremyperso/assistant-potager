// [US-328] Le panneau de droite du Plan, sans sélection : « Aujourd'hui au potager ».
//
// A1 en-tête (date, température, alerte gel), A2 « À confirmer », A3 « À libérer », A4 « À placer »,
// A5 l'aide. Les listes viennent du serveur et se mettent en forme dans `lib/aujourdhui.js` ;
// ce composant n'en recompte aucune.
//
// [CA4] Glisser une carte « À placer » sur un rang libre du plan ouvre Gaston avec la proposition ;
// au clavier, Entrée sur la carte la « prend en main » (annoncé), puis Entrée sur un rang libre.
// Le glisser et la prise en main sont tenus par l'écran Plan (`carteEnMain`), qui connaît les rangs.
import { CloudSnow, Thermometer } from 'lucide-react'
import {
  TITRE_AUJOURDHUI, AIDE_AUJOURDHUI, AIDE_CLAVIER, LISTES, LISTE_A_PLACER, dateDuJour,
} from '../lib/aujourdhui.js'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'

/** A2 / A3 : une culture ; la toucher ouvre son suivi (US-322). */
function LigneTache({ ligne, onOuvrir }) {
  return (
    <li>
      <button type="button" aria-label={ligne.nomAccessible} onClick={() => onOuvrir?.(ligne.selection)}
        className={`flex w-full min-h-[44px] items-center gap-2.5 rounded-[10px] border border-border bg-card px-3 py-2
                    text-left hover:border-brand ${FOCUS}`}>
        <span aria-hidden="true" className="text-[18px] leading-none">{ligne.emoji}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13.5px] font-semibold text-txt">{ligne.nom}</span>
          <span className="block truncate text-[12px] text-txt2">
            {[ligne.lieu, ligne.detail].filter(Boolean).join(' · ')}
          </span>
        </span>
        <span aria-hidden="true"
          className="etape-pastille-texte shrink-0 rounded-full border border-dashed border-current px-2 py-0.5 text-[11px] font-bold">
          {ligne.pastille}
        </span>
      </button>
    </li>
  )
}

/** A4 : une carte à placer, à glisser sur un rang libre — ou à prendre au clavier. */
function CarteAPlacer({ carte, enMain, onPrendre, onGlisser, onLacher }) {
  return (
    <li>
      <button type="button" draggable="true" aria-pressed={enMain ? 'true' : 'false'}
        aria-label={carte.nomAccessible} aria-describedby="aide-placer"
        onClick={() => onPrendre?.(enMain ? null : carte)}
        onDragStart={(e) => {
          try { e.dataTransfer.setData('text/plain', carte.cle); e.dataTransfer.effectAllowed = 'move' } catch { /* jsdom */ }
          onGlisser?.(carte)
        }}
        onDragEnd={() => onLacher?.()}
        className={`flex w-full min-h-[44px] cursor-grab items-center gap-2.5 rounded-[10px] border-[1.5px] border-dashed px-3 py-2
                    text-left active:cursor-grabbing ${FOCUS}
                    ${enMain ? 'border-brand bg-brand-soft' : 'border-border bg-card hover:border-brand'}`}>
        <span aria-hidden="true" className="text-[18px] leading-none">{carte.emoji}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13.5px] font-semibold text-txt">
            {carte.nom}{carte.variete && <span className="font-normal text-txt2"> {carte.variete}</span>}
          </span>
          <span className="block truncate text-[12px] text-txt2">
            {[carte.quantite, carte.origine].filter(Boolean).join(' · ')}
          </span>
        </span>
      </button>
    </li>
  )
}

/**
 * [CA1] Le panneau entier. `taches` : sortie de `tachesDuPlan` ; `meteo` : sortie de
 * `meteoDuJour` ou null (la ligne disparaît, CA6).
 */
export default function AujourdhuiPotager({
  taches, meteo, dateRef, carteEnMain, onOuvrir, onPrendre, onGlisser, onLacher,
}) {
  return (
    <div className="flex flex-col gap-4 text-[13px] text-txt2">
      {/* A1 */}
      <header>
        <h3 className="font-serif text-[19px] font-semibold text-txt">{TITRE_AUJOURDHUI}</h3>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12.5px]">
          <span className="first-letter:uppercase">{dateDuJour(dateRef)}</span>
          {meteo?.temperature && (
            <span className="inline-flex items-center gap-1">
              <Thermometer size={13} aria-hidden="true" />{meteo.temperature}
            </span>
          )}
          {meteo?.alerte && (
            <span className="inline-flex items-center gap-1 font-semibold etape-pastille-texte">
              <CloudSnow size={13} aria-hidden="true" />{meteo.alerte}
            </span>
          )}
        </p>
      </header>

      {/* A2, A3, A4 */}
      {LISTES.map(({ cle, titre, vide }) => {
        const liste = taches?.[cle] || []
        return (
          <section key={cle} aria-label={`${titre} : ${liste.length}`}>
            <h4 className="mb-2 text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2">
              {titre} · {liste.length}
            </h4>
            {liste.length === 0 ? (
              <p className="text-[12.5px] text-txt3">{vide}</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {cle === LISTE_A_PLACER
                  ? liste.map((c) => (
                    <CarteAPlacer key={c.cle} carte={c} enMain={carteEnMain?.cle === c.cle}
                      onPrendre={onPrendre} onGlisser={onGlisser} onLacher={onLacher} />
                  ))
                  : liste.map((l) => <LigneTache key={l.cle} ligne={l} onOuvrir={onOuvrir} />)}
              </ul>
            )}
          </section>
        )
      })}

      {/* A5 */}
      <p id="aide-placer" className="text-[12px] text-txt3">
        {AIDE_AUJOURDHUI} <span className="sr-only">{AIDE_CLAVIER}</span>
      </p>
    </div>
  )
}
