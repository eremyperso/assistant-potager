import base from '../frontend/tailwind.config.js'

// [US-311 / CA1] La configuration Tailwind du frontend (jetons de l'identité visuelle, polices,
// `nav` à 900 px, container queries) est PARTAGÉE, pas copiée : seul le périmètre scanné change,
// plus un seuil de page, `tab` (600 px), que la maquette d'US-318 utilise pour passer de 2 à 3
// colonnes de chiffres et du panneau en feuille au panneau latéral. Placé avant `nav` : Tailwind
// émet les largeurs minimales dans l'ordre de déclaration.
/** @type {import('tailwindcss').Config} */
export default {
  ...base,
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    ...base.theme,
    extend: {
      ...base.theme.extend,
      screens: { tab: '600px', ...base.theme.extend.screens },
    },
  },
}
