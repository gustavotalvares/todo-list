/** @type {import('tailwindcss').Config} */

module.exports = {
  content: ["./src/**/*.{html,js}"],
  theme: {
    extend: {
      colors: {
        coolors: {
          blue: {
            100: '#CAF0F8',
            200: '#90E0EF',
            300: '#00B4D8',
            400: '#0077B6',
            500: '#03045E',
          },
        },
      }
    },
  },
  plugins: [],
}

