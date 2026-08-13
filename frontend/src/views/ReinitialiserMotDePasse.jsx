// [US-057 / CA2-CA4] Écran ouvert depuis le lien de réinitialisation reçu par
// e-mail (/reinitialiser-mot-de-passe?token=...). Indépendant de l'état de
// connexion, même principe que VerifyEmail.jsx (US-044).
import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { authApi } from '../lib/api.js'
import { Field } from '../components/ui'

export default function ReinitialiserMotDePasse({ token, onDone }) {
  const [statut, setStatut] = useState(token ? 'formulaire' : 'erreur') // 'formulaire' | 'succes' | 'erreur'
  const [motDePasse, setMotDePasse] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [erreur, setErreur] = useState(token ? null : 'Lien de réinitialisation invalide')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setErreur(null)

    if (motDePasse !== confirmation) {
      setErreur('Les deux mots de passe ne correspondent pas')
      return
    }

    setLoading(true)
    try {
      await authApi.reinitialiserMotDePasse(token, motDePasse)
      setStatut('succes')
    } catch (e) {
      setErreur(e.message)
      setStatut('erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center h-dvh w-full bg-bg px-6 text-center">
      <div className="w-full max-w-md bg-card border border-border rounded-2xl p-6">
        <div className="w-11 h-11 rounded-xl bg-brand-soft flex items-center justify-center mx-auto mb-3.5">
          <KeyRound size={21} className="text-brand" />
        </div>

        {statut === 'formulaire' && (
          <>
            <h1 className="font-serif text-[19px] font-bold text-txt mb-1">Nouveau mot de passe</h1>
            <p className="text-[13.5px] text-txt2 mb-5">Choisissez un mot de passe d'au moins 8 caractères.</p>
            <form onSubmit={handleSubmit} className="flex flex-col gap-3.5 text-left">
              <Field
                id="mdp"
                label="Nouveau mot de passe"
                type="password"
                required
                minLength={8}
                placeholder="Au moins 8 caractères"
                autoComplete="new-password"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
              />
              <Field
                id="mdp-confirm"
                label="Confirmer le mot de passe"
                type="password"
                required
                minLength={8}
                placeholder="Ressaisissez le mot de passe"
                autoComplete="new-password"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
              />
              {erreur && <p className="text-red text-[13px]">{erreur}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full h-12 rounded-xl bg-brand text-white dark:text-bg font-bold text-[15px] disabled:opacity-60"
              >
                {loading ? '…' : 'Réinitialiser mon mot de passe'}
              </button>
            </form>
          </>
        )}

        {statut === 'succes' && (
          <>
            <p className="text-txt text-base font-semibold mb-2">Mot de passe mis à jour</p>
            <p className="text-txt2 text-sm mb-4">Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.</p>
          </>
        )}

        {statut === 'erreur' && (
          <>
            <p className="text-red text-base font-semibold mb-2">Lien invalide</p>
            <p className="text-txt2 text-sm mb-4">
              {erreur} — vous pouvez redemander un nouveau lien depuis l'écran de connexion.
            </p>
          </>
        )}

        {statut !== 'formulaire' && (
          <button
            onClick={onDone}
            className="w-full h-12 rounded-xl bg-brand text-white dark:text-bg font-bold text-[15px]"
          >
            Aller à la connexion
          </button>
        )}
      </div>
    </div>
  )
}
