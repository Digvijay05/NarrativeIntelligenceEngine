/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Forensic Palette
                bg: {
                    primary: '#0E1116',   // Main canvas
                    secondary: '#151A21', // Panels
                    tertiary: '#1D2430',  // Hover
                },
                border: {
                    subtle: '#2A3242',
                    strong: '#3A455C',
                },
                text: {
                    primary: '#E6E9EF',
                    secondary: '#B4BDCC',
                    muted: '#7F8AA3',
                    disabled: '#56607A',
                },
                state: {
                    active: '#4C9AFF',
                    dormant: '#8A94A6',
                    terminated: '#5A647A',
                    divergent: '#C77D3A',
                    absence: '#2F3748',
                },
                trace: {
                    line: '#6B85B7',
                    node: '#8FAADC',
                    hover: '#BFD4FF',
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            spacing: {
                '4.5': '1.125rem',
            }
        },
    },
    plugins: [],
}
