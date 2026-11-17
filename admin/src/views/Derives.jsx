import { useCallback, useMemo, useState } from 'react'
import { FlaskConical } from 'lucide-react'
import CadreVue from '../components/CadreVue.jsx'
import CarteGraphique from '../components/CarteGraphique.jsx'
import RappelPerimetre from '../components/RappelPerimetre.jsx'
import Segments from '../components/Segments.jsx'
import TableauDonnees from '../components/TableauDonnees.jsx'
import { useDonnees } from '../hooks/useDonnees.js'
import { versParametresApi } from '../lib/filtres.js'
import {
  COLONNES_VERSION_CANAL, COLONNES_VERSION_TYPE, CONSEIL_MESURE, TYPE_PAR_DEFAUT, comparer, libelleVersion,
  lignesVersionCanal, lignesVersionType, modeleCourbe, periodeSansAppel, typesDisponibles, versionsParDefaut,
} from '../lib/derives.js'

const RACINE = '/admin/pilotage'

export default function Derives({ client, filtres, declencheur, signalerMaj, surFiltres }) {
  const [typeCourbe, setTypeCourbe] = useState(TYPE_PAR_DEFAUT)
  const parametres = useMemo(() => ({ ...versParametresApi(filtres), type_courbe: typeCourbe }), [filtres, typeCourbe])
  const charger = useCallback(() => client.appeler(`${RACINE}/derives`, parametres), [client, parametres])
  const etat = useDonnees(charger, {
    cle: JSON.stringify(parametres), periode: filtres.periode, declencheur, surMiseAJour: signalerMaj,
  })

  return (
    <CadreVue {...etat} periode={filtres.periode}>
      {() => {
        const derives = etat.donnees
        const vide = periodeSansAppel(derives)
        const courbe = modeleCourbe(derives)
        const types = typesDisponibles(derives)
        return (
          <>
            <RappelPerimetre filtres={filtres} surChangement={surFiltres} />
            <ConseilMesure filtres={filtres} surFiltres={surFiltres} />

            <Comparaison derives={derives} typeInitial={typeCourbe} vide={vide} />

            <CarteGraphique
              titre="Jetons d'entrée par appel, jour après jour"
              sousTitre={`Médiane du type « ${derives.courbe.appel_type} » · un repère à la première apparition de chaque version`}
              actions={<Segments libelle="Type d'appel" choix={types.map((t) => ({ id: t, libelle: t }))} valeur={typeCourbe} surChoix={setTypeCourbe} />}
              modele={courbe.modele} reperes={courbe.reperes}
              titreAccessible={`Médiane des jetons d'entrée par appel, type ${derives.courbe.appel_type}`}
              vide={vide || courbe.sansAppel} titreVide={vide ? 'Aucun appel sur la période' : `Aucun appel « ${derives.courbe.appel_type} » mesuré`}
              messageVide="La courbe se dessinera dès qu'un appel réussi de ce type sera mesuré."
            />

            <TableauDonnees titre="Par version et par type d'appel"
              sousTitre={`Appels réussis, au jeton. Les ${derives.versions.filter((v) => v !== null).length} versions les plus récentes ayant des appels`}
              premiereColonne="Version" colonnes={COLONNES_VERSION_TYPE} lignes={lignesVersionType(derives)} vide={vide}
              messageVide="Aucun appel mesuré sur la période." />

            <TableauDonnees titre="Par version et par canal : ce que coûte un échange"
              sousTitre="Un échange = tous les appels d'une même réponse, échecs compris"
              premiereColonne="Version" colonnes={COLONNES_VERSION_CANAL} lignes={lignesVersionCanal(derives)} vide={vide}
              messageVide="Aucun échange sur la période." />
          </>
        )
      }}
    </CadreVue>
  )
}

/** [CA6] La comparaison la plus propre est celle d'une campagne de mesure rejouée sur les mêmes phrases. */
function ConseilMesure({ filtres, surFiltres }) {
  const enMesure = filtres.provenance.length === 1 && filtres.provenance[0] === 'mesure'
  return (
    <p role="note" className="flex items-start gap-2 text-[12.5px] text-txt2">
      <FlaskConical size={15} className="mt-px shrink-0" aria-hidden="true" />
      {enMesure ? (
        <span>Comparaison sur les mesures : le jeu de phrases est le même d'une version à l'autre, c'est la plus propre.</span>
      ) : (
        <span>{CONSEIL_MESURE}{' '}
          <button type="button" className="font-bold text-brand-text underline underline-offset-2"
            onClick={() => surFiltres({ ...filtres, provenance: ['mesure'] })}>Comparer en mesure</button>
        </span>
      )}
    </p>
  )
}

const SELECT = 'min-h-[38px] rounded-[10px] border border-border bg-card px-2.5 text-[13px] font-semibold text-txt'

function SelectVersion({ libelle, versions, valeur, surChange }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-txt2">
      <span className="font-semibold">{libelle}</span>
      <select className={SELECT} value={valeur === null ? '__aucune__' : valeur ?? ''}
        onChange={(e) => surChange(e.target.value === '__aucune__' ? null : e.target.value)}>
        {versions.map((v) => <option key={String(v)} value={v === null ? '__aucune__' : v}>{libelleVersion(v)}</option>)}
      </select>
    </label>
  )
}

/** [CA4, CA5] Deux versions côte à côte, l'écart en pourcentage, mis en évidence au-delà de 20 %. */
function Comparaison({ derives, typeInitial, vide }) {
  const [type, setType] = useState(typeInitial)
  const [choix, setChoix] = useState(null)
  const types = typesDisponibles(derives)
  const versions = derives.versions
  const defaut = useMemo(() => versionsParDefaut(derives, type), [derives, type])
  const a = choix?.a ?? defaut?.a
  const b = choix?.b ?? defaut?.b
  const resultat = a !== undefined && b !== undefined ? comparer(derives, a, b, type) : null

  return (
    <section aria-labelledby="titre-comparaison" className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
      <div className="mb-2.5">
        <h3 id="titre-comparaison" className="font-serif text-base font-semibold leading-tight text-txt">Comparer deux versions</h3>
        <p className="mt-0.5 text-xs text-txt2">
          Écart mis en évidence au-delà de {Math.round(derives.seuil_ecart * 100)} % ; une version de moins de {derives.seuil_echantillon} appels
          (ou échanges) reste « échantillon faible » et n'est jamais mise en évidence.
        </p>
      </div>
      {vide || versions.length < 2 ? (
        <p className="py-3 text-center text-[13px] text-txt2">
          {vide ? 'Aucun appel sur la période.' : 'Une seule version sur la période : rien à comparer. Élargissez la période.'}
        </p>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-1 gap-2.5 tab:grid-cols-3">
            <SelectVersion libelle="Version de référence" versions={versions} valeur={a} surChange={(v) => setChoix({ a: v, b })} />
            <SelectVersion libelle="Version comparée" versions={versions} valeur={b} surChange={(v) => setChoix({ a, b: v })} />
            <label className="flex flex-col gap-1 text-xs text-txt2">
              <span className="font-semibold">Type d'appel</span>
              <select className={SELECT} value={type} onChange={(e) => { setType(e.target.value); setChoix(null) }}>
                {types.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
          </div>
          {resultat === null || resultat.sansDonnees ? (
            <p className="py-3 text-center text-[13px] text-txt2">Aucun appel « {type} » mesuré pour l'une de ces versions.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[13px] tabular-nums">
                <thead>
                  <tr>
                    <th scope="col" className="border-b border-border px-2 py-1.5 text-left text-[11.5px] font-bold text-txt2">Indicateur</th>
                    <th scope="col" className="border-b border-border px-2 py-1.5 text-right text-[11.5px] font-bold text-txt2">{libelleVersion(a)}</th>
                    <th scope="col" className="border-b border-border px-2 py-1.5 text-right text-[11.5px] font-bold text-txt2">{libelleVersion(b)}</th>
                    <th scope="col" className="border-b border-border px-2 py-1.5 text-right text-[11.5px] font-bold text-txt2">Écart</th>
                  </tr>
                </thead>
                <tbody>
                  {resultat.lignes.map((l) => (
                    <tr key={l.id} className={l.enEvidence ? 'bg-card-alt' : ''}>
                      <th scope="row" className="border-b border-border-soft px-2 py-2 text-left font-normal text-txt">{l.libelle}</th>
                      <td className="border-b border-border-soft px-2 py-2 text-right">{l.a}</td>
                      <td className="border-b border-border-soft px-2 py-2 text-right">{l.b}</td>
                      <td className="border-b border-border-soft px-2 py-2 text-right">
                        {l.faible ? (
                          <span className="text-txt2">{l.ecart.texte} <em className="ml-1 rounded-full bg-card-alt px-2 py-px text-[11px] font-bold not-italic">échantillon faible</em></span>
                        ) : (
                          <b className={l.enEvidence ? (l.ecart.jugement === 'favorable' ? 'text-brand-text' : 'text-[color:var(--ecart-defavorable)]') : 'font-semibold text-txt2'}>
                            {l.ecart.texte}
                            {l.enEvidence ? <em className="ml-1.5 font-bold not-italic">· {l.ecart.jugement === 'favorable' ? 'à noter, favorable' : 'à surveiller'}</em> : null}
                          </b>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
