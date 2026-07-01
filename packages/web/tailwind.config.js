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
        // Body / UI: DM Sans — clean geometric sans, used for nav, labels,
        // and UI text across the Good Ship brand surfaces.
        sans: ['"DM Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        // Mono for org_ids, ONS codes, schema names. Also used for body copy
        // paragraphs on the Good Ship site at 16px / line-height 1.7.
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
        // Good Ship brand palette — navy/cream/teal with amber + coral
        // accents. Opt-in via ``bg-cream text-navy`` on Open Org pages;
        // other surfaces stay on plain white/gray.
        navy: '#1B2A4A',        // deep navy blue-black — primary text + headings
        'navy-light': '#243556', // slightly lighter navy for dark-section variants
        cream: '#F5F0E8',       // warm cream background
        'cream-dark': '#EBE4D8', // slightly darker inset / cards on cream bg
        teal: '#2D8B7A',        // primary accent — buttons, links, positive states
        'teal-light': '#3AA08D', // hover state for teal
        amber: '#D4993D',       // secondary accent — strategies, highlights
        'amber-light': '#E0AD56', // hover state for amber
        'grey-blue': '#8BA4B8', // muted/secondary text
        coral: '#C75B3A',       // occasional accent
        'paper-white': '#FEFCF9', // off-white (not pure white) for light surfaces
        // Hairline divider colour — close to cream-dark, used for borders.
        rule: '#EBE4D8',
      },
      letterSpacing: {
        'kicker': '0.14em',   // for small-caps kicker labels
        'display': '-0.02em', // tightened tracking for large serif heads
      },
      borderRadius: {
        'brand': '0.5rem',    // 8px — default button/card radius
        'brand-lg': '1rem',   // 16px — large card radius
      },
      transitionTimingFunction: {
        'brand': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      transitionDuration: {
        'brand': '300ms',
      },
      boxShadow: {
        'brand': '0 2px 8px rgba(27, 42, 74, 0.08)',
        'brand-lg': '0 4px 16px rgba(27, 42, 74, 0.15)',
      },
    },
  },
  plugins: [],
}