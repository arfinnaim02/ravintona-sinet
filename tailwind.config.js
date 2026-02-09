/*
 * Tailwind CSS configuration for the Ravintola Sinet project.
 *
 * This file defines a custom colour palette inspired by a rustic
 * Finnish restaurant. It can be used when compiling Tailwind
 * locally. The project templates load Tailwind via the CDN and
 * configure these colours on the fly, but having this file
 * available makes it easy to switch to a build pipeline later.
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './restaurant/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        beige: '#f5f0e6',
        dark: '#3e2723',
        lightbrown: '#8d6e63',
        gold: '#bfa76f',
      },
    },
  },
  plugins: [],
};