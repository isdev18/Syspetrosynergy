module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        steel: "#1f2937",
        rust: "#b45309",
        sand: "#f5f5f4",
      },
      fontFamily: {
        heading: ["Oswald", "sans-serif"],
        body: ["Source Sans 3", "sans-serif"],
      },
    },
  },
  plugins: [],
};
