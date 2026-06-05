# instar-skill-personality

Personality engine for Project Instar. Stores and retrieves structured personality traits that bots query at runtime based on conversation context.

## What It Does

Instead of dumping a text blob into the bot's system prompt, this skill stores personality as **atomic, categorized, weighted traits** that the bot retrieves per-conversation. The bot gets a minimal slice of relevant traits — not the entire personality — keeping token usage low and responses contextually appropriate.

## Categories

| Category | Purpose |
|----------|---------|
| `identity` | Core values and principles (stable) |
| `tone` | Communication style preferences |
| `stance` | Problem-solving approaches |
| `boundary` | Things the bot avoids |
| `phrase` | Vocabulary and expressions |
| `situational` | Context-dependent behaviors |

## Tools

- **`personality_read`** — Returns relevant trait slice for a given situation. Bot calls this once per conversation.
- **`personality_list`** — Lists available categories and trait counts.

## Install

Upload as a skill zip through the Instar admin Tools page, or use Browse GitHub to find and install directly.

## Setup

1. Install the skill (creates `personality_traits` table)
2. Add traits via admin UI or import from `data/example_traits.yaml`
3. Set a profile's personality field to `skill:personality`
4. Launch the profile — bot will call `personality_read` at conversation start

## Trait Structure

Each trait has:
- **category** — one of the 6 categories above
- **content** — the actual trait text (one idea per trait)
- **tags** — context keywords for retrieval (e.g. `["debugging", "technical"]`)
- **weight** — base importance (0.0 - 1.0)
- **stable** — if true, always included regardless of context (never decays)

## Decay

Non-stable traits lose ~5% of effective weight per day since last update. Core identity traits (`stable = true`) never decay. This allows personality to evolve naturally — recent traits matter more, old ones fade unless reinforced.
