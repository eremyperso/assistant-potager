import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import './brand.css'

// Pages de contrôle visuel [US-052 / US-053], hors navigation applicative.
//
// ⚠️ Chargement PARESSEUX obligatoire : ces modules simulent des appels d'API
// pour s'afficher sans backend. Un import statique exécuterait leur corps au
// démarrage et cette simulation contaminerait l'application réelle (les vrais
// potagers de l'utilisateur seraient remplacés par les données de démo).
const PREVIEWS = {
  '/design-system': () => import('./views/_DesignSystemPreview.jsx'),
  '/shell': () => import('./views/_ShellPreview.jsx'),
  '/fiche-calendrier': () => import('./views/_FicheCalendrierPreview.jsx'),  // [US-183]
  '/fiche-culture': () => import('./views/_FicheCulturePreview.jsx'),  // [US-207]
  '/plan-dessus': () => import('./views/_PlanDessusPreview.jsx'),  // [US-327 / CA8]
  '/fiche-lot': () => import('./views/_FicheLotPreview.jsx'),  // [US-216]
  '/pepiniere-parcours': () => import('./views/_PepiniereParcoursPreview.jsx'),  // [US-218]
  '/pepiniere-lots': () => import('./views/_PepiniereLotsPreview.jsx'),  // [US-242]
  '/regle-temps': () => import('./views/_RegleTempsPreview.jsx'),  // règle des temps
  '/etapes': () => import('./views/_EtapesPreview.jsx'),  // [US-321]
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
