/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Editorial display: variable serif with optical sizing.
        // Used for h1/h2 and emphasis, never body copy.
        display: ['"Fraunces"', 'Georgia', '"Times New Roman"', 'serif'],
        // Body / UI: USDS Public Sans — characterful but neutral, designed
        // for accessible government-style documents. Pairs with Fraunces.
        sans: ['"Public Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        // Mono for org_ids, ONS codes, schema names.
        mono: ['"JetBrains Mono"', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        // Civic-editorial paper/ink scale. Opt-in via ``bg-paper text-ink``
        // on Open Org pages; other surfaces stay on plain white/gray.
        paper: '#FAF7F2',     // warm off-white background
        'paper-2': '#F2EDE3', // slightly darker inset
        ink: '#1A1814',       // warm near-black primary text
        muted: '#6E6859',     // secondary text + dim labels (5.24:1 on paper — WCAG AA)
        rule: '#D9D2C2',      // hairline dividers and borders
      },
      letterSpacing: {
        'kicker': '0.14em',   // for small-caps kicker labels
        'display': '-0.02em', // tightened tracking for large serif heads
      },
    },
  },
  plugins: [],
}
