import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import DesignSystemPreview from './views/_DesignSystemPreview.jsx'
import ShellPreview from './views/_ShellPreview.jsx'
import './index.css'

// Pages de contrôle visuel [US-052 / US-053], hors navigation applicative.
const PREVIEWS = {
  '/design-system': DesignSystemPreview,
  '/shell': ShellPreview,
}
const Root = PREVIEWS[window.location.pathname] ?? App

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
