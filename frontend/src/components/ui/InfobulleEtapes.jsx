import { useEffect, useState } from 'react'
import {
  creerAppuiLong, texteInfobulle, positionBulle, ATTRIBUT_INFOBULLE,
} from '../../lib/infobulle.js'

/**
 * Infobulle d'étape [US-352 / CA4], montée UNE fois pour toute l'application : tout élément qui
 * porte `data-tip` (pastille, rang du plan, case du calendrier) affiche son texte
 *  - au survol à la souris ;
 *  - à l'appui long de 380 ms au doigt (le clic qui suit est avalé : un appui long n'ouvre pas ce
 *    qui est dessous) ; un doigt qui défile n'est pas un appui long.
 * Rend `null` tant qu'aucune bulle n'est affichée. Position `fixed` : jamais rognée par un parent.
 */
export function InfobulleEtapes() {
  const [bulle, setBulle] = useState(null)

  useEffect(() => {
    let cibleCourante = null
    const montrer = (cible) => {
      const texte = texteInfobulle(cible)
      if (!texte) return
      const porteur = cible.closest(`[${ATTRIBUT_INFOBULLE}]`)
      porteur.classList.add('infobulle-cible')
      cibleCourante = porteur
      const pos = positionBulle(porteur.getBoundingClientRect(), {
        largeurBulle: Math.min(texte.length * 6.6 + 18, 320), largeurEcran: window.innerWidth,
      })
      setBulle({ texte, ...pos })
    }
    const cacher = () => {
      cibleCourante?.classList.remove('infobulle-cible')
      cibleCourante = null
      setBulle(null)
    }
    const appuiLong = creerAppuiLong({ surDeclenche: (cible) => montrer(cible), surFin: cacher })

    const surPointeurBas = (e) => {
      if (e.pointerType === 'mouse') return
      appuiLong.debut(e.target.closest?.(`[${ATTRIBUT_INFOBULLE}]`), e.clientX, e.clientY)
    }
    const surPointeurBouge = (e) => { if (e.pointerType !== 'mouse') appuiLong.deplacement(e.clientX, e.clientY) }
    const surPointeurFin = (e) => { if (e.pointerType !== 'mouse') appuiLong.fin() }
    const surEntree = (e) => {
      if (e.pointerType !== 'mouse') return
      if (e.target.closest?.(`[${ATTRIBUT_INFOBULLE}]`)) montrer(e.target)
    }
    const surSortie = (e) => {
      if (e.pointerType !== 'mouse') return
      if (e.target.closest?.(`[${ATTRIBUT_INFOBULLE}]`)) cacher()
    }
    // Un appui long ne doit rien ouvrir : le clic et le menu contextuel qui suivent sont avalés.
    const surClic = (e) => {
      if (!appuiLong.avaleLeClic()) return
      e.preventDefault()
      e.stopPropagation()
    }
    const surMenu = (e) => { if (appuiLong.actif && e.target.closest?.(`[${ATTRIBUT_INFOBULLE}]`)) e.preventDefault() }

    document.addEventListener('pointerdown', surPointeurBas, true)
    document.addEventListener('pointermove', surPointeurBouge, true)
    document.addEventListener('pointerup', surPointeurFin, true)
    document.addEventListener('pointercancel', surPointeurFin, true)
    document.addEventListener('pointerover', surEntree, true)
    document.addEventListener('pointerout', surSortie, true)
    document.addEventListener('click', surClic, true)
    document.addEventListener('contextmenu', surMenu, true)
    return () => {
      document.removeEventListener('pointerdown', surPointeurBas, true)
      document.removeEventListener('pointermove', surPointeurBouge, true)
      document.removeEventListener('pointerup', surPointeurFin, true)
      document.removeEventListener('pointercancel', surPointeurFin, true)
      document.removeEventListener('pointerover', surEntree, true)
      document.removeEventListener('pointerout', surSortie, true)
      document.removeEventListener('click', surClic, true)
      document.removeEventListener('contextmenu', surMenu, true)
      cacher()
    }
  }, [])

  if (!bulle) return null
  return (
    <div role="tooltip" className="infobulle-etape" style={{ left: bulle.x, top: bulle.y }}>
      {bulle.texte}
    </div>
  )
}

export default InfobulleEtapes
