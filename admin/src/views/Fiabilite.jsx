import { useCallback, useMemo, useState } from 'react'
import { Info } from 'lucide-react'
import CadreVue from '../components/CadreVue.jsx'
import CarteGraphique from '../components/CarteGraphique.jsx'
import ChiffreCle from '../components/ChiffreCle.jsx'
import GrilleChaleur from '../components/GrilleChaleur.jsx'
import RappelPerimetre from '../components/RappelPerimetre.jsx'
import Segments from '../components/Segments.jsx'
import TableauDonnees from '../components/TableauDonnees.jsx'
import { useDonnees } from '../hooks/useDonnees.js'
import { bornes, estVueDuJour } from '../lib/periode.js'
import { versParametresApi } from '../lib/filtres.js'
import { jourBref } from '../lib/format.js'
import {
  COLONNES_ECHECS, COLONNES_ISSUES, NOTE_LATENCE, chiffresCles, lignesEchecs, lignesIssues, modeleGraphiqueIssues,
  periodeSansAppel, texteLatenceEchecs, titreGrille,
} from '../lib/fiabilite.js'

const RACINE = '/admin/pilotage'

/** Deux lectures en parallèle : la fiabilité (bandeau, tableaux, grille, échecs) et la série des issues par
 *  jour. Les taux et les latences sont ceux de l'API [US-314]. */
async function lire(client, parametres) {
  const [fiabilite, serie] = await Promise.all([
    client.appeler(`${RACINE}/fiabilite`, parametres),
    client.appeler(`${RACINE}/series`, { ...parametres, mesure: 'appels', dimension: 'issue' }),
  ])
  return { fiabilite, serie }
}

function libellePeriode(filtres, pas) {
  if (pas === 'heure') return "Aujourd'hui, pas horaire"
  if (filtres.periode === 'perso') { const b = bornes(filtres); return `du ${jourBref(b.depuis)} au ${jourBref(b.jusqu_a)}` }
  return `${filtres.periode.replace('j', '')} derniers jours`
}

export default function Fiabilite({ client, filtres, declencheur, signalerMaj, surFiltres }) {
  const parametres = useMemo(() => versParametresApi(filtres), [filtres])
  const charger = useCallback(() => lire(client, parametres), [client, parametres])
  const etat = useDonnees(charger, {
    cle: JSON.stringify(parametres), periode: filtres.periode, declencheur, surMiseAJour: signalerMaj,
  })

  return (
    <CadreVue {...etat} periode={filtres.periode}>
      {(ancien, hhmm) => {
        const { fiabilite, serie } = etat.donnees
        const vide = periodeSansAppel(fiabilite)
        const precedente = `${jourBref(fiabilite.periode_precedente.depuis)} – ${jourBref(fiabilite.periode_precedente.jusqu_a)}`
        const graphique = modeleGraphiqueIssues(serie)
        const titre = `Issues des appels par ${serie.pas === 'heure' ? 'heure' : 'jour'}`
        return (
          <>
            <RappelPerimetre filtres={filtres} surChangement={surFiltres} />

            <section aria-label="Chiffres clés">
              <ul className="grid grid-cols-2 gap-2 tab:grid-cols-3 nav:grid-cols-5">
                {chiffresCles(fiabilite).map((c) => (
                  <li key={c.id} className="last:odd:col-span-2 tab:last:odd:col-auto">
                    <ChiffreCle libelle={c.libelle} texte={c.texte} ecart={c.ecart} periodePrecedente={precedente}
                      vide={vide} ancien={ancien ? hhmm : ''} />
                  </li>
                ))}
              </ul>
              <p className="mt-2 flex items-start gap-2 text-[12.5px] text-txt2">
                <Info size={15} className="mt-px shrink-0" aria-hidden="true" />
                <span>{NOTE_LATENCE} {vide ? '' : texteLatenceEchecs(fiabilite)}</span>
              </p>
            </section>

            <CarteGraphique
              titre={titre} sousTitre={`${libellePeriode(filtres, serie.pas)} · toutes les issues présentes en base`}
              modele={graphique} titreAccessible={`${titre}, empilées par issue`}
              vide={vide} titreVide={estVueDuJour(filtres.periode) ? "Aucun appel aujourd'hui" : 'Aucun appel sur la période'}
            />

            <div className="grid gap-3 tab:gap-3.5 nav:grid-cols-2 nav:items-start">
              <TableauDonnees titre="Par modèle" sousTitre="Latences sur les appels réussis" premiereColonne="Modèle"
                colonnes={COLONNES_ISSUES} lignes={lignesIssues(fiabilite.par_modele)} vide={vide} messageVide="Aucun appel sur la période." />
              <TableauDonnees titre="Par type d'appel" sousTitre="Latences sur les appels réussis" premiereColonne="Type d'appel"
                colonnes={COLONNES_ISSUES} lignes={lignesIssues(fiabilite.par_type)} vide={vide} messageVide="Aucun appel sur la période." />
            </div>

            <CarteQuotas grille={fiabilite.grille_quota} />

            <TableauDonnees titre="Les 20 derniers échecs" sousTitre="Aucun contenu de message : heure, type, modèle, issue, canal et latence seulement"
              premiereColonne="Heure" colonnes={COLONNES_ECHECS} lignes={lignesEchecs(fiabilite.derniers_echecs)}
              messageVide="Aucun échec sur la période." />
          </>
        )
      }}
    </CadreVue>
  )
}

/** [CA5] Les quotas atteints, heure × jour, un modèle à la fois. */
function CarteQuotas({ grille }) {
  const [choix, setChoix] = useState('')
  const modeles = grille.modeles
  const courant = modeles.find((m) => m.modele === choix) || modeles[0]
  return (
    <section aria-labelledby="titre-quotas" className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
      <div className="mb-2.5 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div>
          <h3 id="titre-quotas" className="font-serif text-base font-semibold leading-tight text-txt">Quotas atteints, heure par heure</h3>
          <p className="mt-0.5 text-xs text-txt2">7 derniers jours, {titreGrille(grille)} · appels en « quota » par modèle</p>
        </div>
        {modeles.length > 1 ? (
          <Segments libelle="Modèle" choix={modeles.map((m) => ({ id: m.modele, libelle: String(m.modele).replace(/^mistral\//, '') }))}
            valeur={courant.modele} surChoix={setChoix} />
        ) : null}
      </div>
      {courant ? (
        <GrilleChaleur jours={grille.jours} cellules={courant.cellules} titre={`Quotas de ${courant.modele}, heure par jour`} />
      ) : (
        <div className="flex flex-col items-center gap-1.5 px-3 py-[22px] text-center text-[13px] text-txt2">
          <b className="text-sm text-txt">Aucun quota atteint</b>
          <span>Aucun appel en « quota » sur ces 7 jours.</span>
        </div>
      )}
    </section>
  )
}
