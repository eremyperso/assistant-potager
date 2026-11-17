import { useCallback, useEffect, useMemo, useState } from 'react'
import { creerClient } from '../lib/client.js'
import { URL_API } from '../config.js'

/**
 * Qui est connecté, et a-t-il le droit d'entrer ? [US-311 / CA3]
 *   chargement → connexion | reserve | hors_ligne | ok
 * L'accès se décide sur `/auth/me` : un compte qui n'est pas l'administrateur n'envoie AUCUNE
 * requête `/admin/...`.
 */
export function useSession() {
  const [etat, setEtat] = useState('chargement')
  const [compte, setCompte] = useState(null)

  const client = useMemo(() => creerClient({
    base: URL_API,
    stockage: window.localStorage,
    surSessionExpiree: () => window.dispatchEvent(new CustomEvent('pilotage:session-expiree')),
  }), [])

  const verifier = useCallback(async () => {
    if (!client.aUnJeton()) { setEtat('connexion'); return }
    setEtat('chargement')
    try {
      const moi = await client.moi()
      setCompte(moi)
      setEtat(moi.administrateur ? 'ok' : 'reserve')
    } catch (e) {
      setEtat(e.statut === 0 ? 'hors_ligne' : 'connexion')
    }
  }, [client])

  useEffect(() => {
    verifier()
    const surExpiration = () => { setCompte(null); setEtat('connexion') }
    window.addEventListener('pilotage:session-expiree', surExpiration)
    return () => window.removeEventListener('pilotage:session-expiree', surExpiration)
  }, [verifier])

  const connecter = useCallback(async (email, motDePasse) => {
    await client.connecter(email, motDePasse)
    await verifier()
  }, [client, verifier])

  const deconnecter = useCallback(() => {
    client.deconnecter()
    setCompte(null)
    setEtat('connexion')
  }, [client])

  return { etat, compte, client, connecter, deconnecter, reessayer: verifier }
}
