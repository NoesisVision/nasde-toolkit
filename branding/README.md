# NASDE Branding

This directory contains the source vector assets for the NASDE project brand.

## Logo Assets

- `nasde-mark.svg` - primary standalone mark.
- `nasde-mark-dark.svg` - standalone mark tuned for dark backgrounds.
- `nasde-mark-mono.svg` - single-color standalone mark.
- `nasde-wordmark.svg` - wordmark without the mark.
- `nasde-lockup.svg` - primary horizontal lockup with mark, wordmark, and acronym expansion.
- `nasde-lockup-card.svg` - primary horizontal lockup on a light background for README and other mixed-theme surfaces.
- `nasde-lockup-simple.svg` - horizontal lockup with mark and wordmark.
- `nasde-stacked.svg` - stacked lockup for square placements.

## Usage

- The repository README uses `branding/nasde-lockup-card.svg`.
- The documentation website header uses `website/src/assets/nasde-mark.png`.
- The documentation website hero uses `website/public/nasde-toolkit-hero.svg`.
- Favicons are generated into `website/public/favicon.svg` and `website/public/favicon.png`.

Prefer the SVG files in this directory as the source of truth. Regenerate raster
or website-specific assets from these vectors when a derived asset needs to
change.
