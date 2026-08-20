// [US-076] Écran « Tableau de bord — Vue d'ensemble » — portage partiel de
// `ScreenDashboard` (`web-screens.jsx`, maquette 2026, gel du 15/08/2026) :
// seul le widget météo consomme une donnée réelle (`GET /meteo`, US-075) ; les
// trois autres widgets de la maquette (à faire cette semaine, récoltes de la
// saison, dernières interventions) restent en `Placeholder` explicite tant que
// leurs données ne sont pas calculables côté backend (cf. §6 point ouvert n°1,
// docs/ANALYSE_REFONTE_UI_WEB_2026.md — Lot D, non cadré).
//
// [US-077] Chaque widget n'est rendu que s'il figure dans la préférence
// d'affichage locale (`useDashboardWidgets`) — mécanisme générique, un futur
// widget réel du Lot D n'a qu'à rejoindre `WIDGETS_CATALOGUE` pour en hériter.
//
// [US-078] Enrichissement de la carte météo : lever/coucher du soleil,
// libellés explicites humidité/vent, conseil potager du jour — les trois
// champs (`lever_soleil`, `coucher_soleil`, `conseil`) étaient déjà renvoyés
// par `GET /meteo` (US-075) sans être consommés ici.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Sun, MapPinned, CheckSquare, ShoppingBasket, ScrollText, Sunrise, Sunset } from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { useDashboardWidgets } from '../hooks/useDashboardWidgets.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import ModalModifierPotager from '../components/ModalModifierPotager.jsx'
import { Card, CardHead, Btn, Placeholder } from '../components/ui'

const JOUR_LABEL = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']

/**
 * [US-078 / CA3, CA4, CA5] Conseil potager du jour — hauteur figée à 3 lignes
 * (`line-clamp-3`) ; le lien « Afficher plus » n'apparaît que si le texte est
 * réellement tronqué (mesuré via `scrollHeight` vs `clientHeight`, pas déduit
 * d'un nombre de caractères qui varierait avec la largeur de carte).
 */
function ConseilPotager({ texte }) {
  const ref = useRef(null)
  const [ouvert, setOuvert] = useState(false)
  const [tronque, setTronque] = useState(false)

  useEffect(() => { setOuvert(false) }, [texte])

  useLayoutEffect(() => {
    if (!ouvert && ref.current) {
      setTronque(ref.current.scrollHeight > ref.current.clientHeight + 1)
    }
  }, [texte, ouvert])

  return (
    <div className="mt-3.5 pt-3.5 border-t border-border-soft">
      <p ref={ref} className={`text-[12.5px] text-txt2 leading-relaxed ${ouvert ? '' : 'line-clamp-3'}`}>
        {texte}
      </p>
      {tronque && !ouvert && (
        <button
          onClick={() => setOuvert(true)}
          className="text-[12px] font-semibold text-brand-text mt-1"
        >
          Afficher plus
        </button>
      )}
    </div>
  )
}

/**
 * [CA2, CA3, CA4] Carte météo — donnée réelle, invitation à localiser le
 * potager si `localisation_manquante` (US-075/CA4), ou erreur cohérente avec
 * le reste de l'application en cas d'échec (`ApiError`, US-059).
 */
function CarteMeteo({ meteo, loading, error, onRetry, onLocaliser }) {
  if (loading) return <LoadingSkeleton lines={2} />
  if (error) return <ApiError message={error} onRetry={onRetry} />

  if (meteo?.localisation_manquante) {
    return (
      <Card className="text-center" pad="px-5 py-8">
        <div className="w-12 h-12 rounded-2xl bg-brand-soft flex items-center justify-center mx-auto mb-3">
          <MapPinned size={22} className="text-brand" />
        </div>
        <div className="font-serif text-[16px] font-semibold text-txt">Localisation manquante</div>
        <p className="text-[13px] text-txt2 mt-1.5 max-w-[320px] mx-auto leading-relaxed">
          Renseignez la ville de ce potager pour afficher sa météo locale.
        </p>
        <Btn kind="soft" small className="mt-3.5" onClick={onLocaliser}>
          Modifier le potager
        </Btn>
      </Card>
    )
  }

  return (
    <Card>
      <CardHead icon={Sun} tint="amber" title={meteo.ville} sub={meteo.label} />
      <div className="flex items-baseline gap-2.5 flex-wrap">
        <span className="font-serif text-[40px] font-bold text-txt tracking-tight">
          {meteo.temp_actuelle ?? meteo.temp_max}°
        </span>
        <span className="text-[12.5px] text-txt3">
          ressenti {meteo.ressenti ?? '—'}° · Humidité : {meteo.humidite ?? '—'} % · Vent : {meteo.vent_actuel_kmh ?? '—'} km/h
        </span>
      </div>
      {/* [US-078 / CA1] `lever_soleil`/`coucher_soleil` — déjà exposés par `GET /meteo` (US-075) */}
      <div className="flex items-center gap-4 mt-2 text-[12px] text-txt3">
        <span className="inline-flex items-center gap-1.5">
          <Sunrise size={14} className="text-amber" />{meteo.lever_soleil}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Sunset size={14} className="text-amber" />{meteo.coucher_soleil}
        </span>
      </div>
      {meteo.conseil && <ConseilPotager texte={meteo.conseil} />}
      <div className="flex gap-2 mt-3.5">
        {meteo.previsions.map((p) => (
          <div key={p.date} className="flex-1 bg-card-alt rounded-[11px] py-2 px-1 text-center">
            <div className="text-[10px] font-bold text-txt3 tracking-wide uppercase">
              {JOUR_LABEL[new Date(`${p.date}T12:00:00`).getDay()]}
            </div>
            <div className="my-1.5 text-[18px] leading-none">{p.emoji}</div>
            <div className="text-[12.5px] font-bold text-txt">{p.temp_max}°</div>
            <div className="text-[11px] text-txt3">{p.temp_min}°</div>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default function Dashboard({ refresh }) {
  const { potagerActif } = usePotager()
  const { visible } = useDashboardWidgets()
  const afficheMeteo = visible.includes('meteo')

  const [meteo, setMeteo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [modaleLocalisation, setModaleLocalisation] = useState(false)

  async function chargerMeteo() {
    setLoading(true); setError(null)
    try { setMeteo(await api.meteo()) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  // Ne pas appeler l'API pour un widget masqué [US-077] — se redéclenche à sa
  // réapparition (dépendance sur `afficheMeteo`, pas seulement au montage).
  useEffect(() => { if (afficheMeteo) chargerMeteo() }, [refresh, afficheMeteo])

  return (
    <div className="@container/dash">
      <div className="grid gap-4 @[720px]/dash:grid-cols-2">
        {visible.includes('todo') && (
          <Placeholder
            icon={CheckSquare}
            title="À faire cette semaine"
            body="Liste des tâches de la semaine, dérivée du calendrier de vos cultures."
          />
        )}
        {afficheMeteo && (
          <CarteMeteo
            meteo={meteo}
            loading={loading}
            error={error}
            onRetry={chargerMeteo}
            onLocaliser={() => setModaleLocalisation(true)}
          />
        )}
        {visible.includes('recoltes') && (
          <Placeholder
            icon={ShoppingBasket}
            title="Récoltes de la saison"
            body="Suivi des récoltes pesées depuis le début de la saison."
          />
        )}
        {visible.includes('journal') && (
          <Placeholder
            icon={ScrollText}
            title="Dernières interventions"
            body="Vos dernières actions enregistrées dans le journal du potager."
          />
        )}
      </div>

      {modaleLocalisation && potagerActif && (
        <ModalModifierPotager potager={potagerActif} onClose={() => setModaleLocalisation(false)} />
      )}
    </div>
  )
}
