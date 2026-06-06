# instar-skill-personality

Personality traits skill for [Project Instar](https://github.com/thegman54/project-instar). Provides structured, categorized personality traits with weights, decay, and an admin panel for management.

## What It Does

Stores personality traits (short categorical entries) that shape HOW the bot communicates — tone, phrasing, boundaries, identity. Traits are grouped into categories, weighted, and optionally time-decaying.

## Install

Zip and upload via the Instar admin UI, or copy into `tool-executor/src/tools/personality/`.

```bash
zip -r instar-skill-personality.zip . -x '.git/*' 'README.md'
# Upload via POST /skills/upload or the admin Skills page
```

## Usage

1. Set a profile's **Personality** field to `skill:personality`
2. Open the **Traits** admin panel on the profile card
3. Add traits by category with optional tags, weights, and stability flags
4. Launch the profile — traits are queried at runtime and injected into conversation context

## Categories

| Category | Purpose |
|----------|---------|
| identity | Who the bot is — name, role, origin |
| tone | How it speaks — formal, casual, dry wit |
| stance | Positions and preferences |
| boundary | What it won't do |
| phrase | Signature phrases and speech patterns |
| situational | Context-dependent behaviors |

## Trait Properties

- **weight** (0.0-1.0) — higher weight = more influence
- **stable** — if true, never decays; if false, effective weight decreases over time
- **tags** — keywords for situational retrieval

## License

MIT
