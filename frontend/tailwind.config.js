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
        violet:        'var(--violet)',
        'violet-soft': 'var(--violet-soft)',

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
