import { Calendar, Search, SlidersHorizontal } from 'lucide-react'
import { useDateRef } from '../context/AppContext.jsx'
import { boutonDate } from '../lib/coquille.js'
import MenuVue from './MenuVue.jsx'

/**
 * Barre d'outils [US-353 / CA8] : toujours dans cet ordre, contrôles de 40 px — bouton date, champ
 * de recherche (texte indicatif propre à la vue), **Filtrer** avec le compteur de filtres actifs,
 * menu **⋯**. Une vue peut retirer la date ou Filtrer ; rien ne s'y ajoute.
 *
 * `barre` est celle que rend `barreEffective` (`lib/coquille.js`) : la vue déclare ses contrôles, la
 * coquille les pose. Sous 520 px de CONTENEUR (container query sur le conteneur `page`, pas sur
 * l'écran), Filtrer se réduit à son icône et son compteur passe en coin.
 *
 * [CA10] « Aujourd'hui » ouvre `RegleTemps` juste dessous ; quand on regarde un autre jour, le
 * bouton passe en ambre avec la date courte (« 12 nov. »).
 */
export default function BarreOutils({ barre }) {
  const { dateRef, regleOuverte, setRegleOuverte } = useDateRef()
  if (!barre) return null
  const date = boutonDate(dateRef)
  const { recherche, filtre, menu } = barre

  return (
    <div role="toolbar" aria-label="Barre d’outils de la vue" className="relative flex items-center gap-2">
      {barre.date && (
        <button
          type="button" onClick={() => setRegleOuverte(!regleOuverte)}
          aria-expanded={regleOuverte} aria-label={date.ambre ? `Date de lecture : ${date.libelle}` : 'Date : aujourd’hui'}
          className={`inline-flex h-10 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border px-[11px] text-[13px] font-semibold ${
            date.ambre
              ? 'border-amb-bd bg-amb-bg text-amb-tx'
              : `bg-surface text-txt ${regleOuverte ? 'border-brand shadow-[0_0_0_1px_var(--brand)]' : 'border-border'}`
          }`}
        >
          <Calendar size={16} className={date.ambre ? 'text-amb-tx' : 'text-txt2'} aria-hidden="true" />
          {date.libelle}
        </button>
      )}

      {recherche && (
        <label className="flex h-10 min-w-0 flex-1 items-center gap-[7px] overflow-hidden rounded-xl border border-border bg-surface px-[11px] text-[13px] text-txt">
          <Search size={16} className="shrink-0 text-txt3" aria-hidden="true" />
          <input
            type="search" value={recherche.valeur ?? ''} onChange={(e) => recherche.onChange?.(e.target.value)}
            placeholder={recherche.placeholder || 'Rechercher'} aria-label={recherche.placeholder || 'Rechercher'}
            className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-txt3"
          />
        </label>
      )}
      {!recherche && <span className="flex-1" aria-hidden="true" />}

      {filtre && (
        <button
          type="button" onClick={filtre.onOuvrir}
          aria-label={filtre.nombre ? `Filtrer, ${filtre.nombre} actif${filtre.nombre > 1 ? 's' : ''}` : 'Filtrer'}
          className="relative inline-flex h-10 w-10 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border border-border bg-surface text-[13px] font-semibold text-txt @[520px]/page:w-auto @[520px]/page:px-[11px]"
        >
          <SlidersHorizontal size={16} className="text-txt2" aria-hidden="true" />
          <span className="hidden @[520px]/page:inline">Filtrer</span>
          {filtre.nombre > 0 && (
            <span className="absolute -right-[5px] -top-[5px] grid h-[18px] min-w-[18px] place-items-center rounded-[9px] bg-brand px-[5px] text-[11px] text-white @[520px]/page:static">
              {filtre.nombre}
            </span>
          )}
        </button>
      )}

      <MenuVue menu={menu} />
    </div>
  )
}
