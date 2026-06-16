/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Palette jardin — les valeurs résolues via CSS vars (light/dark auto)
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
        // Alias rétrocompat
        primary: {
          DEFAULT: 'var(--g-acc)',
          light:   'var(--g-acc-dim)',
          dark:    'var(--g-mid)',
        },
      },
      fontFamily: {
        serif: ['Lora', 'Georgia', '"Times New Roman"', 'serif'],
        sans:  ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Text"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
