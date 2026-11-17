import { useCallback, useState } from 'react'
import Coquille, { texteMiseAJour } from './components/Coquille.jsx'
import VueEnAttente from './components/VueEnAttente.jsx'
import { EcranAccesReserve, EcranChargement, EcranConnexion, EcranHorsLigne } from './components/Ecrans.jsx'
import Consommation from './views/Consommation.jsx'
import Cout from './views/Cout.jsx'
import Derives from './views/Derives.jsx'
import Fiabilite from './views/Fiabilite.jsx'
import Potagers from './views/Potagers.jsx'
import Seuils from './views/Seuils.jsx'
import { useAdresse } from './hooks/useAdresse.js'
import { useAlertesOuvertes } from './hooks/useAlertesOuvertes.js'
import { useSession } from './hooks/useSession.js'

// Les vues livrées : toutes les six. `VueEnAttente` reste le repli d'une vue qui serait ajoutée à la navigation
// avant d'être livrée : même coquille, mêmes filtres.
const VUES_LIVREES = { consommation: Consommation, cout: Cout, fiabilite: Fiabilite, derives: Derives, potagers: Potagers, seuils: Seuils }

export default function App() {
  const session = useSession()
  const { filtres, vue, changerFiltres, changerVue } = useAdresse()
  const [declencheur, setDeclencheur] = useState(0)
  const [maj, setMaj] = useState({ a: null, enPanne: false })
  const alertesOuvertes = useAlertesOuvertes(session.client, session.etat === 'ok', declencheur)
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
      majTexte={texteMiseAJour(maj)} enPanne={maj.enPanne} alertesOuvertes={alertesOuvertes}
      surVue={changerVue} surFiltres={changerFiltres}
      surRafraichir={() => setDeclencheur((n) => n + 1)} surDeconnexion={session.deconnecter}
    >
      {Vue
        ? <Vue client={session.client} filtres={filtres} declencheur={declencheur} signalerMaj={signalerMaj} surFiltres={changerFiltres} surVue={changerVue} />
        : <VueEnAttente vue={vue} />}
    </Coquille>
  )
}
