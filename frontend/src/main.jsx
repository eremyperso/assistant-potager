import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Pages de contrôle visuel [US-052 / US-053], hors navigation applicative.
//
// ⚠️ Chargement PARESSEUX obligatoire : ces modules simulent des appels d'API
// pour s'afficher sans backend. Un import statique exécuterait leur corps au
// démarrage et cette simulation contaminerait l'application réelle (les vrais
// potagers de l'utilisateur seraient remplacés par les données de démo).
const PREVIEWS = {
  '/design-system': () => import('./views/_DesignSystemPreview.jsx'),
  '/shell': () => import('./views/_ShellPreview.jsx'),
}

const chargeur = PREVIEWS[window.location.pathname]
const Root = chargeur ? lazy(chargeur) : App

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Suspense fallback={null}>
      <Root />
    </Suspense>
  </React.StrictMode>
)
