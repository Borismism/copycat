# Shared Configuration System

This directory contains the universal configuration system that makes Copycat flexible to monitor **ANY intellectual property from ANY company**.

## Quick Start

### For Service Developers

```python
# In any service (discovery, risk-analyzer, vision-analyzer, etc.)
from shared.config_loader import load_config

# Load config
config = load_config()

# Get all characters to monitor
characters = config.get_all_characters()
# Returns: ["Superman", "Batman", "Wonder Woman", ...]

# Get client name
client = config.client_name
# Returns: "Warner Bros. Entertainment"

# Get characters by priority
high_priority = config.get_characters_by_priority("high")
# Returns: ["Superman", "Batman", "Joker", ...]

# Get IP details
justice_league = config.get_ip_by_id("dc-justice-league")
# Returns: {id, name, owner, characters, ...}
```

### For System Administrators

To monitor different IPs (e.g., switch from DC Comics to Marvel):

1. **Edit `shared_config.yaml`**:

```yaml
client:
  name: "The Walt Disney Company"
  abbreviation: "Disney"

intellectual_properties:
  - id: "marvel-avengers"
    name: "The Avengers"
    owner: "Marvel Entertainment / Disney"
    characters:
      - "Iron Man"
      - "Captain America"
      - "Thor"
      - "Hulk"
```

2. **Restart services** - they automatically load the new config!

## File Structure

```
/copycat/
├── shared_config.yaml          # Main configuration file (EDIT THIS)
└── shared/
    ├── __init__.py
    ├── config_loader.py        # Python loader (USE THIS in services)
    └── README.md               # This file
```

## Configuration Schema

### Client Section

```yaml
client:
  name: "Company Name"
  abbreviation: "ABBR"
  industry: "Industry Type"
  description: "What we're monitoring"
```

### Intellectual Properties

```yaml
intellectual_properties:
  - id: "unique-id"              # Used in code to reference this IP
    name: "Display Name"         # Shown in UI
    owner: "Copyright Holder"    # Legal owner
    type: "character_franchise"  # or character_group
    value_tier: "AAA"            # AAA, AA, A, B, C (affects risk scoring)
    characters:
      - "Character 1"
      - "Character 2"
    legal_notice: "Copyright notice text"
    monitoring_priority: "high"  # high, medium, low
```

### AI Tools

```yaml
ai_tools:
  - name: "Tool Name"
    company: "Company"
    detection_keywords: ["keyword1", "keyword2"]
    priority: "high"  # high, medium, low
```

## How Services Use This

### Discovery Service

```python
from shared.config_loader import load_config

config = load_config()

# Automatically generate search keywords from config
for ip in config.intellectual_properties:
    keywords = config.generate_search_keywords(ip["id"])
    # Searches for "[character] ai|sora|runway|kling"
```

### Vision Analyzer

```python
from shared.config_loader import load_config

config = load_config()

# Build prompt with characters from config
characters = config.get_all_characters(priority="high")
prompt = f"Analyze for these characters: {', '.join(characters)}"

# Get copyright owner
owner = config.get_copyright_owner("Superman")
# Returns: "DC Comics / Warner Bros. Entertainment"
```

### Risk Analyzer

```python
from shared.config_loader import load_config

config = load_config()

# Adjust risk score based on IP value
ip_id = "dc-justice-league"
multiplier = config.get_value_tier_multiplier(ip_id)
# Returns: 2.0 (for AAA tier)

risk_score = base_score * multiplier
```

### Frontend

```typescript
// Fetch config from API
const config = await fetch('/api/config');

// Display client name
<h1>{config.client.name} - Copyright Monitoring</h1>

// Show IPs
config.intellectual_properties.map(ip => (
  <Card key={ip.id}>
    <h2>{ip.name}</h2>
    <p>Owner: {ip.owner}</p>
    <p>Characters: {ip.characters.join(', ')}</p>
  </Card>
))
```

## Example: Switching to Marvel

**Current** (DC Comics / Warner Bros):
```yaml
client:
  name: "Warner Bros. Entertainment"

intellectual_properties:
  - id: "dc-justice-league"
    characters: ["Superman", "Batman", ...]
```

**New** (Marvel / Disney):
```yaml
client:
  name: "The Walt Disney Company"

intellectual_properties:
  - id: "marvel-avengers"
    characters: ["Iron Man", "Captain America", "Thor", ...]

  - id: "marvel-x-men"
    characters: ["Wolverine", "Storm", "Cyclops", ...]

  - id: "marvel-spider-verse"
    characters: ["Spider-Man", "Miles Morales", "Gwen Stacy", ...]
```

**That's it!** All services automatically use the new IPs.

## Benefits

1. **No Code Changes**: Switch IPs by editing one YAML file
2. **Consistency**: All services use the same character lists
3. **Flexibility**: Support multiple clients/IPs simultaneously
4. **Maintainability**: Update character lists in one place
5. **Extensibility**: Easy to add new IPs or AI tools

## API Endpoint

For frontend/external access:

```
GET /api/config
```

Returns the full configuration as JSON.

## Environment Variables

Optional overrides:

```bash
COPYCAT_CONFIG_PATH=/path/to/custom_config.yaml
```

## Testing

```python
# Test the config loader
python3 -c "
from shared.config_loader import load_config

config = load_config()
print(f'Client: {config.client_name}')
print(f'IPs: {len(config.intellectual_properties)}')
print(f'Characters: {len(config.get_all_characters())}')
"
```

## Migration Guide

To migrate existing hardcoded references:

### Before (Hardcoded):
```python
JUSTICE_LEAGUE_CHARACTERS = [
    "Superman", "Batman", "Wonder Woman", ...
]
```

### After (Config-driven):
```python
from shared.config_loader import load_config

config = load_config()
characters = config.get_all_characters()
```

## Support

For questions or issues with configuration, see:
- Main documentation: `/copycat/CLAUDE.md`
- Config examples: `/copycat/shared_config.yaml`
