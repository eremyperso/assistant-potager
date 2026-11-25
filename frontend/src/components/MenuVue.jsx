import { useEffect, useRef, useState } from 'react'
import { MoreHorizontal, Download, FileJson, HelpCircle } from 'lucide-react'
import { entreesMenu } from '../lib/coquille.js'

const ICONES = { csv: Download, json: FileJson, aide: HelpCircle }

/**
 * Menu ⋯ de la vue [US-353 / CA9] : Exporter en CSV, Exporter en JSON, un séparateur, Aide de la
 * vue. Chaque entrée n'apparaît que si la vue la fournit (`menu` : `{ exporterCsv, exporterJson,
 * aide }`) ; « Pièces jointes » est supprimé pour l'instant (D10). Sans aucune entrée, rien n'est
 * rendu. Se ferme à un appui ailleurs, à Échap, et après le choix d'une entrée.
 */
export default function MenuVue({ menu }) {
  const entrees = entreesMenu(menu)
  const [ouvert, setOuvert] = useState(false)
  const racine = useRef(null)

  useEffect(() => {
    if (!ouvert) return undefined
    const dehors = (e) => { if (!racine.current?.contains(e.target)) setOuvert(false) }
    const echap = (e) => { if (e.key === 'Escape') setOuvert(false) }
    document.addEventListener('pointerdown', dehors)
    document.addEventListener('keydown', echap)
    return () => {
      document.removeEventListener('pointerdown', dehors)
      document.removeEventListener('keydown', echap)
    }
  }, [ouvert])

  if (!entrees.length) return null
  return (
    <div ref={racine} className="relative shrink-0">
      <button
        type="button" onClick={() => setOuvert((o) => !o)} aria-label="Plus d’options"
        aria-haspopup="menu" aria-expanded={ouvert}
        className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-txt2"
      >
        <MoreHorizontal size={16} aria-hidden="true" />
      </button>
      {ouvert && (
        <div role="menu" className="absolute right-0 top-[46px] z-30 w-[220px] rounded-xl border border-border bg-surface p-1.5 shadow-[0_10px_28px_rgba(22,33,12,.16)]">
          {entrees.map((e) => {
            if (e.id === 'separateur') return <hr key="sep" className="my-1 border-0 border-t border-border-soft" />
            const Icone = ICONES[e.id]
            return (
              <button
                key={e.id} type="button" role="menuitem"
                onClick={() => { setOuvert(false); e.action() }}
                className="flex min-h-[40px] w-full items-center gap-2.5 rounded-lg px-2.5 text-left text-[13px] text-txt hover:bg-card-alt"
              >
                <Icone size={16} className="text-txt2" aria-hidden="true" />{e.libelle}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
