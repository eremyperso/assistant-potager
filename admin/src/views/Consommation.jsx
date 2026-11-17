import { useCallback, useMemo, useState } from 'react'
import { BarChart3, CloudOff, Table2 } from 'lucide-react'
import ChiffreCle from '../components/ChiffreCle.jsx'
import Graphique from '../components/Graphique.jsx'
import TableauVentilation from '../components/TableauVentilation.jsx'
import BlocAudio from '../components/BlocAudio.jsx'
import RappelPerimetre from '../components/RappelPerimetre.jsx'
import { useDonnees } from '../hooks/useDonnees.js'
import { bornes, estVueDuJour } from '../lib/periode.js'
import { versParametresApi } from '../lib/filtres.js'
import { heure, jourBref } from '../lib/format.js'
import {
  DIMENSIONS, blocAudio, chiffresCles, lignesTableau, modeleGraphique, periodeSansAppel, tableauGraphique,
} from '../lib/consommation.js'

const RACINE = '/admin/pilotage'

/** Les cinq lectures de la vue, en parallèle. Rien ici n'additionne : ce que l'écran montre est
 *  ce que rendent les routes d'agrégats [US-312 / CA10]. */
async function lire(client, parametres, dimension) {
  const [synthese, serieEntree, serieCache, parType, parModele] = await Promise.all([
    client.appeler(`${RACINE}/synthese`, parametres),
    client.appeler(`${RACINE}/series`, { ...parametres, mesure: 'jetons_entree', dimension }),
    client.appeler(`${RACINE}/series`, { ...parametres, mesure: 'jetons_cache' }),
    client.appeler(`${RACINE}/ventilation`, { ...parametres, dimension: 'appel_type', mesure: 'jetons_entree', limite: 20 }),
    client.appeler(`${RACINE}/ventilation`, { ...parametres, dimension: 'modele', mesure: 'jetons_entree', limite: 20 }),
  ])
  return { synthese, serieEntree, serieCache, parType, parModele }
}

/** « 7 derniers jours », « Aujourd'hui, pas horaire », « du 1 nov. au 9 nov. ». */
function libellePeriode(filtres, pas) {
  if (pas === 'heure') return "Aujourd'hui, pas horaire"
  if (filtres.periode === 'perso') { const b = bornes(filtres); return `du ${jourBref(b.depuis)} au ${jourBref(b.jusqu_a)}` }
  return `${filtres.periode.replace('j', '')} derniers jours`
}

const SEG = 'flex max-w-full gap-[3px] overflow-x-auto rounded-[10px] bg-card-alt p-[3px]'
const SEG_BTN = (actif) => `min-h-[34px] whitespace-nowrap rounded-lg px-[11px] py-[7px] text-[12.5px] font-semibold ${actif ? 'bg-card text-txt shadow-[0_1px_3px_rgba(0,0,0,.12)]' : 'text-txt2'}`

export default function Consommation({ client, filtres, declencheur, signalerMaj, surFiltres }) {
  const [dimension, setDimension] = useState('')
  const [enTableau, setEnTableau] = useState(false)

  const parametres = useMemo(() => versParametresApi(filtres), [filtres])
  const charger = useCallback(() => lire(client, parametres, dimension), [client, parametres, dimension])
  const { donnees, misAJour, erreur, enCours } = useDonnees(charger, {
    cle: JSON.stringify([parametres, dimension]), periode: filtres.periode, declencheur, surMiseAJour: signalerMaj,
  })

  if (!donnees) {
    if (erreur) return <Panne erreur={erreur} />
    return <p className="py-10 text-center text-sm text-txt2" role="status">Chargement des chiffres…</p>
  }

  const { synthese, serieEntree, serieCache, parType, parModele } = donnees
  const ancien = Boolean(erreur)
  const hhmm = misAJour ? heure(misAJour) : ''
  const cles = chiffresCles(synthese)
  const vide = periodeSansAppel(synthese)
  const graphique = modeleGraphique(serieEntree, serieCache, dimension)
  const precedente = `${jourBref(synthese.periode_precedente.depuis)} – ${jourBref(synthese.periode_precedente.jusqu_a)}`
  const horaire = graphique.pas === 'heure'
  const titre = `Jetons d'entrée par ${horaire ? 'heure' : 'jour'}`
  const dimensionLibelle = DIMENSIONS.find((d) => d.id === dimension)?.libelle.toLowerCase()

  const corps = (
    <>
      <RappelPerimetre filtres={filtres} surChangement={surFiltres} />

      <section aria-label="Chiffres clés">
        <ul className="grid grid-cols-2 gap-2 tab:grid-cols-3 nav:grid-cols-5">
          {cles.map((c) => (
            <li key={c.id} className="last:odd:col-span-2 tab:last:odd:col-auto">
              <ChiffreCle libelle={c.libelle} texte={c.texte} ecart={c.ecart} periodePrecedente={precedente}
                vide={vide} ancien={ancien ? hhmm : ''} />
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Graphique" className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
        <div className="mb-2.5 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div>
            <h2 className="font-serif text-base font-semibold leading-tight text-txt">{titre}</h2>
            <p className="mt-0.5 text-xs text-txt2">{libellePeriode(filtres, graphique.pas)} · ventilation : {dimensionLibelle}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Ventiler par" className={SEG}>
              {DIMENSIONS.map((d) => (
                <button key={d.id || 'cache'} type="button" aria-pressed={dimension === d.id} onClick={() => setDimension(d.id)} className={SEG_BTN(dimension === d.id)}>
                  {d.libelle}
                </button>
              ))}
            </div>
            <button type="button" aria-pressed={enTableau} onClick={() => setEnTableau((v) => !v)}
              className="flex min-h-[34px] items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 text-[12.5px] font-semibold text-txt">
              {enTableau ? <BarChart3 size={15} aria-hidden="true" /> : <Table2 size={15} aria-hidden="true" />}
              {enTableau ? 'Voir le graphique' : 'Voir en tableau'}
            </button>
          </div>
        </div>

        {vide ? (
          <div className="flex min-h-[190px] flex-col items-center justify-center gap-1.5 px-3 py-[22px] text-center text-[13px] text-txt2">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-card-alt text-txt3"><BarChart3 size={22} aria-hidden="true" /></span>
            <b className="text-sm text-txt">{estVueDuJour(filtres.periode) ? "Aucun appel aujourd'hui" : 'Aucun appel sur la période'}</b>
            <span>Le graphique se remplira au premier appel.</span>
          </div>
        ) : enTableau ? (
          <TableGraphique modele={graphique} />
        ) : (
          <Graphique modele={graphique} titre={`${titre}, ventilés par ${dimensionLibelle}`} />
        )}
      </section>

      <div className="grid gap-3 tab:gap-3.5 nav:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] nav:items-start">
        <TableauVentilation titre="Par type d'appel" premiereColonne="Type d'appel" lignes={lignesTableau(parType)} vide={vide} />
        <div className="flex flex-col gap-3 tab:gap-3.5">
          <TableauVentilation titre="Par modèle" premiereColonne="Modèle" lignes={lignesTableau(parModele)} vide={vide} />
          <BlocAudio audio={blocAudio(synthese, parType)} vide={vide} />
        </div>
      </div>
    </>
  )

  return (
    <div className="flex flex-col gap-3 tab:gap-3.5" aria-busy={enCours}>
      {ancien ? (
        <div role="status" className="flex items-start gap-2.5 rounded-xl border border-amber bg-amber-soft px-3 py-2.5 text-[13px] text-txt">
          <CloudOff size={18} className="mt-px shrink-0 text-amber" aria-hidden="true" />
          <span>
            <b className="block">API indisponible</b>
            Dernières valeurs connues, données de {hhmm}.{' '}
            {estVueDuJour(filtres.periode) ? 'Nouvel essai automatique dans 1 min.' : 'Rafraîchissez pour réessayer.'}
          </span>
        </div>
      ) : null}
      {ancien
        ? <div className="flex flex-col gap-3 tab:gap-3.5 opacity-55 grayscale-[.7]" style={{ filter: 'grayscale(.7)' }}>{corps}</div>
        : corps}
    </div>
  )
}

/** L'équivalent en tableau du graphique, atteignable au clavier [CA9]. */
function TableGraphique({ modele }) {
  const { entetes, lignes } = tableauGraphique(modele)
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-border-soft" tabIndex={0} role="region" aria-label="Valeurs du graphique">
      <table className="w-full text-[13px] tabular-nums">
        <thead className="sticky top-0 bg-card-alt text-[11.5px] text-txt2">
          <tr>{entetes.map((e, i) => <th key={e} scope="col" className={`px-2 py-1.5 font-bold ${i ? 'text-right' : 'text-left'}`}>{e}</th>)}</tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l[0]} className="border-t border-border-soft">
              {l.map((c, i) => i === 0
                ? <th key={i} scope="row" className="px-2 py-1.5 text-left font-semibold text-txt">{c}</th>
                : <td key={i} className="px-2 py-1.5 text-right">{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Panne({ erreur }) {
  return (
    <section role="alert" className="flex items-start gap-2.5 rounded-xl border border-amber bg-amber-soft px-3 py-2.5 text-[13px] text-txt">
      <CloudOff size={18} className="mt-px shrink-0 text-amber" aria-hidden="true" />
      <span>
        <b className="block">{erreur.statut === 0 ? 'API indisponible' : erreur.statut === 403 ? 'Accès réservé' : 'Lecture impossible'}</b>
        {erreur.statut === 0 ? "Aucune valeur n'a encore pu être lue : il n'y a pas de données à montrer." : erreur.message}
      </span>
    </section>
  )
}
