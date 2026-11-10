// [US-290 / CA2, CA3] Page de consentement d'un assistant IA (Claude, ChatGPT, Le Chat).
// Ouverte par `/oauth/authorize` (→ /connecteur-ia?demande=…), une fois le jardinier
// connecté avec son compte. Elle nomme l'assistant, la portée (lecture cochée d'office,
// écriture à cocher), les potagers, et prévient que les données lues partent chez
// l'éditeur de l'assistant (L17). La réponse renvoie le jardinier vers son assistant.
import { useEffect, useState } from 'react'
import { Plug, ShieldAlert } from 'lucide-react'
import { connecteurApi } from '../lib/api.js'
import { ecriturePossible, oublierDemande, potagersPreselectionnes } from '../lib/connecteurIa.js'
import { InfoBanner } from '../components/ui'

const LIBELLES_ROLE = { owner: 'propriétaire', editor: 'éditeur', lecteur: 'lecteur' }

function CaseACocher({ id, checked, disabled, onChange, titre, detail }) {
  return (
    <label
      htmlFor={id}
      className={`flex items-start gap-3 rounded-xl border border-border px-3.5 py-3 ${disabled ? 'opacity-80' : 'cursor-pointer'}`}
    >
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 w-4 h-4 accent-brand shrink-0"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span className="min-w-0">
        <span className="block text-[14px] font-semibold text-txt">{titre}</span>
        {detail && <span className="block text-[12.5px] text-txt2 mt-0.5 leading-snug">{detail}</span>}
      </span>
    </label>
  )
}

export default function ConsentementConnecteur({ demande, onAbandon }) {
  const [etat, setEtat] = useState('chargement') // chargement | formulaire | envoi | erreur
  const [infos, setInfos] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [ecriture, setEcriture] = useState(false)
  const [choisis, setChoisis] = useState([])

  useEffect(() => {
    let actif = true
    connecteurApi
      .demande(demande)
      .then((donnees) => {
        if (!actif) return
        setInfos(donnees)
        setChoisis(potagersPreselectionnes(donnees.potagers))
        setEtat('formulaire')
      })
      .catch(() => {
        if (!actif) return
        setErreur('Cette demande de connexion a expiré ou n’est plus valable. Relancez la connexion depuis votre assistant.')
        setEtat('erreur')
      })
    return () => { actif = false }
  }, [demande])

  const ecritureOuverte = infos ? ecriturePossible(infos.potagers, choisis) : false

  function basculerPotager(id, coche) {
    setChoisis((liste) => (coche ? [...new Set([...liste, id])] : liste.filter((x) => x !== id)))
  }

  async function repondre(accepte) {
    setEtat('envoi')
    setErreur(null)
    try {
      const { redirection } = await connecteurApi.consentir({
        demande, accepte, ecriture: accepte && ecriture && ecritureOuverte, potagerIds: accepte ? choisis : [],
      })
      oublierDemande()
      window.location.assign(redirection)
    } catch (e) {
      setErreur(e.message)
      setEtat('formulaire')
    }
  }

  const nom = infos?.client?.nom || 'Un assistant'

  return (
    <div className="min-h-dvh w-full bg-bg px-4 py-8 flex justify-center">
      <div className="w-full max-w-md">
        <div className="bg-card border border-border rounded-2xl p-5 sm:p-6">
          <div className="w-11 h-11 rounded-xl bg-brand-soft flex items-center justify-center mb-3.5">
            <Plug size={21} className="text-brand" />
          </div>

          {etat === 'chargement' && <p className="text-txt2 text-sm">Chargement de la demande…</p>}

          {etat === 'erreur' && (
            <>
              <h1 className="font-serif text-[19px] font-bold text-txt mb-2">Connexion impossible</h1>
              <p className="text-txt2 text-sm mb-4">{erreur}</p>
              <button
                onClick={() => { oublierDemande(); onAbandon?.() }}
                className="w-full h-12 rounded-xl bg-brand text-white dark:text-bg font-bold text-[15px]"
              >
                Aller à mon potager
              </button>
            </>
          )}

          {(etat === 'formulaire' || etat === 'envoi') && infos && (
            <>
              <h1 className="font-serif text-[19px] font-bold text-txt mb-1 break-words">
                Connecter {nom} à votre potager
              </h1>
              <p className="text-[13.5px] text-txt2 mb-1">
                <strong className="text-txt">{nom}</strong> demande l’accès à votre compte Les bons gestes.
              </p>
              <p className="text-[12px] text-txt3 mb-5 break-all">Retour vers : {infos.client.retour}</p>

              <h2 className="text-[12px] font-bold uppercase tracking-wide text-txt3 mb-2">Ce que l’assistant pourra faire</h2>
              <div className="flex flex-col gap-2 mb-5">
                <CaseACocher
                  id="portee-lecture"
                  checked
                  disabled
                  titre="Lire mon potager"
                  detail="Plan, cultures, pépinière, stock, carnet, météo et statistiques."
                />
                <CaseACocher
                  id="portee-ecriture"
                  checked={ecriture && ecritureOuverte}
                  disabled={!ecritureOuverte}
                  onChange={setEcriture}
                  titre="Proposer des enregistrements"
                  detail={
                    ecritureOuverte
                      ? 'Gestes, parcelles, rappels. Rien n’est enregistré sans votre confirmation ; aucune suppression.'
                      : 'Indisponible : vous êtes lecteur sur les potagers choisis.'
                  }
                />
                {infos.ecriture_demandee && !ecriture && ecritureOuverte && (
                  <p className="text-[12.5px] text-txt3 px-1">
                    L’assistant demande aussi l’écriture : laissez décoché pour une connexion en lecture seule.
                  </p>
                )}
              </div>

              <h2 className="text-[12px] font-bold uppercase tracking-wide text-txt3 mb-2">Potagers concernés</h2>
              {infos.potagers.length === 0 ? (
                <p className="text-sm text-txt2 mb-5">Vous n’avez encore aucun potager actif à partager.</p>
              ) : (
                <div className="flex flex-col gap-2 mb-5">
                  {infos.potagers.map((p) => (
                    <CaseACocher
                      key={p.id}
                      id={`potager-${p.id}`}
                      checked={choisis.includes(p.id)}
                      onChange={(coche) => basculerPotager(p.id, coche)}
                      titre={p.nom}
                      detail={`Vous êtes ${LIBELLES_ROLE[p.role] || p.role}${p.actif ? ' · potager actif' : ''}`}
                    />
                  ))}
                </div>
              )}

              <InfoBanner
                tint="amber"
                icon={ShieldAlert}
                dismissible={false}
                className="mb-5"
                title="Vos données quittent Les bons gestes"
                body={`Ce que ${nom} lira part chez son éditeur (Anthropic, OpenAI, Mistral…) et suit sa politique de confidentialité et de conservation. Nous ne pouvons ni l’effacer ni le contrôler. Vous pourrez révoquer cette connexion à tout moment.`}
              />

              {erreur && <p className="text-red text-[13px] mb-3">{erreur}</p>}

              <div className="flex flex-col-reverse sm:flex-row gap-2.5">
                <button
                  onClick={() => repondre(false)}
                  disabled={etat === 'envoi'}
                  className="w-full sm:flex-1 h-12 rounded-xl border border-border bg-card text-txt2 font-semibold text-[15px] disabled:opacity-60"
                >
                  Refuser
                </button>
                <button
                  onClick={() => repondre(true)}
                  disabled={etat === 'envoi' || choisis.length === 0}
                  className="w-full sm:flex-1 h-12 rounded-xl bg-brand text-white dark:text-bg font-bold text-[15px] disabled:opacity-60"
                >
                  {etat === 'envoi' ? '…' : 'Autoriser'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
