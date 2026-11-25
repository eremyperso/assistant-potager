import containerQueries from '@tailwindcss/container-queries'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      screens: {
        // Seuil de bascule de la navigation principale : bandeau haut au-dessus,
        // barre d'onglets basse en dessous [US-053 / CA1]. Breakpoint d'écran
        // assumé — c'est de la structure de page globale, seul cas autorisé par
        // la règle « Responsive frontend » de CLAUDE.md.
        nav: '900px',
      },
      colors: {
        // ─── Palette refonte 2026 (tokens sémantiques) ───
        bg:            'var(--bg)',
        surface:       'var(--surface)',
        card:          'var(--card)',
        'card-alt':    'var(--card-alt)',
        border:        'var(--border)',
        'border-soft': 'var(--border-soft)',

        brand:         'var(--brand)',
        'brand-deep':  'var(--brand-deep)',
        'brand-soft':  'var(--brand-soft)',
        'brand-text':  'var(--brand-text)',

        txt:           'var(--txt)',
        txt2:          'var(--txt2)',
        txt3:          'var(--txt3)',

        amber:         'var(--amber)',
        'amber-soft':  'var(--amber-soft)',
        red:           'var(--red)',
        'red-soft':    'var(--red-soft)',
        blue:          'var(--blue)',
        'blue-soft':   'var(--blue-soft)',
        // [US-218] Stades du parcours du plant.
        sem: 'var(--sem)', 'sem-d': 'var(--sem-d)', 'sem-s': 'var(--sem-s)',
        god: 'var(--god)', 'god-d': 'var(--god-d)', 'god-s': 'var(--god-s)',
        end: 'var(--end)', 'end-d': 'var(--end-d)', 'end-s': 'var(--end-s)',
        frk: 'var(--frk)', 'frk-d': 'var(--frk-d)', 'frk-s': 'var(--frk-s)',
        violet:        'var(--violet)',
        'violet-soft': 'var(--violet-soft)',

        // [US-352 / CA1] Dû, autre jour, carnet du jardinier, pépinière, sol.
        due: 'var(--due)', 'due-bg': 'var(--due-bg)', 'due-bd': 'var(--due-bd)', 'due-tx': 'var(--due-tx)',
        'amb-bg': 'var(--amb-bg)', 'amb-bd': 'var(--amb-bd)', 'amb-tx': 'var(--amb-tx)',
        ink: 'var(--ink)', paper: 'var(--paper)', 'paper-bd': 'var(--paper-bd)',
        pep: 'var(--pep)', 'pep-soft': 'var(--pep-soft)',
        soil: 'var(--soil)', 'soil-bd': 'var(--soil-bd)',
        btn: 'var(--btn)',

        'header-from':  'var(--header-from)',
        'header-to':    'var(--header-to)',
        'header-txt':   'var(--header-txt)',
        'header-dim':   'var(--header-dim)',
        'header-glass': 'var(--header-glass)',

        // ─── Alias de compatibilité (anciens noms → nouvelle palette) ───
        // [US-064] Lot B clôturé, cf. le commentaire jumeau dans src/index.css pour
        // la liste nominative des fichiers qui retiennent encore ce bloc et la
        // condition de sa suppression (docs/ANALYSE_REFONTE_UI_WEB_2026.md §7.4).
        'g-bg':      'var(--g-bg)',
        'g-sur':     'var(--g-sur)',
        'g-card':    'var(--g-card)',
        'g-brd':     'var(--g-brd)',
        'g-acc':     'var(--g-acc)',
        'g-acc-dim': 'var(--g-acc-dim)',
        'g-pri':     'var(--g-pri)',
        'g-sec':     'var(--g-sec)',
        'g-mid':     'var(--g-mid)',
        'g-amb':     'var(--g-amb)',
        'g-amb-dim': 'var(--g-amb-dim)',
        'g-red':     'var(--g-red)',
        'g-red-dim': 'var(--g-red-dim)',
      },
      boxShadow: {
        card: 'var(--shadow)',
      },
      fontFamily: {
        serif: ['Lora', 'Georgia', '"Times New Roman"', 'serif'],
        // [US-352 / CA6] Kalam est RÉSERVÉE au texte dicté ou écrit par le jardinier (note du
        // carnet, bulle du jardinier). Ni le nom de Gaston, ni un titre de carte, ni une date.
        // Les anciens usages de la pépinière (jalons « J34 », chiffres) sont recensés par
        // `lib/kalam.test.js` et sortent avec US-356.
        hand:  ['Kalam', 'cursive'],
        sans:  ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Text"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [
    // Requis par la règle « Responsive frontend » de CLAUDE.md : tout composant
    // réutilisable s'adapte via @container, pas via les breakpoints d'écran.
    containerQueries,
  ],
}
