import { useState } from 'react'
import { HelpCircle, ChevronDown } from 'lucide-react'
import { IconeEtape, PuceEtape } from './EtapeCulture.jsx'
import { entreesLegende } from '../../lib/etapes.js'

/**
 * Légende repliable commune [US-352 / CA7] : « ? Légende ⌄ » + « Appui long sur … : son étape ».
 * Dépliée : les puces d'étape (Levé et Planté fusionnés), le hachuré « prévu » et le point orange
 * « à confirmer ». `calendrier` ajoute « cadre = ce mois-ci » ; `sujet` dit ce qu'on presse.
 * Repliée par défaut sur toutes les tailles : une seule règle pour toutes les vues.
 */
export function LegendeCommune({ sujet = 'une pastille', calendrier = false, className = '' }) {
  const [ouverte, setOuverte] = useState(false)
  const puces = entreesLegende({ compact: true }).filter((e) => e.type === 'etape')
  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <button type="button" onClick={() => setOuverte((o) => !o)} aria-expanded={ouverte}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 text-[12.5px] font-semibold text-txt2">
          <HelpCircle size={15} aria-hidden="true" />Légende
          <ChevronDown size={14} aria-hidden="true" className={ouverte ? 'rotate-180' : ''} />
        </button>
        <span className="text-[11.5px] text-txt3">Appui long sur {sujet} : son étape</span>
      </div>
      {ouverte && (
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Légende des étapes">
          {puces.map((e) => (
            <li key={e.cle}>
              <span className={`puce-etape petite etape-${e.famille}`}>
                <IconeEtape etape={e.cle} taille={12} />{e.libelle}
              </span>
            </li>
          ))}
          <li><PuceEtape etape="levee" prevue petite /></li>
          <li>
            <span className="puce-etape petite text-txt2 bg-card-alt">
              <i className="inline-block w-[9px] h-[9px] rounded-full bg-due" aria-hidden="true" />à confirmer
            </span>
          </li>
          {calendrier && (
            <li>
              <span className="puce-etape petite bg-card text-txt" style={{ boxShadow: 'inset 0 0 0 1.5px var(--txt)' }}>
                cadre = ce mois-ci
              </span>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

export default LegendeCommune
