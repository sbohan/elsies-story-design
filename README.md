# Elsie's Story: Digital Brand Book

The digital brand book for [Elsie's Story](https://elsiesstory.org) (Registered Charity No 1210811). It's a single-page, scrapbook-style site covering the story, logo, colour, type, illustration, photography, voice, scrapbook materials, motion and the brand in use.

## Run it

```sh
python3 -I build.py                       # inlines the fonts and writes index.html
python3 -m http.server 8792 --bind 127.0.0.1
```

Then open http://127.0.0.1:8792/index.html.

## Layout

- `src/index.src.html`: the page source, with hash routes for each section.
- `build.py`: embeds Paperink and Lazy Dog as base64 at the `/*@FONTS@*/` marker and writes `index.html`.
- `assets/img/`: logos, illustrations, textures and photography.
- `assets/fonts/`: Paperink and Lazy Dog, which are licensed to Elsie's Story, and Jost, which is under the OFL (see `Jost-OFL.txt`).
- `assets/logo/logo-write.json`: the handwriting recording that drives the animated logo.
- `tools/`: the pipeline that turns the logo PNG into that recording: skeletonise, build the stroke graph, separate the butterfly from the handwriting, then order and time the strokes. Run `tools/build_logo.sh`.

## Colour palette

| Name | Hex | Notes |
| --- | --- | --- |
| Elsie Pink | `#E6BCC6` | our Elsie pink, the one we use most |
| Mocha | `#796867` | |
| Taupe | `#D6CAC1` | racer colour option |
| Parma Lilac | `#E8D8E3` | |
| Blush | `#EFBCC8` | |
| Paper Grey | `#F2F1EB` | racer colour option |
| Oat | `#E6D5C0` | |
| Clay | `#D4A395` | |
| White | `#FFFFFF` | |

Supporting colours: Cocoa `#574A48` and Dusky Pink `#9A5568` (small labels and accents; we stay away from red).
