import { useCallback, useState } from 'react'
import Coquille, { texteMiseAJour } from './components/Coquille.jsx'
import VueEnAttente from './components/VueEnAttente.jsx'
import { EcranAccesReserve, EcranChargement, EcranConnexion, EcranHorsLigne } from './components/Ecrans.jsx'
import Consommation from './views/Consommation.jsx'
import { useAdresse } from './hooks/useAdresse.js'
import { useSession } from './hooks/useSession.js'

// Les vues livrées. Les autres (Coût, Fiabilité, Dérives, Potagers, Seuils) s'ouvrent sur un écran
// d'attente qui nomme l'US qui les remplira : même coquille, mêmes filtres.
const VUES_LIVREES = { consommation: Consommation }

export default function App() {
  const session = useSession()
  const { filtres, vue, changerFiltres, changerVue } = useAdresse()
  const [declencheur, setDeclencheur] = useState(0)
  const [maj, setMaj] = useState({ a: null, enPanne: false })
  const signalerMaj = useCallback((m) => setMaj((avant) => ({ a: m.a || avant.a, enPanne: m.enPanne })), [])

  // Un compte qui n'est pas l'administrateur n'atteint jamais une vue : aucune donnée n'est chargée.
  if (session.etat === 'chargement') return <EcranChargement />
  if (session.etat === 'connexion') return <EcranConnexion surConnexion={session.connecter} />
  if (session.etat === 'hors_ligne') return <EcranHorsLigne surReessai={session.reessayer} />
  if (session.etat === 'reserve') return <EcranAccesReserve compte={session.compte} surDeconnexion={session.deconnecter} />

  const Vue = VUES_LIVREES[vue]
  return (
    <Coquille
      client={session.client} compte={session.compte} vue={vue} filtres={filtres}
      majTexte={texteMiseAJour(maj)} enPanne={maj.enPanne}
      surVue={changerVue} surFiltres={changerFiltres}
      surRafraichir={() => setDeclencheur((n) => n + 1)} surDeconnexion={session.deconnecter}
    >
      {Vue
        ? <Vue client={session.client} filtres={filtres} declencheur={declencheur} signalerMaj={signalerMaj} surFiltres={changerFiltres} />
        : <VueEnAttente vue={vue} />}
    </Coquille>
  )
}
