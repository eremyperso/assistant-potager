import { Mic, Pencil } from 'lucide-react'
import { NOTER } from '../navigation.js'
import { useNotifier } from '../context/NotificationsContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { peutEnregistrer } from '../lib/gestes.js'
import { libellePastille } from '../lib/compagnon.js'
import { ouvrirGastonAvec, pastilleNoter, TEXTE_PEPINIERE_NOTER } from '../lib/contexteCompagnon.js'
import { DECALAGE_NOTER_PX } from '../lib/coquille.js'

/**
 * Noter [US-353 / CA2, CA3] : le SEUL bouton rond pour parler à Gaston (le médaillon flottant est
 * supprimé, D5). Le même rond sert deux places :
 *  - `barre` : au centre de la barre basse mobile (62 px, il déborde de 30 px) ;
 *  - `bureau` : en bas à droite sur ordinateur, décalé à gauche du panneau quand il est ouvert, et
 *    absent tant que Gaston est ouvert (`gastonOuvert`).
 *
 * Sa pastille de 24 px montre ce qui sera noté : l'emoji de la culture sélectionnée ou ouverte,
 * sinon le micro. Le compteur de messages non lus (US-272) s'y pose. Noter est une ACTION, jamais
 * l'onglet courant ; un membre en lecture seule ne l'a pas (US-324 / CA9).
 */
export default function BoutonNoter({
  variante = 'barre', selection = null, nonLus = 0, panneauOuvert = false, gastonOuvert = false, onGo,
}) {
  const { notifier } = useNotifier()
  const { potagerActif } = usePotager()
  if (!peutEnregistrer(potagerActif?.role)) return null
  if (variante === 'bureau' && gastonOuvert) return null

  const pastille = pastilleNoter(selection)
  const compteur = libellePastille(nonLus)

  const noter = () => {
    if (pastille.sorte === 'pepiniere') {
      // [US-325] Sur une parcelle pépinière : les lots se notent dans Ma pépinière.
      notifier({ tone: 'blue', titre: TEXTE_PEPINIERE_NOTER, cle: 'noter-pepiniere' })
      onGo?.('pepiniere')
      return
    }
    ouvrirGastonAvec(selection)
  }

  const aria = `${NOTER.label}${nonLus > 0 ? ` (${nonLus} message${nonLus > 1 ? 's' : ''} non lu${nonLus > 1 ? 's' : ''})` : ''}`
  const rond = (
    <button
      type="button" onClick={noter} aria-label={aria} title={NOTER.label} data-noter={variante}
      className={`noter-rond ${variante === 'bureau' ? 'bureau' : ''} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand`}
    >
      <Pencil strokeWidth={2.2} aria-hidden="true" />
      <span className="noter-pastille" aria-hidden="true" data-pastille={pastille.sorte}>
        {pastille.emoji || <Mic strokeWidth={2.4} />}
        {compteur && <span className="noter-nonlus" role="status">{compteur}</span>}
      </span>
    </button>
  )

  if (variante === 'bureau') {
    return (
      <div
        className="fixed bottom-[26px] z-20 flex flex-col items-center gap-[5px] text-[12px] font-bold text-brand-text transition-[right] duration-200"
        style={{ right: panneauOuvert ? DECALAGE_NOTER_PX : 28 }}
      >
        {rond}
        {NOTER.shortLabel}
      </div>
    )
  }
  return (
    <div className="flex flex-1 flex-col items-center gap-[3px] text-[10.5px] font-bold text-brand-text">
      {rond}
      {NOTER.shortLabel}
    </div>
  )
}
