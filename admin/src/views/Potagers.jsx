import { useCallback, useMemo, useState } from 'react'
import { ArrowLeft, Info } from 'lucide-react'
import CadreVue from '../components/CadreVue.jsx'
import CarteGraphique from '../components/CarteGraphique.jsx'
import ChiffreCle from '../components/ChiffreCle.jsx'
import RappelPerimetre from '../components/RappelPerimetre.jsx'
import Segments from '../components/Segments.jsx'
import TableauDonnees from '../components/TableauDonnees.jsx'
import { useDonnees } from '../hooks/useDonnees.js'
import { estVueDuJour } from '../lib/periode.js'
import { versParametresApi } from '../lib/filtres.js'
import { euro, entier } from '../lib/format.js'
import {
  COLONNES_JARDINIERS, COLONNES_PARTAGE, COLONNES_POTAGERS, COLONNES_REPARTITION, DEFINITION_ACTIF, ONGLETS, TRIS,
  aucunAppel, chiffresBandeau, lignesJardiniers, lignesPartage, lignesPotagers, lignesRepartition, modeleAppels,
  modeleCout, regleUsageElevee, resumeEchange, texteIssues,
} from '../lib/acteurs.js'

const RACINE = '/admin/pilotage'

/** La liste de l'onglet, ou la fiche ouverte : une seule lecture, celle de l'API [US-319]. */
async function lire(client, parametres, onglet, fiche) {
  return client.appeler(fiche ? `${RACINE}/${fiche.onglet}/${fiche.id}` : `${RACINE}/${onglet}`, parametres)
}

function Bandeau({ bandeau, vide, ancien }) {
  return (
    <section aria-label="Chiffres clés">
      <ul className="grid grid-cols-2 gap-2 nav:grid-cols-5">
        {chiffresBandeau(bandeau).map((c) => (
          <li key={c.id}><ChiffreCle libelle={c.libelle} texte={c.texte} note={c.note} vide={vide && c.id !== 'potagers' && c.id !== 'jardiniers'} ariaVide="— pas d'appel" ancien={ancien} /></li>
        ))}
      </ul>
      <ul className="mt-2 flex flex-col gap-1 text-[12.5px] text-txt2">
        <li className="flex items-start gap-2"><Info size={15} className="mt-px shrink-0" aria-hidden="true" /><span>{DEFINITION_ACTIF}</span></li>
        <li className="flex items-start gap-2"><Info size={15} className="mt-px shrink-0" aria-hidden="true" /><span>{regleUsageElevee(bandeau)}</span></li>
      </ul>
    </section>
  )
}

function Liste({ donnees, onglet, ouvrir, tri, setTri, setOnglet, ancien, filtres }) {
  const potagers = onglet === 'potagers'
  const vide = donnees.lignes.every((l) => !l.appels)
  const lignes = (potagers ? lignesPotagers(donnees.lignes, tri) : lignesJardiniers(donnees.lignes, tri))
    .map((l) => (l.automatique ? l : { ...l, surOuvrir: (x) => ouvrir({ onglet, id: x.id, libelle: x.titre }) }))
  return (
    <>
      <Bandeau bandeau={donnees.bandeau} vide={vide} ancien={ancien} />
      <section className="rounded-2xl border border-border bg-card p-3.5 shadow-card" aria-label="Choix de la liste">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <Segments libelle="Liste" choix={ONGLETS} valeur={onglet} surChoix={setOnglet} />
          <div className="flex flex-wrap items-center gap-2 text-[12.5px] font-semibold text-txt2">
            <span>Trier par</span>
            <Segments libelle="Trier par" choix={TRIS} valeur={tri} surChoix={setTri} />
          </div>
        </div>
        {vide ? <p className="mt-2.5 text-[13px] text-txt2">{estVueDuJour(filtres.periode) ? "Aucun appel aujourd'hui" : 'Aucun appel sur la période'} : tous les chiffres sont à zéro.</p> : null}
      </section>
      <TableauDonnees
        titre={potagers ? 'Potagers' : 'Jardiniers'}
        sousTitre={potagers ? 'Tous les potagers, ceux sans appel compris' : 'Tous les comptes, avec les tâches automatiques à part'}
        premiereColonne={potagers ? 'Potager' : 'Adresse e-mail'}
        colonnes={potagers ? COLONNES_POTAGERS : COLONNES_JARDINIERS} lignes={lignes} messageVide="Aucun élément à afficher." />
    </>
  )
}

function Fiche({ fiche, donnees, retour, filtres }) {
  const potager = fiche.onglet === 'potagers'
  const entite = potager ? donnees.potager : donnees.utilisateur
  const partage = potager ? donnees.membres : donnees.potagers
  const g = donnees.graphique
  const sansAppel = aucunAppel(g)
  const echange = resumeEchange(donnees.echange)
  const periode = estVueDuJour(filtres.periode) ? "Aujourd'hui" : 'Sur la période'
  const vide = {
    vide: sansAppel, titreVide: estVueDuJour(filtres.periode) ? "Aucun appel aujourd'hui" : 'Aucun appel sur la période',
    messageVide: 'Le graphique se remplira au premier appel.',
  }
  return (
    <>
      <button type="button" onClick={retour} className="flex min-h-[38px] items-center gap-1.5 self-start text-[13px] font-bold text-brand-text">
        <ArrowLeft size={16} aria-hidden="true" />{potager ? 'Tous les potagers' : 'Tous les jardiniers'}
      </button>
      <section aria-label="Fiche">
        <h2 className="font-serif text-lg font-semibold leading-tight text-txt">{entite.libelle}</h2>
        <p className="mt-0.5 text-xs text-txt2">
          {potager ? `${entier(entite.membres)} membre${entite.membres > 1 ? 's' : ''}` : `${entier(entite.potagers)} potager${entite.potagers > 1 ? 's' : ''}`}
          {entite.usage_eleve ? ' · usage élevé' : ''}
        </p>
        <ul className="mt-2.5 grid grid-cols-2 gap-2 nav:grid-cols-4">
          <li><ChiffreCle libelle="Coût de la période" texte={euro(entite.cout_micro_eur)} note={`${entier(entite.appels)} appel${entite.appels > 1 ? 's' : ''}`} /></li>
          <li><ChiffreCle libelle="Coût médian d'un échange" texte={echange.texte} note={echange.note} /></li>
          <li><ChiffreCle libelle="Issues des appels" texte={entite.taux_echec === null ? '—' : `${(entite.taux_echec * 100).toFixed(1).replace('.', ',')} %`} note={`échec · ${texteIssues(donnees.issues)}`} /></li>
          <li><ChiffreCle libelle="Part du coût de la plateforme" texte={entite.part_cout === null ? '—' : `${(entite.part_cout * 100).toFixed(1).replace('.', ',')} %`} note="sur la période" /></li>
        </ul>
      </section>
      <div className="grid gap-3 tab:gap-3.5 nav:grid-cols-2 nav:items-start">
        <CarteGraphique titre="Coût par jour" sousTitre={periode} modele={modeleCout(g)} formatValeur={euro} formatAxe={euro} {...vide} />
        <CarteGraphique titre="Appels par jour" sousTitre={periode} modele={modeleAppels(g)} {...vide} />
      </div>
      <TableauDonnees titre={potager ? 'Membres et part de la consommation' : 'Potagers et part de la consommation'}
        sousTitre="Part du coût (des appels quand rien n'est chiffré)" premiereColonne={potager ? 'Adresse e-mail' : 'Potager'}
        colonnes={COLONNES_PARTAGE} lignes={lignesPartage(partage)} messageVide="Personne pour l'instant." />
      <div className="grid gap-3 tab:gap-3.5 nav:grid-cols-2 nav:items-start">
        <TableauDonnees titre="Par type d'appel" premiereColonne="Type" colonnes={COLONNES_REPARTITION} lignes={lignesRepartition(donnees.par_type)} vide={sansAppel} messageVide="Aucun appel sur la période." />
        <TableauDonnees titre="Par canal" premiereColonne="Canal" colonnes={COLONNES_REPARTITION} lignes={lignesRepartition(donnees.par_canal, true)} vide={sansAppel} messageVide="Aucun appel sur la période." />
      </div>
    </>
  )
}

export default function Potagers({ client, filtres, declencheur, signalerMaj, surFiltres }) {
  const [onglet, setOnglet] = useState('potagers')
  const [tri, setTri] = useState('cout')
  const [fiche, setFiche] = useState(null)
  const parametres = useMemo(() => versParametresApi(filtres), [filtres])
  const charger = useCallback(() => lire(client, parametres, onglet, fiche), [client, parametres, onglet, fiche])
  const etat = useDonnees(charger, {
    cle: JSON.stringify([parametres, onglet, fiche && [fiche.onglet, fiche.id]]), periode: filtres.periode, declencheur, surMiseAJour: signalerMaj,
  })
  const quitter = useCallback(() => setFiche(null), [])

  return (
    <CadreVue {...etat} periode={filtres.periode}>
      {(ancien, hhmm) => {
        const d = etat.donnees
        const pret = fiche ? Boolean(d.potager || d.utilisateur) : Boolean(d.lignes)
        return (
        <>
          <RappelPerimetre filtres={filtres} surChangement={surFiltres} />
          {!pret ? <p className="py-10 text-center text-sm text-txt2" role="status">Chargement des chiffres…</p> : fiche
            ? <Fiche fiche={fiche} donnees={etat.donnees} retour={quitter} filtres={filtres} />
            : <Liste donnees={etat.donnees} onglet={onglet} ouvrir={setFiche} tri={tri} setTri={setTri} setOnglet={setOnglet} ancien={ancien ? hhmm : ''} filtres={filtres} />}
        </>
        )
      }}
    </CadreVue>
  )
}
