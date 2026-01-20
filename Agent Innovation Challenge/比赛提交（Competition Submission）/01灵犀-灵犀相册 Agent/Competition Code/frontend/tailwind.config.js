/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    DEFAULT: 'hsl(var(--primary))',
                    light: 'hsl(var(--primary-light))',
                    dark: 'hsl(var(--primary-dark))',
                    foreground: 'hsl(var(--primary-foreground))',
                },
                accent: {
                    DEFAULT: 'hsl(var(--accent))',
                    light: 'hsl(var(--accent-light))',
                },
                background: {
                    DEFAULT: 'hsl(var(--background))',
                    secondary: 'hsl(var(--background-secondary))',
                    tertiary: 'hsl(var(--background-tertiary))',
                },
                foreground: {
                    DEFAULT: 'hsl(var(--foreground))',
                    muted: 'hsl(var(--foreground-muted))',
                    subtle: 'hsl(var(--foreground-subtle))',
                },
                border: {
                    DEFAULT: 'hsl(var(--border))',
                    hover: 'hsl(var(--border-hover))',
                },
                surface: {
                    DEFAULT: 'hsl(var(--surface))',
                    hover: 'hsl(var(--surface-hover))',
                },
            },
            borderRadius: {
                sm: 'var(--radius-sm)',
                md: 'var(--radius-md)',
                lg: 'var(--radius-lg)',
                xl: 'var(--radius-xl)',
            },
            boxShadow: {
                sm: 'var(--shadow-sm)',
                md: 'var(--shadow-md)',
                lg: 'var(--shadow-lg)',
                glow: 'var(--shadow-glow)',
            },
            transitionTimingFunction: {
                'ease-smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
            },
            transitionDuration: {
                fast: '150ms',
                base: '200ms',
                slow: '300ms',
            },
            animation: {
                'spin-slow': 'spin 1.5s linear infinite',
                'fade-in': 'fadeIn 0.3s ease-out forwards',
                'slide-up': 'slideUp 0.3s ease-out forwards',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0', transform: 'translateY(10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                slideUp: {
                    '0%': { opacity: '0', transform: 'translateY(20px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
            },
        },
    },
    plugins: [],
}
