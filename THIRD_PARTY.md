# Third-party code

Code and other files in this repository that were made by others, with where each came from and its licence. Photos and map data are in `CREDITS.md`.

## QR Code Generator for JavaScript

- File: `frontend/js/vendor/qrcode.js`, used by `frontend/js/handoff.js` to draw the QR code of the phone link. No other file holds code from it.
- Source: https://github.com/kazuhikoarase/qrcode-generator, the npm package `qrcode-generator` 2.0.4, its file `dist/qrcode.mjs`, unchanged apart from the file name.
- Copyright (c) 2009 Kazuhiko Arase. MIT licence. The word "QR Code" is a registered trademark of DENSO WAVE INCORPORATED.

```
The MIT License (MIT)

Copyright (c) 2009 Kazuhiko Arase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## Mercature

- What: "Mercature, an editable spatial accessibility model", by Glendon Chin.
- Source: https://github.com/glendonC/mercature
- Commit the parts were taken from: `fd5514b1c8c1fa6da27ba66decf432bff03ede26`
- Licence: MIT. Copyright (c) 2026 Glendon Chin.

Parts of Mercature's interface were adapted or ported into this project's plain HTML, CSS and JavaScript. No image,
mascot artwork, wordmark or name of Mercature is used, and the colours are this project's own tokens.

| Our file | What comes from Mercature |
|---|---|
| `frontend/styles/tokens.css` | The names and sizes of the glass, shadow, radius and motion tokens (`src/style.css`). |
| `frontend/styles/ui.css` | The rules for the guide's bubble, the numbered choices (a row whose visible surface is its `::before`), the text field with its send button inside, and the floating guide (`src/ui/chat.css`). |
| `frontend/styles/views.css` | The layout of the guide's dock: the bubble at the bottom, the choices and the card it is about, the phone rules (`src/guide/guide-screen.css`, `src/ui/chat.css`). |
| `frontend/styles/map.css` | The way the tilted map is drawn in SVG classes: block roofs, lit and shaded walls, the route with its halo, the dark label pills; the sizes of the numbered marker and of the captions (`src/destinations/map.css`). The haze over the far part of the map, solid at the top and clear at 36% of the height (`src/destinations/lens.ts`, `GeographicMap.tsx`). The landing backdrop's small dots, and the three stops of the landing veil, which stand in `frontend/styles/views.css` (`src/home/Home.css`). |
| `frontend/js/map.js` | The drawing method, ported from TypeScript: rotate the world to a bearing, squash the vertical axis, paint each building's viewer-facing walls and then its roof, far to near (`src/destinations/RouteMap.tsx`). One height for every ordinary block with landmarks taller, and the blocks of a run painted all walls before all roofs (`src/destinations/GeographicMap.tsx`, `lens.ts`). Labels that keep their place on every frame of a move (`src/destinations/RouteMap.tsx`). |
| `frontend/js/main.js` | Only the idea, not code: the landing screen shows one still route in the free part beside the headline (`src/home/Home.tsx`). |

Each of these files names this source in a comment at its top, except `frontend/js/main.js`, which holds the idea and no code.

Taken later, when the landing, the guide and the panels were set at Mercature's sizes and given its motion:

| Our file | What also comes from Mercature |
|---|---|
| `frontend/styles/ui.css` | The small number keys of the choices and the guide that bobs while it speaks (`src/ui/chat.css`, `src/guide/guide.css`). How a surface answers the pointer: it brightens, lifts and deepens its shadow on hover, and a press scales the surface and not the words (`src/ui/interact.css`). |
| `frontend/styles/views.css` | The bubble on the screen's centre line with the guide left of it (`src/ui/chat.css`, `src/home/Home.css`). The landing: the column and its headline, the field with a round button of its own beside it, the washed photo card that wakes on hover, and its label (`src/home/Home.css`, `src/home/search.css`). The route note's height and the fade at its bottom (`src/ui/chat.css`). The tracking of the title while the map is made (`src/preparation/reveal.css`). The photo card's soft shape is drawn in this file as an inline SVG; Mercature's mask image is not used. |
| `frontend/js/parts.js` | `typeLine`: the guide types its sentence at 40 characters a second and the choices come 600 ms after it is whole, ported from TypeScript (`src/ui/Chat.tsx`). |
| `frontend/js/route.js` | The three lines that lift the note's fade at the end of its scroll (`src/ui/Chat.tsx`, `useScrollFade`). |

### Licence text

```
MIT License

Copyright (c) 2026 Glendon Chin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Aspekta (font)

- File: `frontend/fonts/AspektaVF.woff2`, the one font of both pages, unchanged.
- Copyright (c) 2025 Ivo Dolenc, with Reserved Font Name "Aspekta".
- Licence: SIL Open Font License, Version 1.1. The full text is beside the font in `frontend/fonts/Aspekta-LICENSE.txt`.

## Libraries that are installed, not copied

`requirements.txt` pins them; none of their code is in this repository.

| Package | What it is used for | Licence |
|---|---|---|
| `google-adk` 2.15.0 | The Agent Development Kit: the agents, the agent server, the plugin hook the guards use. | Apache License 2.0 |
| `tavily-python` 0.8.5 | The client for the web search. | MIT |
| `python-dotenv` 1.2.4 | Reads the keys from `.env`. | BSD 3-Clause |
| `mcp` 2.3.0 | The Model Context Protocol SDK: our own Google Places server and the scout's connection to it. | MIT |
