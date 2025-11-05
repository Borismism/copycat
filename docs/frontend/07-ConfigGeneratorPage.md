# Config Generator Page

**Route**: `/config`
**File**: `services/frontend-service/app/web/src/pages/ConfigGeneratorPage.tsx`

## Purpose

The Config Generator Page is an **AI-powered IP configuration manager** that helps create and maintain intellectual property monitoring configurations. It uses Claude AI to generate comprehensive configs from minimal input.

## What It Shows

The page has **3 views**:

### View 1: List View (Default)

**Header**:
- Title: "IP Configuration"
- Description: "Manage intellectual property monitoring configurations"
- "Add New IP" button → Generate view

**Stats Cards**:
- **Total IPs**: Count of all configs
- **High Priority**: Count of high-priority configs
- **Total Characters**: Sum of all characters across configs

**Config Grid**:
- 3-column responsive grid
- Each card shows:
  - IP name (e.g., "Justice League")
  - Owner company (e.g., "Warner Bros")
  - Priority badge (low/medium/high)
  - Clickable → Detail view

### View 2: Detail View (Click on config)

Shows full configuration with **6 editable sections**:

1. **Characters** (purple tags)
   - Main characters from the IP
   - Example: Batman, Superman, Wonder Woman

2. **Search Keywords** (blue tags)
   - YouTube search queries optimized for AI content
   - Example: "batman ai generated", "batman sora video"

3. **AI Tool Patterns** (orange tags)
   - Specific IP + AI tool combinations
   - Example: "superman runway ai", "batman kling video"

4. **Visual Detection Markers** (green tags)
   - Key visual elements for Gemini analysis
   - Example: "red cape", "bat symbol", "utility belt"

5. **Common Video Title Patterns** (gray tags)
   - Typical title patterns to search for
   - Example: "AI Superman Movie", "Batman Sora Animation"

6. **False Positive Filters** (yellow tags)
   - Keywords indicating non-infringing content
   - Example: "review", "commentary", "analysis", "parody"

**Each Section Has**:
- Display mode (view tags)
- Edit mode (add/remove/reorder tags)
- "✏️ Edit" / "💾 Save" button
- "✨ AI Suggest" button → AI-powered suggestions

### View 3: Generate View (Click "Add New IP")

**Configuration Manager Form**:
- **IP Name** (required) - e.g., "Harry Potter"
- **Company** (required) - e.g., "Warner Bros"
- **Additional Context** (optional) - Free text for AI guidance
- **Business Priority** - low/medium/high/critical
- "⚡ Generate Configuration" button

**After Generation**:
- Shows generated configuration preview
- All 6 sections are **immediately editable**
- AI reasoning explanation
- "💾 Save Configuration" button → Saves to Firestore & returns to list

## Data Sources

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/config/list` | GET | Load all IP configs |
| `/api/config/ai/generate` | POST | Generate new config with AI |
| `/api/config/ai/save` | POST | Save generated config to Firestore |
| `/api/config/{id}/characters` | PATCH | Update characters section |
| `/api/config/{id}/keywords` | PATCH | Update search keywords |
| `/api/config/{id}/ai-patterns` | PATCH | Update AI tool patterns |
| `/api/config/{id}/visual-keywords` | PATCH | Update visual keywords |
| `/api/config/{id}/video-titles` | PATCH | Update video title patterns |
| `/api/config/{id}/false-positive-filters` | PATCH | Update false positive filters |
| `/api/config/ai/suggest-characters` | POST | Get AI suggestions for characters |
| `/api/config/ai/suggest-keywords` | POST | Get AI suggestions for keywords |
| `/api/config/ai/suggest-ai-patterns` | POST | Get AI suggestions for AI patterns |
| `/api/config/ai/suggest-visual-keywords` | POST | Get AI suggestions for visual keywords |
| `/api/config/ai/suggest-video-titles` | POST | Get AI suggestions for video titles |
| `/api/config/ai/suggest-false-positive-filters` | POST | Get AI suggestions for filters |

**Location**: API calls made directly to `http://localhost:8080/api/config/*`

## Key Features

### 1. AI-Powered Generation

**How it works**:
1. User enters IP name, company, optional context
2. Clicks "Generate Configuration"
3. Backend calls Claude AI with prompt:
   ```
   Generate a comprehensive monitoring config for {IP_NAME} by {COMPANY}.
   Include main characters, search keywords, AI tool patterns, visual markers,
   video title patterns, and false positive filters.
   ```
4. Claude generates full config in seconds
5. Frontend displays editable sections immediately

**Example Input**:
```
IP Name: Spider-Man
Company: Marvel Studios (Disney)
Context: Focus on MCU version, exclude comic book reviews
Priority: High
```

**Example Output**:
- Characters: Peter Parker, Spider-Man, Miles Morales, Gwen Stacy
- Keywords: spider-man ai video, spiderman sora, etc.
- AI Patterns: spider-man runway, spiderman kling ai
- Visual Markers: web shooters, red and blue suit, spider emblem
- Video Titles: AI Spider-Man Movie, Spider-Man Sora Animation
- False Positives: comic review, movie analysis, cosplay tutorial

### 2. Editable Tags Component

**Component**: `EditableTagsSection`
**Location**: `services/frontend-service/app/web/src/components/EditableTagsSection.tsx`

**Features**:
- **Display mode**: Shows tags as colored pills
- **Edit mode**: Inline editing with:
  - Add new tag (input + "Add" button)
  - Remove tag (× button on each tag)
  - Drag to reorder (future enhancement)
- **AI Suggest**: Opens dialog for AI-powered suggestions
  - User provides optional prompt
  - AI generates 5-10 new suggestions
  - User selects which to add
  - Updates immediately

**AI Suggest Workflow**:
1. User clicks "✨ AI Suggest"
2. Optional: Enters custom prompt (e.g., "add female characters")
3. Backend calls Claude AI with context:
   ```
   IP: {IP_NAME}
   Section: Characters
   Existing: [Batman, Superman, ...]
   User request: {USER_PROMPT}
   Generate additional suggestions.
   ```
4. AI returns suggestions
5. User selects which to add
6. Frontend sends PATCH request to update section

### 3. Instant Editing

**Before saving configuration**:
- Edits are stored in local React state
- No API calls made until "Save Configuration"
- Can edit multiple sections before saving

**After saving configuration**:
- Each section edit immediately saves to Firestore
- Toast notification confirms save
- Changes persist across page reloads

### 4. Toast Notifications

Success/error messages shown in top-right corner:
- "✅ Characters updated successfully!"
- "✅ Successfully saved Spider-Man!"
- "❌ Failed to update keywords: [error]"

## How It Works Internally

### State Management

```typescript
// View state
const [view, setView] = useState<'list' | 'detail' | 'generate'>('list')
const [selectedConfig, setSelectedConfig] = useState<IPConfig | null>(null)
const [generatedConfig, setGeneratedConfig] = useState<GeneratedConfig | null>(null)

// Section data
const [characters, setCharacters] = useState<string[]>([])
const [keywords, setKeywords] = useState<string[]>([])
// ... etc for all sections

// Editing states
const [editingCharacters, setEditingCharacters] = useState(false)
const [editingKeywords, setEditingKeywords] = useState(false)
// ... etc for all sections
```

### Data Flow

**Generate new config**:
```
User input → POST /api/config/ai/generate → Claude AI
  ↓
Generated config → Display in UI → Edit sections
  ↓
POST /api/config/ai/save → Firestore → List view
```

**Edit existing config**:
```
Click on config card → Load from Firestore → Display sections
  ↓
Click "Edit" on section → Edit mode → Modify tags
  ↓
Click "Save" → PATCH /api/config/{id}/{section} → Firestore
  ↓
Toast notification → Updated display
```

**AI Suggest**:
```
Click "AI Suggest" → Optional prompt → POST /api/config/ai/suggest-{section}
  ↓
Claude AI generates suggestions → Display in dialog
  ↓
User selects suggestions → Merged with existing → PATCH request
```

## Where to Look

**Change AI generation prompt**:
- Backend: `services/api-service/app/routers/config_ai_assistant.py`
- Look for `generate_config()` function

**Modify editable tags UI**:
```typescript
// EditableTagsSection component
// services/frontend-service/app/web/src/components/EditableTagsSection.tsx
```

**Add new section type**:
1. Add state variables (line 60-66)
2. Add update/suggest functions (line 183-387)
3. Add EditableTagsSection component (line 537-673)
4. Add backend PATCH endpoint

**Change color schemes**:
```typescript
// ConfigGeneratorPage.tsx
// Each EditableTagsSection has a colorScheme prop:
colorScheme={{
  displayBg: 'bg-purple-100',      // Tag background
  displayText: 'text-purple-800',  // Tag text
  editBorder: 'border-purple-300', // Input border
  editBg: 'bg-purple-50',          // Input background
  itemBg: 'bg-purple-100',         // Edit mode tag background
  itemText: 'text-purple-800'      // Edit mode tag text
}}
```

**Customize AI suggestions**:
- Backend: `services/api-service/app/routers/config_ai_assistant.py`
- Each suggest endpoint has its own Claude prompt
- Modify prompts to change suggestion behavior

## Common Issues

**"Failed to generate configuration" error**:
- Check api-service is running on port 8080
- Verify Claude API key is set in environment
- Check `/api/config/ai/generate` endpoint logs
- Ensure Claude API has sufficient credits

**Edits not saving**:
- Check PATCH endpoints are implemented
- Verify Firestore write permissions
- Check for validation errors in backend
- Look for network errors in browser console

**AI suggestions not working**:
- Check Claude API key
- Verify suggest endpoints return 200 OK
- Check prompt formatting in backend
- Ensure IP name is passed correctly

**Tags disappear after edit**:
- Check update function is updating local state
- Verify PATCH request succeeds
- Check response data structure
- Ensure state is not reset unexpectedly

**Config list empty**:
- Check `/api/config/list` endpoint
- Verify configs exist in Firestore
- Check collection name matches backend
- Look for errors in loadConfigs() function (line 79-104)

## Configuration Storage

Configs are stored in Firestore under collection `ip_configs` (or `ip_configs_dev`):

**Document structure**:
```json
{
  "id": "justice-league",
  "name": "Justice League",
  "owner": "Warner Bros",
  "description": "DC Comics superhero franchise",
  "type": "franchise",
  "tier": "1",
  "priority": "high",
  "characters": ["Superman", "Batman", "Wonder Woman", ...],
  "search_keywords": ["justice league ai", "batman sora", ...],
  "ai_tool_patterns": ["superman runway", "batman kling", ...],
  "visual_keywords": ["bat symbol", "red cape", ...],
  "common_video_titles": ["AI Justice League", ...],
  "false_positive_filters": ["review", "commentary", ...],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

## Related Files

- `services/frontend-service/app/web/src/components/EditableTagsSection.tsx` - Editable tags component
- `services/api-service/app/routers/config.py` - Config CRUD endpoints
- `services/api-service/app/routers/config_ai_assistant.py` - AI generation/suggestion endpoints
- `services/api-service/app/routers/config_manager.py` - Config validation logic
