# Static Archive branding

The mark is the glitch block: a solid slab of three bands with the middle band slipped one step to the right. Static, in one move. It is built on a 100-unit grid: bands are 24 tall with 4-unit gaps, inscribed in a 10 to 90 square, the middle band offset 12.

## Files

| file | use |
|---|---|
| `mark.svg` | the mark in ink, transparent background. Default everywhere on paper. |
| `mark-paper.svg` | the mark in paper, for ink or photographic backgrounds. |
| `mark-tile.svg` | paper mark on an ink tile. App icons, avatars, anywhere a square is required. |
| `favicon.svg` | the mark with a `prefers-color-scheme` swap so it stays visible on dark browser chrome. |
| `favicon.ico` | 16, 32, 48 px, for browsers that ignore SVG favicons. |
| `wordmark.svg` | mark plus STATIC ARCHIVE, outlined, ink. |
| `wordmark-paper.svg` | same lockup in paper. |
| `wordmark-text.svg` | the wordmark alone, outlined. |
| `png/mark-*.png` | transparent rasters of the mark at 16 to 512 px. |
| `png/icon-192.png`, `png/icon-512.png` | tile rasters for web app manifests. |
| `png/apple-touch-icon.png` | 180 px tile for iOS home screens. |

## Colours

| name | hex | role |
|---|---|---|
| ink | `#1c1a17` | thermal print black |
| paper | `#f4f3f0` | receipt white |
| scanner | `#dedddb` | page background |
| stamp | `#b23a2c` | the 済 SOLD red, accents only |

The mark is always one colour. Never a gradient, never an outline, never rotated.

## Type

Wordmark is Share Tech Mono, all caps, tracked at 0.18 em. In the lockup the mark sits at 1.2× the cap height, gap of 0.5× cap height to the text. The wordmark SVGs are outlined so they need no font installed.

## Clear space and minimum size

Keep clear space around the mark equal to the height of one band (24 units, roughly a quarter of the mark). Minimum size 16 px; below that use the tile.

## Site

The site header and footer render the mark inline from `web/src/components/marketing/Logo.tsx` in `currentColor`. Favicons live in `web/src/app/` (`icon.svg`, `apple-icon.png`, `favicon.ico`), which Next picks up by convention.
