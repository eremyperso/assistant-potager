// [US-294] Écran « Assistants connectés » — menu Compte.
//
// Les assistants IA (Claude, ChatGPT, Le Chat, jetons personnels) qui ont accès aux potagers du
// jardinier : qui, depuis quand, jusqu'où, avec quelle activité — et le moyen de leur retirer
// l'accès (CA1 à CA4). Le contenu des appels n'est jamais affiché : le journal n'en garde pas.
//
// Rendu en `Modal` comme les autres destinations du menu Compte. Le contenu vit dans un
// conteneur (`@container/assistants`) : la mise en page suit la largeur de la fenêtre, pas celle
// de l'écran (frontend/CLAUDE.md).
//
// ⚠️ Pas de maquette de référence au moment de l'écriture (« à produire dans Claude Design » dans
// l'US) : structure et styles repris des modales voisines (Mon compagnon), à recaler sur la maquette.
import { useCallback, useEffect, useState } from 'react'
import { Check, Copy, ExternalLink, KeyRound, Plug, Plus, ShieldCheck } from 'lucide-react'
import { connecteurApi } from '../lib/api.js'
import {
  AIDE_ASSISTANTS, DUREES_JETON, LIBELLE_RESULTAT, LIBELLE_STATUT, TEINTE_RESULTAT, dateCourte,
  libelleOutil, lienGeste, potagersDits, revocable, trierConnexions,
} from '../lib/assistants.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { Badge, Btn, Card, InfoBanner, Modal, SectionLabel } from './ui'

const TEINTE_STATUT = { active: 'brand', revoquee: 'red', expiree: 'amber' }

function Activite({ id }) {
  const [appels, setAppels] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let actif = true
    connecteurApi.activite(id)
      .then((r) => { if (actif) setAppels(r.appels) })
      .catch((e) => { if (actif) setErreur(e.message) })
    return () => { actif = false }
  }, [id])

  if (erreur) return <div role="alert" className="text-[13px] text-red">{erreur}</div>
  if (!appels) return <div className="text-[13px] text-txt3">Chargement…</div>
  if (!appels.length) return <div className="text-[13px] text-txt3">Aucun appel pour l’instant.</div>
  return (
    <ul className="flex flex-col gap-1.5 max-h-[260px] overflow-y-auto" aria-label="Derniers appels">
      {appels.map((a, i) => {
        const lien = lienGeste(a)
        return (
          <li key={i} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-txt2">
            <span className="text-txt3 tabular-nums">{dateCourte(a.date)}</span>
            <span className="font-semibold text-txt">{libelleOutil(a.outil)}</span>
            {a.potager && <span>· {a.potager}</span>}
            <Badge tint={TEINTE_RESULTAT[a.resultat] || 'amber'}>{LIBELLE_RESULTAT[a.resultat] || a.resultat}</Badge>
            {lien && (
              <a href={lien} className="inline-flex items-center gap-1 text-brand-text underline">
                Voir le geste <ExternalLink size={12} aria-hidden="true" />
              </a>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function LigneConnexion({ connexion, onRevoquer, occupe }) {
  const [activite, setActivite] = useState(false)
  const [confirmer, setConfirmer] = useState(false)
  const c = connexion
  return (
    <Card pad="p-3">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {c.type === 'personnel' ? <KeyRound size={16} className="text-brand shrink-0" aria-hidden="true" />
            : <Plug size={16} className="text-brand shrink-0" aria-hidden="true" />}
          <span className="text-[14.5px] font-bold text-txt">{c.client}</span>
          <Badge tint={TEINTE_STATUT[c.statut] || 'amber'}>{LIBELLE_STATUT[c.statut] || c.statut}</Badge>
          <Badge tint={c.portee === 'ecriture' ? 'violet' : 'blue'}>{c.portee_libelle}</Badge>
        </div>
        <dl className="grid gap-x-4 gap-y-1 text-[12.5px] text-txt2 @[420px]/assistants:grid-cols-2">
          <div><dt className="inline text-txt3">Connecté le </dt><dd className="inline">{dateCourte(c.cree_le)}</dd></div>
          <div><dt className="inline text-txt3">Dernier appel </dt><dd className="inline">{dateCourte(c.dernier_appel_le)}</dd></div>
          <div className="@[420px]/assistants:col-span-2">
            <dt className="inline text-txt3">Potagers </dt><dd className="inline">{potagersDits(c.potagers)}</dd>
          </div>
          {c.statut === 'revoquee' && (
            <div className="@[420px]/assistants:col-span-2">
              <dt className="inline text-txt3">Révoquée le </dt><dd className="inline">{dateCourte(c.revoque_le)}</dd>
            </div>
          )}
          {c.type === 'personnel' && c.expire_le && c.statut !== 'revoquee' && (
            <div className="@[420px]/assistants:col-span-2">
              <dt className="inline text-txt3">Expire le </dt><dd className="inline">{dateCourte(c.expire_le)}</dd>
            </div>
          )}
        </dl>

        <div className="flex flex-wrap gap-2">
          <Btn small kind="ghost" onClick={() => setActivite((v) => !v)} aria-expanded={activite}>
            {activite ? 'Masquer l’activité' : 'Activité'}
          </Btn>
          {revocable(c) && !confirmer && (
            <Btn small kind="quiet" onClick={() => setConfirmer(true)} disabled={occupe}>Révoquer</Btn>
          )}
        </div>

        {confirmer && (
          <div role="alertdialog" aria-label={`Révoquer ${c.client}`}
            className="flex flex-col gap-2 rounded-xl bg-red-soft p-3 @[420px]/assistants:flex-row @[420px]/assistants:items-center">
            <p className="flex-1 text-[13px] text-txt">
              Révoquer <strong>{c.client}</strong> ? L’accès est coupé tout de suite ; pour le rétablir, il faudra
              reconnecter l’assistant.
            </p>
            <div className="flex gap-2">
              <Btn small kind="primary" onClick={() => onRevoquer(c.id)} disabled={occupe}>Oui, révoquer</Btn>
              <Btn small kind="ghost" onClick={() => setConfirmer(false)}>Annuler</Btn>
            </div>
          </div>
        )}

        {activite && <Activite id={c.id} />}
      </div>
    </Card>
  )
}

function FormulaireJeton({ potagers, onCree, onAnnuler }) {
  const [libelle, setLibelle] = useState('')
  const [ecriture, setEcriture] = useState(false)
  const [choisis, setChoisis] = useState(() => potagers.filter((p) => p.actif).map((p) => p.id))
  const [jours, setJours] = useState(30)
  const [erreur, setErreur] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  async function creer(e) {
    e.preventDefault()
    if (envoi) return
    setEnvoi(true)
    setErreur(null)
    try {
      onCree(await connecteurApi.creerJeton({ libelle: libelle.trim(), ecriture, potagerIds: choisis, dureeJours: jours }))
    } catch (err) {
      setErreur(err.message)
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={creer} className="flex flex-col gap-3">
      {erreur && <div role="alert" className="text-[13px] text-red">{erreur}</div>}
      <label className="flex flex-col gap-1 text-[13px] text-txt2">
        Nom du jeton
        <input value={libelle} maxLength={120} onChange={(e) => setLibelle(e.target.value)} required
          placeholder="Ex. MCP Inspector"
          className="text-[14px] bg-surface border border-border rounded-[9px] px-3 py-2 text-txt" />
      </label>
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-[13px] text-txt2 mb-1">Potagers</legend>
        {potagers.filter((p) => !p.assistants_externes_interdits).map((p) => (
          <label key={p.id} className="flex items-center gap-2 text-[13.5px] text-txt">
            <input type="checkbox" className="w-4 h-4 accent-brand" checked={choisis.includes(p.id)}
              onChange={(e) => setChoisis((l) => (e.target.checked ? [...l, p.id] : l.filter((x) => x !== p.id)))} />
            {p.nom}
          </label>
        ))}
      </fieldset>
      <label className="flex items-center gap-2 text-[13.5px] text-txt">
        <input type="checkbox" className="w-4 h-4 accent-brand" checked={ecriture} onChange={(e) => setEcriture(e.target.checked)} />
        Autoriser l’écriture (sur confirmation, jamais de suppression)
      </label>
      <label className="flex flex-col gap-1 text-[13px] text-txt2">
        Validité
        <select value={jours} onChange={(e) => setJours(Number(e.target.value))}
          className="text-[14px] bg-surface border border-border rounded-[9px] px-3 py-2 text-txt">
          {DUREES_JETON.map((d) => <option key={d.jours} value={d.jours}>{d.libelle}</option>)}
        </select>
      </label>
      <div className="flex gap-2">
        <Btn kind="primary" type="submit" disabled={envoi || !libelle.trim() || !choisis.length}>Créer le jeton</Btn>
        <Btn kind="ghost" type="button" onClick={onAnnuler}>Annuler</Btn>
      </div>
    </form>
  )
}

function JetonAffiche({ resultat, onFermer }) {
  const [copie, setCopie] = useState(false)
  async function copier() {
    try {
      await navigator.clipboard.writeText(resultat.jeton)
      setCopie(true)
    } catch { /* presse-papiers refusé : le jeton reste sélectionnable */ }
  }
  return (
    <div className="flex flex-col gap-2" role="status">
      <InfoBanner title="Copiez ce jeton maintenant"
        body="Il n’est affiché qu’une seule fois : nous n’en gardons que l’empreinte. Perdu, il faudra en créer un autre." />
      <code className="block break-all rounded-[9px] bg-surface border border-border px-3 py-2 text-[12.5px] text-txt select-all">
        {resultat.jeton}
      </code>
      <div className="text-[12.5px] text-txt3">Adresse du connecteur : <span className="select-all">{resultat.url_connecteur}</span></div>
      <div className="flex gap-2">
        <Btn small kind="primary" icon={copie ? Check : Copy} onClick={copier}>{copie ? 'Copié' : 'Copier'}</Btn>
        <Btn small kind="ghost" onClick={onFermer}>J’ai copié le jeton</Btn>
      </div>
    </div>
  )
}

export default function ModalAssistantsConnectes({ onClose }) {
  const { potagers } = usePotager()
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [mode, setMode] = useState('liste') // liste | jeton | jeton-cree
  const [jeton, setJeton] = useState(null)

  const charger = useCallback(
    () => connecteurApi.connexions().then(setDonnees).catch((e) => setErreur(e.message)),
    [],
  )
  useEffect(() => { charger() }, [charger])

  async function revoquer(id) {
    setOccupe(true)
    setErreur(null)
    try {
      await connecteurApi.revoquer(id)
      await charger()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setOccupe(false)
    }
  }

  const connexions = donnees ? trierConnexions(donnees.connexions) : []
  const vide = donnees && !connexions.length

  return (
    <Modal
      title="Assistants connectés"
      icon={Plug}
      sub="Qui a accès à vos potagers"
      onClose={onClose}
      width={560}
      disposition="adaptative"
      bodyClassName="p-4 overflow-y-auto min-h-0 flex-1 @container/assistants"
      foot="Un assistant connecté lit vos données : elles suivent la politique de son éditeur."
    >
      {erreur && <div role="alert" className="mb-3 text-[13px] text-red">{erreur}</div>}
      {!donnees && !erreur && <div className="text-[13px] text-txt3">Chargement…</div>}

      {donnees && (
        <div className="flex flex-col gap-4">
          {/* [CA7] Le mode d'emploi (US-295) et la politique de l'éditeur. */}
          <InfoBanner title={AIDE_ASSISTANTS.titre} body={AIDE_ASSISTANTS.texte} />

          {mode === 'liste' && (
            <>
              <section>
                <SectionLabel>Connexions</SectionLabel>
                {vide ? (
                  <Card pad="p-3">
                    <p className="text-[13.5px] text-txt2">
                      Aucun assistant n’est connecté. Ajoutez l’adresse du connecteur dans Claude, ChatGPT ou Le Chat :{' '}
                      <span className="select-all font-semibold">{donnees.url_connecteur}</span>
                    </p>
                  </Card>
                ) : (
                  <div className="flex flex-col gap-2">
                    {connexions.map((c) => (
                      <LigneConnexion key={c.id} connexion={c} onRevoquer={revoquer} occupe={occupe} />
                    ))}
                  </div>
                )}
              </section>
              <div>
                <Btn small kind="soft" icon={Plus} onClick={() => setMode('jeton')}>Créer un jeton personnel</Btn>
              </div>
            </>
          )}

          {mode === 'jeton' && (
            <section>
              <SectionLabel>Jeton personnel</SectionLabel>
              <Card pad="p-3">
                <FormulaireJeton potagers={potagers} onAnnuler={() => setMode('liste')}
                  onCree={(r) => { setJeton(r); setMode('jeton-cree'); charger() }} />
              </Card>
            </section>
          )}

          {mode === 'jeton-cree' && jeton && (
            <section>
              <SectionLabel>Jeton personnel</SectionLabel>
              <Card pad="p-3"><JetonAffiche resultat={jeton} onFermer={() => { setJeton(null); setMode('liste') }} /></Card>
            </section>
          )}

          <p className="flex items-start gap-2 text-[12.5px] text-txt3">
            <ShieldCheck size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
            Le propriétaire d’un potager partagé peut interdire les assistants externes dans les paramètres du potager.
          </p>
        </div>
      )}
    </Modal>
  )
}
