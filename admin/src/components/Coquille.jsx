import { useEffect, useState } from 'react'
import { LogOut, Moon, Sun } from 'lucide-react'
import { NavigationBandeau, BarreBasse } from './Navigation.jsx'
import BarreOutils from './BarreOutils.jsx'
import Logo from './Logo.jsx'
import { heure } from '../lib/format.js'
import { pourListeDeModeles } from '../lib/filtres.js'
import { environnement } from '../config.js'
import { useTheme } from '../hooks/useTheme.js'

/** Les modèles réellement appelés sur la période, pour le filtre de modèle. */
function useModeles(client, filtres) {
  const [modeles, setModeles] = useState([])
  const cle = JSON.stringify([filtres.periode, filtres.depuis, filtres.jusqu_a])
  useEffect(() => {
    let actif = true
    client.appeler('/admin/pilotage/ventilation', {
      dimension: 'modele', limite: 100, mesure: 'appels', ...pourListeDeModeles(filtres),
    })
      .then((corps) => { if (actif) setModeles(corps.lignes.map((l) => l.cle).filter((c) => typeof c === 'string' && c !== '(aucun)')) })
      .catch(() => { /* la liste reste celle d'avant : le filtre libre reste possible */ })
    return () => { actif = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, cle])
  return modeles
}

/**
 * La coquille commune à toutes les vues [US-311 / CA4, CA5], d'après la maquette d'US-318 :
 * bandeau (logo, nom, environnement, navigation dès 900 px, heure de mise à jour, thème), barre
 * d'outils (période, filtres, rafraîchir), contenu, barre d'onglets basse sous 900 px.
 */
export default function Coquille({ client, compte, vue, filtres, majTexte, enPanne, surVue, surFiltres, surRafraichir, surDeconnexion, alertesOuvertes = 0, children }) {
  const { theme, basculer } = useTheme()
  const env = environnement()
  const modeles = useModeles(client, filtres)
  const bouton = 'grid h-9 w-9 place-items-center rounded-[10px] text-header-txt hover:bg-header-glass'

  return (
    // La coquille tient dans l'écran, à toutes les tailles : bandeau, barre d'outils (et barre
    // d'onglets basse sous 900 px) restent fixes, seul le contenu défile. `dvh` : la hauteur visible
    // réelle sur mobile, barre d'adresse comprise.
    <div className="coquille-pilotage relative flex h-dvh flex-col overflow-hidden bg-bg text-txt">
      <header className="shrink-0 bg-gradient-to-r from-header-from to-header-to text-header-txt">
        <div className="flex h-[58px] items-center gap-3 px-4 nav:px-6">
          <span className="flex items-center gap-[9px]">
            <Logo />
            <h1 className="font-serif text-lg font-bold leading-none">Pilotage</h1>
            <span aria-label={`Environnement : ${env === 'prod' ? 'production' : 'développement'}`}
              className="rounded-full border border-white/35 bg-header-glass px-[7px] py-0.5 text-[10.5px] font-extrabold uppercase tracking-[.06em]">{env}</span>
          </span>
          <NavigationBandeau vue={vue} surChangement={surVue} alertesOuvertes={alertesOuvertes} />
          <span className="ml-auto flex items-center gap-1.5 whitespace-nowrap text-xs text-header-dim">
            <span className="hidden tab:inline">{majTexte}</span>
            <button type="button" onClick={basculer} aria-label="Basculer le thème" className={bouton}>
              {theme === 'dark' ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
            </button>
            <button type="button" onClick={surDeconnexion} aria-label={`Se déconnecter (${compte?.email || 'compte'})`} className={bouton}>
              <LogOut size={17} aria-hidden="true" />
            </button>
          </span>
        </div>
      </header>

      <BarreOutils filtres={filtres} modeles={modeles} surFiltres={surFiltres} majTexte={majTexte} enPanne={enPanne} surRafraichir={surRafraichir} />

      {/* `relative` est indispensable : sans parent positionné, un élément absolu du contenu (les
          textes `sr-only` de ChiffreCle, GrilleChaleur…) se place par rapport à la page, la rallonge
          bien au-delà de l'écran, et le doigt fait alors défiler TOUTE la coquille au lieu du contenu. */}
      <div className="relative flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain">
        <main className="mx-auto flex w-full flex-1 flex-col gap-3 px-3 pb-6 pt-3.5 tab:gap-3.5 tab:px-5 tab:pb-7 tab:pt-[18px] nav:max-w-[1232px] nav:px-6 nav:pb-8 nav:pt-5">
          {children}
        </main>
      </div>

      <BarreBasse vue={vue} surChangement={surVue} alertesOuvertes={alertesOuvertes} />
    </div>
  )
}

/** « mis à jour à 14 h 32 » — l'heure de la dernière lecture réussie ; en panne, « données de 14 h 32 ». */
export function texteMiseAJour(maj) {
  if (maj?.enPanne) return maj.a ? `données de ${heure(maj.a)}` : 'API indisponible'
  if (!maj?.a) return 'Chargement…'
  return `mis à jour à ${heure(maj.a)}`
}
