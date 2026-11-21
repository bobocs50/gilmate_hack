# Devpost submission: Gilmate

Copy each section into the matching Devpost field.

---

## Project name

Gilmate

---

## Elevator pitch (max 200 characters)

A multi-agent tour guide that plans walks around what your parents love and can manage, with every distance, stair and bench checked against real map data.

---

## About the project (Markdown)

## Inspiration

For months, my mom has been asking me one thing: *come to Japan with me.* She studies Japanese every day. I keep saying "soon". I work full-time as an intern, and next year I will be abroad for a semester with a part-time job. Everything gets delayed.

By one estimate (Tim Urban's), by the time we finish school about **93%** of the in-person time we will ever spend with our parents is already behind us. I feel that. And at the same time, my parents finally have the time and the money they worked so hard for to see the world, but every year exploring it gets harder. The walks feel longer, the stairs feel steeper.

Most trip planners know the city and nothing about the person walking it. They will happily send someone with a bad knee up three flights of stairs, and say it is "a short walk". I wanted the opposite: **a tour guide that plans around the person, not the city**, and that says "I don't know" instead of guessing.

## What it does

Gilmate is a multi-agent tour guide. Today it knows two areas: **Shibuya in Tokyo** and **Hongdae in Seoul**.

1. **Say where you want to go, in your own words.** For example: *"My mom wants to visit Shibuya. She loves sushi. Stairs are hard for her, and she can walk about 1 km before she needs to sit down."*
2. **Watch the map being made.** Agents search the web and Google Places for sights, shops and restaurants, and put real places on a map with real photos.
3. **Choose.** One place at a time: Yes or No.
4. **Get one route you can actually walk.** Every walk with its distance, the stairs on the way, the benches where you can sit, street photos of the way, and today's weather.
5. **Take it with you.** A QR code opens the route on a phone, stop by stop. After each walk: *Fine* or *Too far*.
6. **See what it remembers.** A knowledge graph shows everything Gilmate knows about you, where each fact came from, and lets you delete any of it.

## How we built it

**The agents.** Gilmate runs on **Google's Agent Development Kit (ADK)**, with **Claude Sonnet** as the model. One **coordinator** reads each step and hands the work to four specialists:

| Agent | Its job |
| --- | --- |
| **Scout** | Finds places: sights, shops and restaurants. Searches the web with Tavily, and **Google Places through an MCP server we built**. |
| **Router** | Puts her stops in order and checks today's weather. |
| **Critic** | Reviews the route before she sees it, and sends it back to the router if something is wrong (at most twice). |
| **Companion** | Answers her questions on the way, only from the facts of her route. |

**Google Places over MCP.** We wrote a small MCP server (`places_server.py`) that wraps the Places API (New) and only reads. The scout gets it through ADK's `McpToolset`. It returns what matters for her: the rating and how many people rated it, the opening hours, and whether the entrance is step-free. A Google record is attached to a place only when the names agree and the two points are at most 80 m apart. The map stays the truth.

**The spatial model.** The heart of Gilmate is plain Python, not the model. For every walk between two stops, code follows the real paths from **OpenStreetMap**, measures the distance, finds the steps and the benches, and collects street photos from **Mapillary** and photos of the places from **Wikimedia Commons**, each with its author and licence.

**Weather.** **Open-Meteo** gives the forecast, and Python turns it into a fixed list of dangers: rain, heat, wind, cold, darkness and more. No model judges the weather. If rain or great heat is likely, her walking limit for that route drops by a quarter (a 1,000 m limit becomes 750 m), and any walk that would end after sunset is flagged.

**Memory as a knowledge graph.** Every choice she makes is stored: her picks, what she can manage, and the walks that were too far. One *Too far* tap sets her limit for that day to 10 m less than that walk. A second tap keeps it for the next route. A learned limit can only make routes shorter, never longer than what she said herself. Only Python writes the memory, never web text or model text.

**Security.** One rule runs through everything: *the model writes the sentences, code owns every fact.*

- **Deny by default.** Every tool call is checked against one policy table of tools, call limits and allowed values. A tool that is not listed is refused, and that includes the tools that arrive over MCP.
- **No tool books, pays or sends.**
- **Web text is data.** Search results, Google Places records and typed text that read like an instruction to the agent are withheld before a model sees them.
- **Grounding.** Every sentence about a place needs a source that was read and a quote found in it. A rating is shown only when a source states it for that very place.
- **Unknown stays unknown.** The map can only say "no stairs mapped". Gilmate never promises "no stairs".
- **Audit log.** Every decision is a row in a hash-chained log, and the same rows are the steps the page shows while the agents work.

&nbsp;

**Built with coding agents.** I built it during the hackathon as one person directing several coding agents in parallel. I used firstmate, running in tmux, to coordinate them: each agent worked in its own window on its own task. A shared contract decided which agent owned which files and what data they agreed on. A behaviour only counted when a free check proved it: eighteen offline drills run with no network, no key and no model, plus checks of the page in a real browser at phone and desktop size.

## Challenges we ran into

- **Making an AI honest about what it doesn't know.** A model wants to be helpful, so it will say "short walk, no stairs". The fix was architectural: the model never writes a number. Code computes every distance and stair, and a walk with no steps on the map is "no stairs mapped", not "safe".
- **Our own reviews catching us.** In one saved run, every walk was longer than the 300 m she had asked for. The checks flagged all three instead of hiding them, and that is exactly what they are for.
- **Why our own MCP server.** Google's official Maps MCP server returns a text summary with links. We needed the rating, the opening hours and the step-free entrance as separate fields, and its terms do not allow keeping results. So we wrote a small read-only one, behind the same policy table as every other tool.
- **Thin data.** Hongdae has almost no photos of the places themselves, and most entrances are tagged "access unknown". Gilmate shows that as unknown, not as fine.
- **Coordinating many coding agents at once** without them overwriting each other. A written contract and strict file ownership were what made it work.

## Accomplishments we're proud of

- Agents that plan, a critic that pushes back, and code that has the last word on every fact.
- A real, read-only MCP server for Google Places, under the same deny-by-default policy as everything else.
- A memory she can see as a knowledge graph and delete from.
- It ran end to end with the real model, Google Places and Open-Meteo, with no errors.

## What we learned

- **Trust comes from what a system refuses to do.** No booking, no paying, no guessing.
- **"Unknown" is a feature.** For someone with a bad knee, a wrong "no stairs" is worse than an honest "not mapped".
- **Agents are better at writing than at knowing.** Letting the model write the sentences and code own the facts made every answer checkable.

## What's next

- More cities. Each needs its own map extract and search hints.
- Proofreading the Korean, which today is an unreviewed translation.
- Letting my mom try it. She hasn't yet. She is the first person it has to convince.

## Try it

[Demo](https://agile-hawthorn-6qatqxa.tmp.now/): the Gilmate page with two real saved runs, Shibuya and Hongdae, plus the phone walking page. It replays what the agents produced. The live agents need a Python server and API keys, so they run locally with `scripts/demo.sh`. · [GitHub](https://github.com/bobocs50/gilmate_hack)

So if your parents dream of seeing the world but feel unsure going alone, Gilmate builds the trip around them.

---

## Built with (23 of 25 tags)

python, google-adk, anthropic, claude, model-context-protocol, google-places-api, google-cloud, tavily, openstreetmap, open-meteo, wikimedia-commons, wikidata, wikipedia, mapillary, javascript, html5, css3, vercel, claude-code, multi-agent, knowledge-graph, tmux, firstmate

---

## Links ("Try it out")

- Demo: https://agile-hawthorn-6qatqxa.tmp.now/
- GitHub: https://github.com/bobocs50/gilmate_hack

---

## Image gallery

- `img/architecture.png` (architecture slide, 3840 × 2160)
- A photo of your mom, if she agrees.

---

## MLH description (bold, italic, links, lists, code only)

**Inspiration**

For months, my mom has been asking me one thing: _come to Japan with me._ She studies Japanese every day. I keep saying "soon". I work full-time as an intern, and next year I will be abroad for a semester with a part-time job. Everything gets delayed.

By one estimate (Tim Urban's), by the time we finish school about **93%** of the in-person time we will ever spend with our parents is already behind us. I feel that. And at the same time, my parents finally have the time and the money they worked so hard for to see the world, but every year exploring it gets harder. The walks feel longer, the stairs feel steeper.

Most trip planners know the city and nothing about the person walking it. They will happily send someone with a bad knee up three flights of stairs, and say it is "a short walk". I wanted the opposite: **a tour guide that plans around the person, not the city**, and that says "I don't know" instead of guessing.

**What it does**

Gilmate is a multi-agent tour guide. Today it knows two areas: **Shibuya in Tokyo** and **Hongdae in Seoul**.

1. **Say where you want to go, in your own words.** For example: _"My mom wants to visit Shibuya. She loves sushi. Stairs are hard for her, and she can walk about 1 km before she needs to sit down."_
2. **Watch the map being made.** Agents search the web and Google Places for sights, shops and restaurants, and put real places on a map with real photos.
3. **Choose.** One place at a time: Yes or No.
4. **Get one route you can actually walk.** Every walk with its distance, the stairs on the way, the benches where you can sit, street photos of the way, and today's weather.
5. **Take it with you.** A QR code opens the route on a phone, stop by stop. After each walk: _Fine_ or _Too far_.
6. **See what it remembers.** A knowledge graph shows everything Gilmate knows about you, where each fact came from, and lets you delete any of it.

**How we built it**

Gilmate runs on **Google's Agent Development Kit (ADK)**, with **Claude Sonnet** as the model. One **coordinator** reads each step and hands the work to four specialists:

- **Scout:** finds places: sights, shops and restaurants. Searches the web with Tavily, and **Google Places through an MCP server we built**.
- **Router:** puts her stops in order and checks today's weather.
- **Critic:** reviews the route before she sees it, and sends it back to the router if something is wrong (at most twice).
- **Companion:** answers her questions on the way, only from the facts of her route.

**Google Places over MCP.** We wrote a small MCP server (`places_server.py`) that wraps the Places API (New) and only reads. The scout gets it through ADK's `McpToolset`. It returns what matters for her: the rating and how many people rated it, the opening hours, and whether the entrance is step-free. A Google record is attached to a place only when the names agree and the two points are at most 80 m apart. The map stays the truth.

**The spatial model.** The heart of Gilmate is plain Python, not the model. For every walk between two stops, code follows the real paths from **OpenStreetMap**, measures the distance, finds the steps and the benches, and collects street photos from **Mapillary** and photos of the places from **Wikimedia Commons**, each with its author and licence.

**Weather.** **Open-Meteo** gives the forecast, and Python turns it into a fixed list of dangers: rain, heat, wind, cold, darkness and more. No model judges the weather. If rain or great heat is likely, her walking limit for that route drops by a quarter (a 1,000 m limit becomes 750 m), and any walk that would end after sunset is flagged.

**Memory as a knowledge graph.** Every choice she makes is stored: her picks, what she can manage, and the walks that were too far. One _Too far_ tap sets her limit for that day to 10 m less than that walk. A second tap keeps it for the next route. A learned limit can only make routes shorter, never longer than what she said herself. Only Python writes the memory, never web text or model text.

**Security.** One rule runs through everything: _the model writes the sentences, code owns every fact._

- **Deny by default.** Every tool call is checked against one policy table of tools, call limits and allowed values. A tool that is not listed is refused, and that includes the tools that arrive over MCP.
- **No tool books, pays or sends.**
- **Web text is data.** Search results, Google Places records and typed text that read like an instruction to the agent are withheld before a model sees them.
- **Grounding.** Every sentence about a place needs a source that was read and a quote found in it. A rating is shown only when a source states it for that very place.
- **Unknown stays unknown.** The map can only say "no stairs mapped". Gilmate never promises "no stairs".
- **Audit log.** Every decision is a row in a hash-chained log, and the same rows are the steps the page shows while the agents work.

**Built with coding agents.** I built it during the hackathon as one person directing several coding agents in parallel. I used firstmate, running in tmux, to coordinate them: each agent worked in its own window on its own task. A shared contract decided which agent owned which files and what data they agreed on. A behaviour only counted when a free check proved it: eighteen offline drills run with no network, no key and no model, plus checks of the page in a real browser at phone and desktop size.

**Challenges we ran into**

- **Making an AI honest about what it doesn't know.** A model wants to be helpful, so it will say "short walk, no stairs". The fix was architectural: the model never writes a number. Code computes every distance and stair, and a walk with no steps on the map is "no stairs mapped", not "safe".
- **Our own reviews catching us.** In one saved run, every walk was longer than the 300 m she had asked for. The checks flagged all three instead of hiding them, and that is exactly what they are for.
- **Why our own MCP server.** Google's official Maps MCP server returns a text summary with links. We needed the rating, the opening hours and the step-free entrance as separate fields, and its terms do not allow keeping results. So we wrote a small read-only one, behind the same policy table as every other tool.
- **Thin data.** Hongdae has almost no photos of the places themselves, and most entrances are tagged "access unknown". Gilmate shows that as unknown, not as fine.
- **Coordinating many coding agents at once** without them overwriting each other. A written contract and strict file ownership were what made it work.

**Accomplishments we're proud of**

- Agents that plan, a critic that pushes back, and code that has the last word on every fact.
- A real, read-only MCP server for Google Places, under the same deny-by-default policy as everything else.
- A memory she can see as a knowledge graph and delete from.
- It ran end to end with the real model, Google Places and Open-Meteo, with no errors.

**What we learned**

- **Trust comes from what a system refuses to do.** No booking, no paying, no guessing.
- **"Unknown" is a feature.** For someone with a bad knee, a wrong "no stairs" is worse than an honest "not mapped".
- **Agents are better at writing than at knowing.** Letting the model write the sentences and code own the facts made every answer checkable.

**What's next**

- More cities. Each needs its own map extract and search hints.
- Proofreading the Korean, which today is an unreviewed translation.
- Letting my mom try it. She hasn't yet. She is the first person it has to convince.

**Try it**

[Demo](https://agile-hawthorn-6qatqxa.tmp.now/): the Gilmate page with two real saved runs, Shibuya and Hongdae, plus the phone walking page. It replays what the agents produced. The live agents need a Python server and API keys, so they run locally with `scripts/demo.sh`. · [GitHub](https://github.com/bobocs50/gilmate_hack)

So if your parents dream of seeing the world but feel unsure going alone, Gilmate builds the trip around them.

---

## Before you press submit

- [ ] Vercel dashboard: the deployment shows no expiry time (it was created to end around 14:57).
- [ ] Open the demo link on your phone once.
- [ ] Remove `google-cloud` from the tags if the Places key was not set up through Google Cloud.
