<div align="center">

<img src="docs/gilmate-icon.svg" width="120" alt="Gilmate">

# Gilmate | 4th Place | DevFest Münster 2026 Agentic AI Hackathon

**A tour guide that plans around you, not the city.**

Built in three hours by one person directing AI coding agents.

<br/>

![DevFest Münster 2026](https://img.shields.io/badge/DevFest_M%C3%BCnster-2026-172548?style=for-the-badge)
![4th Place](https://img.shields.io/badge/4th_Place-Agentic_AI_Hackathon-b9472a?style=for-the-badge)
![Built in 3 hours](https://img.shields.io/badge/Built_in-3_hours-172548?style=for-the-badge)

<br/>

![Google ADK](https://img.shields.io/badge/Google_ADK-4285F4?style=flat-square&logo=google&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?style=flat-square&logo=anthropic&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-000000?style=flat-square)
![Google Places](https://img.shields.io/badge/Google_Places-34A853?style=flat-square&logo=googlemaps&logoColor=white)
![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-7EBC6F?style=flat-square&logo=openstreetmap&logoColor=white)
![Open-Meteo](https://img.shields.io/badge/Open--Meteo-FF8800?style=flat-square)
![Tavily](https://img.shields.io/badge/Tavily-1A1A1A?style=flat-square)
![Mapillary](https://img.shields.io/badge/Mapillary-05CB63?style=flat-square&logo=mapillary&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

</div>

---

<p align="center">
  <img src="docs/screenshots/landing.png" width="100%" alt="Gilmate: type where you want to go">
</p>

| Choose places on the map | Food is asked once |
|---|---|
| <img src="docs/screenshots/choose.png" alt="A place with its photo, what it is, and Yes or No"> | <img src="docs/screenshots/food.png" alt="Where would you like to eat?"> |

| The route, with the real photo of every bench and stop |
|---|
| <img src="docs/screenshots/route.png" alt="The final map with a bench's street photo"> |


Gilmate is a tour guide for people who find walking hard, and for those who plan for them.
It asks what you can manage, then builds one walk for the places you chose.
Every distance, stair, bench and warning comes from map data; what the map does not know is "unknown", never safe.

## What you do

1. **Type** where you want to go and how you walk.
2. **Watch** the agents make the map.
3. **Choose** two to five places, Yes or No.
4. **Tell** the guide what you can manage.
5. **Read** the route, its walks and its warnings.
6. **Take** it to your phone with a QR code.
7. **See** what it remembers, and forget any of it.

## How it works

<img src="img/architecture.png" width="100%" alt="How Gilmate works">

```mermaid
flowchart TD
  page["The page: plain HTML, CSS and JavaScript"]
  subgraph server["ADK agent server"]
    coordinator["coordinator"]
    scout["scout: makes the map"]
    router["router: drafts the walk"]
    critic["critic: reviews the draft"]
    companion["companion: answers about a stop"]
    coordinator --> scout
    coordinator --> router
    coordinator --> critic
    coordinator --> companion
  end
  state[("Session state and memory")]
  guards["Guards: tool policy, screening, grounding, audit log"]
  tools["Tools: plain Python owns every fact"]
  subgraph sources["Sources"]
    tavily["Tavily"]
    places["Google Places through MCP"]
    meteo["Open-Meteo"]
    osm["OpenStreetMap"]
    photos["Wikimedia Commons and Mapillary"]
    wiki["Wikidata and Wikipedia"]
  end
  page -->|"one JSON message per turn"| coordinator
  scout --> guards
  router --> guards
  critic --> guards
  companion --> guards
  guards --> tools
  tools --> tavily
  tools --> places
  tools --> meteo
  tools --> osm
  tools --> photos
  tools --> wiki
  tools --> state
  state -->|"read back and drawn"| page
```

## Agents

| Agent | Job |
| --- | --- |
| coordinator | Reads each turn and delegates |
| scout | Makes the map, a source for every fact |
| router | Orders your picks into one walk |
| critic | Reviews the draft, cannot change it |
| companion | Answers one question about a stop |

## Why you can trust it

- **Policy:** deny by default; one table of tools, limits and arguments.
- **Screening:** outside text is data, never an instruction.
- **Grounding:** a source and a quote for every fact.
- **Audit:** every decision is a row in a hash-chained log.
- **No actions:** no tool books, pays or sends. [SECURITY.md](SECURITY.md)

## Sources

Tavily, Google Places through our own MCP server, Open-Meteo, OpenStreetMap, Mapillary.

## Run it

```sh
uv venv --python 3.13 && source .venv/bin/activate && uv pip install -r requirements.txt
scripts/demo.sh --saved   # saved run: no key, no model, no search
scripts/demo.sh           # live agents; using the page costs money
```

Keys in `.env`: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`; optional `GOOGLE_API_KEY`, `MAPILLARY_TOKEN`.

## Checked

- Eighteen free drills (`scripts/drills.sh`): no network, no key, no model; all pass.
- A full live run through the page with the real model, 13:02 to 13:07 on 21 Nov 2026.
- Not tested: Hongdae against the live agents; nothing measured on site. [Details](docs/ARCHITECTURE.md#what-was-checked)

## Limits

- Two areas only: Shibuya in Tokyo and Hongdae in Seoul.
- "No stairs mapped" means the map shows none, not that none exist.
- Hongdae's data is thin: no place photos, most entrances unknown.
- The page has no field for the companion's questions yet. [All limits](docs/ARCHITECTURE.md#limits)

## Built with

Google ADK with Claude as the model; Gemini is not used. Map drawing and styling ported from Mercature by Glendon Chin (MIT), see [THIRD_PARTY.md](THIRD_PARTY.md). Photo credits: [CREDITS.md](CREDITS.md).
