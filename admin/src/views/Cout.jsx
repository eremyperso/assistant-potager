import { useCallback, useMemo, useState } from 'react'
import { AlertTriangle, Info } from 'lucide-react'
import CadreVue from '../components/CadreVue.jsx'
import CarteGraphique from '../components/CarteGraphique.jsx'
import ChiffreCle from '../components/ChiffreCle.jsx'
import RappelPerimetre from '../components/RappelPerimetre.jsx'
import Segments from '../components/Segments.jsx'
import TableauDonnees from '../components/TableauDonnees.jsx'
import { useDonnees } from '../hooks/useDonnees.js'
import { bornes, estVueDuJour } from '../lib/periode.js'
import { versParametresApi } from '../lib/filtres.js'
import { euro, jourBref } from '../lib/format.js'
import {
  COLONNES_ECHANGES, COLONNES_POTAGERS, DEFINITION_ACTIF, DIMENSIONS_COUT, MENTION_TARIF, aucunCout,
  avertissementNonChiffres, chiffresCles, garderPrix, lignesEchanges, lignesPotagers, lirePrix, lirePrixGarde,
  marge, modeleGraphiqueCout, texteGrille,
} from '../lib/cout.js'

const RACINE = '/admin/pilotage'

/** Les trois lectures de la vue, en parallèle. Aucune addition ici : ce que l'écran montre est ce que
 *  rendent `cout`, `series` et `ventilation` [US-313]. */
async function lire(client, parametres, dimension) {
  const [cout, serie, potagers] = await Promise.all([
    client.appeler(`${RACINE}/cout`, parametres),
    client.appeler(`${RACINE}/series`, { ...parametres, mesure: 'cout_micro_eur', dimension }),
    client.appeler(`${RACINE}/ventilation`, { ...parametres, dimension: 'potager', mesure: 'cout_micro_eur', limite: 10 }),
  ])
  return { cout, serie, potagers }
}

function libellePeriode(filtres) {
  if (filtres.periode === 'aujourdhui') return "Aujourd'hui, pas horaire"
  if (filtres.periode === 'perso') { const b = bornes(filtres); return `du ${jourBref(b.depuis)} au ${jourBref(b.jusqu_a)}` }
  return `${filtres.periode.replace('j', '')} derniers jours`
}

export default function Cout({ client, filtres, declencheur, signalerMaj, surFiltres }) {
  const [dimension, setDimension] = useState('modele')
  const parametres = useMemo(() => versParametresApi(filtres), [filtres])
  const charger = useCallback(() => lire(client, parametres, dimension), [client, parametres, dimension])
  const etat = useDonnees(charger, {
    cle: JSON.stringify([parametres, dimension]), periode: filtres.periode, declencheur, surMiseAJour: signalerMaj,
  })

  return (
    <CadreVue {...etat} periode={filtres.periode}>
      {(ancien, hhmm) => {
        const { cout, serie, potagers } = etat.donnees
        const vide = cout.appels === 0
        const graphique = modeleGraphiqueCout(serie)
        const dimensionLibelle = DIMENSIONS_COUT.find((d) => d.id === dimension)?.libelle.toLowerCase()
        const horaire = serie.pas === 'heure'
        const titre = `Coût par ${horaire ? 'heure' : 'jour'}`
        const avertissement = avertissementNonChiffres(cout)
        return (
          <>
            <RappelPerimetre filtres={filtres} surChangement={surFiltres} />

            <section aria-label="Chiffres clés">
              <ul className="grid grid-cols-2 gap-2 nav:grid-cols-4">
                {chiffresCles(cout).map((c) => (
                  <li key={c.id}>
                    <ChiffreCle libelle={c.libelle} texte={c.texte} note={c.note} vide={vide && c.id !== 'mois' && c.id !== 'projection'}
                      ariaVide="— pas d'appel" ancien={ancien ? hhmm : ''} />
                  </li>
                ))}
              </ul>
              <ul className="mt-2 flex flex-col gap-1 text-[12.5px] text-txt2">
                <li className="flex items-start gap-2"><Info size={15} className="mt-px shrink-0" aria-hidden="true" /><span>{DEFINITION_ACTIF}</span></li>
                <li className="flex items-start gap-2"><Info size={15} className="mt-px shrink-0" aria-hidden="true" /><span>{MENTION_TARIF} {texteGrille(cout)}.</span></li>
              </ul>
            </section>

            {avertissement ? (
              <section role="note" className="flex items-start gap-2.5 rounded-xl border border-amber bg-amber-soft px-3 py-2.5 text-[13px] text-txt">
                <AlertTriangle size={18} className="mt-px shrink-0 text-amber" aria-hidden="true" />
                <span>
                  <b className="block">{avertissement.titre}</b>
                  {avertissement.detail}{' '}
                  Modèles concernés : <span className="font-mono text-[12.5px]">{avertissement.modeles.map((m) => m.texte).join(', ')}</span>.
                </span>
              </section>
            ) : null}

            <CarteGraphique
              titre={titre} sousTitre={`${libellePeriode(filtres)} · ventilation : ${dimensionLibelle}`}
              actions={<Segments libelle="Ventiler par" choix={DIMENSIONS_COUT} valeur={dimension} surChoix={setDimension} />}
              modele={graphique} titreAccessible={`${titre}, ventilé par ${dimensionLibelle}`}
              formatValeur={euro} formatAxe={euro}
              vide={vide || aucunCout(serie)}
              titreVide={vide ? (estVueDuJour(filtres.periode) ? "Aucun appel aujourd'hui" : 'Aucun appel sur la période') : 'Aucun appel chiffré'}
              messageVide={vide ? 'Le graphique se remplira au premier appel.' : 'Les appels de la période ne sont pas dans la grille tarifaire.'}
            />

            <div className="grid gap-3 tab:gap-3.5 nav:grid-cols-2 nav:items-start">
              <TableauDonnees titre="Coût d'un échange" sousTitre="Une réponse, tous ses appels : par canal"
                premiereColonne="Canal" colonnes={COLONNES_ECHANGES} lignes={lignesEchanges(cout)} vide={vide}
                messageVide="Aucun échange sur la période." />
              <TableauDonnees titre="Les 10 potagers les plus coûteux" sousTitre="Coût, appels et part du total de la période"
                premiereColonne="Potager" colonnes={COLONNES_POTAGERS} lignes={lignesPotagers(potagers)} vide={vide} />
            </div>

            <CarteMarge cout={cout} />
          </>
        )
      }}
    </CadreVue>
  )
}

/** [CA6] Le prix d'abonnement envisagé : gardé sur l'appareil, jamais envoyé ni enregistré. */
function CarteMarge({ cout }) {
  const stockage = typeof window !== 'undefined' ? window.localStorage : null
  const [texte, setTexte] = useState(() => (stockage ? lirePrixGarde(stockage) : ''))
  const prix = lirePrix(texte)
  const resultat = useMemo(() => marge(prix, cout.par_jardinier), [prix, cout.par_jardinier])
  const surSaisie = (e) => { setTexte(e.target.value); if (stockage) garderPrix(stockage, e.target.value) }
  const illisible = texte.trim() !== '' && prix === null

  return (
    <section aria-labelledby="titre-marge" className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
      <div className="mb-2.5">
        <h3 id="titre-marge" className="font-serif text-base font-semibold leading-tight text-txt">Marge d'un abonnement</h3>
        <p className="mt-0.5 text-xs text-txt2">Le prix saisi reste sur cet appareil : il n'est ni envoyé ni enregistré.</p>
      </div>
      <label className="flex flex-wrap items-center gap-2 text-[13px] text-txt">
        <span className="font-semibold">Prix d'abonnement mensuel envisagé</span>
        <span className="flex items-center gap-1.5">
          <input type="text" inputMode="decimal" value={texte} onChange={surSaisie} placeholder="3,00" aria-invalid={illisible}
            className="min-h-[38px] w-24 rounded-[10px] border border-border bg-card px-2.5 text-right text-[14px] font-semibold tabular-nums text-txt" />
          <span aria-hidden="true">€ / mois</span>
        </span>
      </label>
      {illisible ? <p role="alert" className="mt-1.5 text-xs font-semibold text-[color:var(--ecart-defavorable)]">Prix illisible : écrivez un montant, par exemple 3 ou 2,50.</p> : null}

      {cout.par_jardinier.nb === 0 ? (
        <p className="mt-2.5 text-[13px] text-txt2">Aucun jardinier actif sur la période : pas de marge à calculer.</p>
      ) : resultat ? (
        <dl className="mt-3 grid gap-2.5 tab:grid-cols-2 tabular-nums">
          <LigneMarge titre="Jardinier actif médian" ligne={resultat.mediane} />
          <LigneMarge titre="Jardinier au P95" ligne={resultat.p95} />
        </dl>
      ) : (
        <p className="mt-2.5 text-[13px] text-txt2">Saisissez un prix pour voir la marge par jardinier actif médian et par jardinier au P95.</p>
      )}
      <p className="mt-2.5 text-xs text-txt2">Coût d'un jardinier actif ramené à 30 jours. {MENTION_TARIF}</p>
    </section>
  )
}

function LigneMarge({ titre, ligne }) {
  if (!ligne) return <div className="rounded-xl bg-card-alt px-3 py-2.5 text-[13px] text-txt2">{titre} : non chiffré</div>
  return (
    <div className="rounded-xl bg-card-alt px-3 py-2.5">
      <dt className="text-xs text-txt2">{titre}</dt>
      <dd className="mt-0.5 text-xl font-bold text-txt">
        {ligne.texte}
        <small className={`ml-2 text-xs font-bold ${ligne.positive ? 'text-brand-text' : 'text-[color:var(--ecart-defavorable)]'}`}>{ligne.positive ? 'marge' : 'perte'}</small>
      </dd>
      <dd className="text-xs text-txt2">coût mensuel {ligne.cout}</dd>
    </div>
  )
}
