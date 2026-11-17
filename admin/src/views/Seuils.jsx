import { useCallback, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock, Info, PauseCircle } from 'lucide-react'
import CadreVue from '../components/CadreVue.jsx'
import PanneauSeuil from '../components/PanneauSeuil.jsx'
import TableauDonnees from '../components/TableauDonnees.jsx'
import { useDonnees } from '../hooks/useDonnees.js'
import { COLONNES_HISTORIQUE, badgeEtat, depuis, envoisPeriodiques, libelleGravite, lignesHistorique } from '../lib/seuils.js'

const RACINE = '/admin/pilotage/seuils'
const ICONE_ETAT = { franchi: AlertTriangle, norme: CheckCircle2, nodata: Clock, inactif: PauseCircle }
const CLASSE_ETAT = {
  franchi: 'bg-red text-white',
  norme: 'bg-brand-soft text-brand-text',
  nodata: 'bg-card-alt text-txt2',
  inactif: 'bg-transparent text-txt3 shadow-[inset_0_0_0_1px_var(--border)]',
}
const CLASSE_GRAVITE = { haute: 'bg-red-soft text-red', moyenne: 'bg-amber-soft text-amber', basse: 'bg-card-alt text-txt2' }
const BADGE = 'inline-flex items-center gap-1 whitespace-nowrap rounded-full px-[9px] py-0.5 text-[11.5px] font-bold'
// Les vues que les alertes désignent (clés de `lib/navigation.js`).
const NOM_VUE = { consommation: 'Consommation', cout: 'Coût', fiabilite: 'Fiabilité', derives: 'Dérives' }

function Interrupteur({ actif, libelle, surBascule, desactive }) {
  return (
    <button type="button" role="switch" aria-checked={actif} aria-label={libelle} onClick={surBascule} disabled={desactive}
      className={`relative h-7 w-[46px] shrink-0 rounded-full disabled:opacity-60 ${actif ? 'bg-brand' : 'bg-txt3'}`}>
      <span aria-hidden="true" className={`absolute top-[3px] h-[22px] w-[22px] rounded-full bg-surface shadow-[0_1px_3px_rgba(0,0,0,.25)] transition-[left] ${actif ? 'left-[21px]' : 'left-[3px]'}`} />
    </button>
  )
}

function LigneSeuil({ seuil, surBascule, surModifier, occupe }) {
  const { etat, libelle } = badgeEtat(seuil)
  const Icone = ICONE_ETAT[etat] || Clock
  const inactif = !seuil.actif
  return (
    <li className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 border-t border-border-soft px-0.5 py-3 first:border-t-0">
      <div className="col-span-full">
        <div className={`text-sm font-bold leading-snug ${inactif ? 'text-txt3' : 'text-txt'}`}>{seuil.libelle}</div>
        <div className={`mt-0.5 text-[12.5px] ${inactif ? 'text-txt3' : 'text-txt2'}`}>
          Alerte si {seuil.regle}
          {seuil.a_valider ? <span className="ml-1.5 rounded-full bg-amber-soft px-1.5 py-px text-[11px] font-bold text-amber">à valider</span> : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`${BADGE} ${CLASSE_GRAVITE[seuil.gravite]}`}>Gravité {libelleGravite(seuil.gravite)}</span>
        <span className={`${BADGE} ${CLASSE_ETAT[etat]}`}><Icone size={13} aria-hidden="true" />{libelle}</span>
      </div>
      <Interrupteur actif={seuil.actif} desactive={occupe} surBascule={() => surBascule(seuil)}
        libelle={`${seuil.libelle} : ${seuil.actif ? 'actif' : 'inactif'}`} />
      <button type="button" onClick={() => surModifier(seuil)} aria-label={`Modifier le seuil ${seuil.libelle}`}
        className="col-start-2 min-h-[36px] px-1 text-[12.5px] font-bold text-brand-text">Modifier</button>
    </li>
  )
}

/** Le bloc rouge en tête, ou la ligne « aucune alerte ouverte » [maquette d'US-318]. */
function AlertesOuvertes({ alertes, maintenant, surVue }) {
  if (!alertes.length) {
    return (
      <p className="flex items-center gap-2.5 rounded-[14px] border border-border bg-card px-3.5 py-[11px] text-[13px] text-txt2">
        <CheckCircle2 size={18} className="shrink-0 text-brand" aria-hidden="true" />Aucune alerte ouverte.
      </p>
    )
  }
  return (
    <section aria-label="Alertes ouvertes" className="rounded-2xl border-[1.5px] border-red bg-red-soft px-3.5 py-3">
      <h2 className="flex items-center gap-2 font-serif text-base font-semibold leading-tight text-txt">
        <AlertTriangle size={18} className="text-red" aria-hidden="true" />
        {alertes.length} alerte{alertes.length > 1 ? 's' : ''} ouverte{alertes.length > 1 ? 's' : ''}
      </h2>
      {alertes.map((a) => (
        <div key={a.id} className="mt-2.5 rounded-xl border border-border bg-card px-3 py-2.5">
          <div className="text-sm font-bold">{a.libelle}</div>
          <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-[3px] text-[12.5px] tabular-nums">
            <dt className="text-txt2">Mesuré</dt><dd className="font-bold">{a.mesure_texte}</dd>
            <dt className="text-txt2">Seuil</dt><dd className="font-bold">{a.seuil_texte}{a.reference_texte ? ` · moyenne 7 j : ${a.reference_texte}` : ''}</dd>
            <dt className="text-txt2">Depuis</dt><dd className="font-bold">{depuis(a.declenchee_le, maintenant)}</dd>
          </dl>
          {a.vue ? (
            <button type="button" onClick={() => surVue(a.vue)} className="mt-2 text-[13px] font-bold text-brand-text">
              Voir dans {NOM_VUE[a.vue] || a.vue} →
            </button>
          ) : null}
        </div>
      ))}
    </section>
  )
}

function EnvoisPeriodiques({ reglages, canaux }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
      <h2 className="mb-1 font-serif text-base font-semibold leading-tight text-txt">Envois périodiques</h2>
      <ul>
        {envoisPeriodiques(reglages, canaux).map((e) => (
          <li key={e.id} className="flex items-center justify-between gap-3 border-t border-border-soft px-0.5 py-2.5 first:border-t-0">
            <span>
              <b className="block text-sm">{e.titre}</b>
              <small className="text-xs text-txt2">{e.detail}</small>
              {e.actif && !e.canalJoignable ? <small className="block text-xs font-semibold text-red">Aucun destinataire joignable sur ce canal.</small> : null}
            </span>
            <span className={`${BADGE} ${e.actif ? 'bg-brand-soft text-brand-text' : 'bg-card-alt text-txt2'}`}>
              {e.actif ? <CheckCircle2 size={13} aria-hidden="true" /> : <PauseCircle size={13} aria-hidden="true" />}{e.actif ? 'Activé' : 'Désactivé'}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 flex items-start gap-2 text-xs text-txt2">
        <Info size={14} className="mt-px shrink-0" aria-hidden="true" />
        <span>Réglés par la configuration du serveur (<code className="font-mono">PILOTAGE_RESUME_QUOTIDIEN</code>, <code className="font-mono">PILOTAGE_BILAN_HEBDO</code>) ; un seul changement et un redémarrage.</span>
      </p>
    </section>
  )
}

export default function Seuils({ client, declencheur, signalerMaj, surVue }) {
  const [occupe, setOccupe] = useState(false)
  const [edition, setEdition] = useState(null)
  const [recharge, setRecharge] = useState(0)
  const [erreur, setErreur] = useState('')
  const charger = useCallback(() => client.appeler(RACINE), [client])
  const etat = useDonnees(charger, { cle: 'seuils', periode: 'aujourdhui', declencheur: declencheur + recharge, surMiseAJour: signalerMaj })

  const enregistrer = useCallback(async (id, corps) => {
    await client.modifier(`${RACINE}/${id}`, corps)
    setRecharge((n) => n + 1)
  }, [client])

  const basculer = useCallback(async (seuil) => {
    setOccupe(true)
    setErreur('')
    try { await enregistrer(seuil.id, { actif: !seuil.actif }) } catch (e) { setErreur(e.message || 'Le changement a échoué.') } finally { setOccupe(false) }
  }, [enregistrer])

  return (
    <CadreVue {...etat} periode="aujourdhui">
      {() => {
        const { seuils, alertes_ouvertes: ouvertes, alertes, reglages, canaux } = etat.donnees
        const maintenant = new Date()
        const actifs = seuils.filter((s) => s.actif).length
        const courant = edition ? seuils.find((s) => s.id === edition) : null
        return (
          <>
            <AlertesOuvertes alertes={ouvertes} maintenant={maintenant} surVue={surVue} />
            {erreur ? <p role="alert" className="rounded-xl border border-red bg-red-soft px-3 py-2 text-[13px] font-semibold text-txt">{erreur}</p> : null}

            <div className="grid gap-3 tab:gap-3.5 nav:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] nav:items-start">
              <section className="rounded-2xl border border-border bg-card p-3.5 shadow-card" aria-labelledby="titre-seuils">
                <h2 id="titre-seuils" className="font-serif text-base font-semibold leading-tight text-txt">Seuils</h2>
                <p className="mb-1 mt-0.5 text-xs text-txt2">Alerte par Telegram et par e-mail · {actifs} actif{actifs > 1 ? 's' : ''} sur {seuils.length}
                  {reglages.alertes ? '' : ' · envois éteints (PILOTAGE_ALERTES=non) : les alertes sont seulement journalisées'}</p>
                <ul>
                  {seuils.map((s) => <LigneSeuil key={s.id} seuil={s} occupe={occupe} surBascule={basculer} surModifier={(x) => setEdition(x.id)} />)}
                </ul>
              </section>

              <div className="flex flex-col gap-3 tab:gap-3.5">
                <EnvoisPeriodiques reglages={reglages} canaux={canaux} />
                <TableauDonnees titre="Historique des alertes" sousTitre={`Les ${alertes.length} dernière${alertes.length > 1 ? 's' : ''} · le contenu des messages de jardiniers n'y figure jamais`}
                  premiereColonne="Indicateur" colonnes={COLONNES_HISTORIQUE} lignes={lignesHistorique(alertes, maintenant)}
                  messageVide="Aucune alerte n'a encore été déclenchée." />
              </div>
            </div>
            {courant ? <PanneauSeuil key={courant.id} seuil={courant} surFermer={() => setEdition(null)} surEnregistrer={enregistrer} /> : null}
          </>
        )
      }}
    </CadreVue>
  )
}

