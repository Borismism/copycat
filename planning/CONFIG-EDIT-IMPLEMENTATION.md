# Configuration Manager - Full Edit Implementation Plan

## Current Status ✅
- Characters section: Fully editable with add/remove/Gemini validation
- Vision analyzer: Now loads ALL characters from both Firestore + shared_config.yaml
- Gemini priority bug: Fixed (respects user's High/Medium/Low selection)
- Gemini max_output_tokens: Increased to 50,000

## What Still Needs Implementation 🚧

### Make These Sections Editable (Same Pattern as Characters):

1. **Search Keywords** (`search_keywords[]`)
2. **AI Tool Patterns** (`ai_tool_patterns[]`)
3. **Visual Keywords** (`visual_keywords[]`)
4. **Common Video Titles** (`common_video_titles[]`)
5. **False Positive Filters** (`false_positive_filters[]`)

---

## Implementation Pattern (Repeat for Each Section)

### Frontend (ConfigGeneratorPage.tsx)

```tsx
// 1. Add state
const [editingKeywords, setEditingKeywords] = useState(false);
const [keywords, setKeywords] = useState<string[]>([]);
const [newKeyword, setNewKeyword] = useState("");
const [loadingKeywordSuggestion, setLoadingKeywordSuggestion] = useState(false);

// 2. Load from Firestore
useEffect(() => {
  if (config?.id) {
    const docRef = firestore.collection('ip_targets').doc(config.id);
    docRef.get().then(doc => {
      const data = doc.data();
      setKeywords(data?.search_keywords || []);
    });
  }
}, [config?.id]);

// 3. Add Gemini "Suggest More" button
const handleSuggestKeywords = async () => {
  setLoadingKeywordSuggestion(true);
  const response = await fetch('/api/config/suggest-keywords', {
    method: 'POST',
    body: JSON.stringify({
      config_id: config.id,
      ip_name: config.name,
      existing_keywords: keywords,
    })
  });
  const data = await response.json();
  setKeywords([...keywords, ...data.suggestions]);
};

// 4. Remove item
const removeKeyword = (index: number) => {
  setKeywords(keywords.filter((_, i) => i !== index));
};

// 5. Save to Firestore
const saveKeywords = async () => {
  const docRef = firestore.collection('ip_targets').doc(config.id);
  await docRef.update({ search_keywords: keywords });
  setEditingKeywords(false);
};

// 6. UI with X buttons
{editingKeywords ? (
  <div>
    {keywords.map((kw, i) => (
      <div key={i} className="keyword-item">
        <span>{kw}</span>
        <button onClick={() => removeKeyword(i)}>×</button>
      </div>
    ))}
    <button onClick={handleSuggestKeywords}>🤖 Suggest More Keywords</button>
    <button onClick={saveKeywords}>Save</button>
  </div>
) : (
  <div onClick={() => setEditingKeywords(true)}>
    {keywords.join(', ')}
  </div>
)}
```

---

## Backend API Endpoints Needed

### 1. Update Config List Endpoint
**File:** `services/api-service/app/routers/config.py`

```python
@router.get("/list")
def list_configs():
    configs = db.collection("ip_targets").stream()
    return [{
        "id": doc.id,
        "name": data.get("name"),
        "characters": data.get("characters", []),
        "search_keywords": data.get("search_keywords", []),  # ADD
        "ai_tool_patterns": data.get("ai_tool_patterns", []),  # ADD
        "visual_keywords": data.get("visual_keywords", []),  # ADD
        "common_video_titles": data.get("common_video_titles", []),  # ADD
        "false_positive_filters": data.get("false_positive_filters", []),  # ADD
        # ... other fields
    } for doc, data in [(d, d.to_dict()) for d in configs]]
```

### 2. Create Gemini Suggestion Endpoints

**File:** `services/api-service/app/routers/config_ai_assistant.py`

Add these new endpoints (copy the `/suggest-characters` pattern):

```python
@router.post("/suggest-keywords")
def suggest_keywords(request: SuggestKeywordsRequest):
    prompt = f"""
    Given this IP: {request.ip_name}

    Existing keywords: {request.existing_keywords}

    Suggest 5-10 NEW search keywords for YouTube discovery.
    Focus on: video titles, AI tools, creative descriptions.

    Return JSON: {{"suggestions": ["keyword1", "keyword2", ...]}}
    """
    # Call Gemini, parse JSON
    return {"suggestions": [...]}

@router.post("/suggest-ai-patterns")
def suggest_ai_patterns(request: SuggestAIToolsRequest):
    prompt = f"""
    Given this IP: {request.ip_name}

    Suggest AI tool detection patterns (regex/keywords).
    Examples: "made with sora", "kling ai", "runway gen"

    Return JSON: {{"suggestions": ["pattern1", "pattern2", ...]}}
    """
    # Call Gemini, parse JSON
    return {"suggestions": [...]}

# Repeat for: visual_keywords, video_titles, false_positives
```

### 3. Update Save Endpoint

**File:** `services/api-service/app/routers/config.py`

```python
@router.patch("/{config_id}/keywords")
def update_keywords(config_id: str, request: UpdateKeywordsRequest):
    db.collection("ip_targets").document(config_id).update({
        "search_keywords": request.keywords
    })
    return {"success": True}

# Add similar endpoints for each section
```

---

## Critical Implementation Notes ⚠️

### 1. Data Consistency
- Always load from Firestore, not from state
- Update immediately after Gemini suggestions
- Don't lose data on page refresh

### 2. Gemini Token Limits
- Each "Suggest More" call costs ~500-1000 tokens
- Set `max_output_tokens: 4096` (not 50k for simple suggestions)
- Cache suggestions to avoid redundant calls

### 3. UX Patterns
- Show loading spinner during Gemini calls
- Disable "Suggest More" if already generating
- Auto-save on remove (don't require explicit save click)
- Confirm before removing (prevent accidents)

### 4. Error Handling
```tsx
try {
  await saveKeywords();
  toast.success("Keywords updated");
} catch (err) {
  toast.error("Failed to save keywords");
  // Revert local state
  setKeywords(originalKeywords);
}
```

### 5. Firestore Security Rules
Ensure users can update these fields:
```javascript
match /ip_targets/{configId} {
  allow update: if request.resource.data.keys().hasOnly([
    'search_keywords',
    'ai_tool_patterns',
    'visual_keywords',
    'common_video_titles',
    'false_positive_filters',
    'characters'
  ]);
}
```

---

## Testing Checklist

- [ ] Load existing config → All sections show correct data
- [ ] Click "Edit" on each section → Shows edit UI
- [ ] Remove item with X → Updates immediately
- [ ] Click "Suggest More" → Gemini adds new items
- [ ] Save changes → Persists to Firestore
- [ ] Refresh page → Data still there
- [ ] Error scenarios → Shows toast, reverts state
- [ ] Multiple configs → Each has independent data

---

## Estimated Effort

- **Per section:** ~50 lines frontend + 30 lines backend = 80 LOC
- **5 sections:** ~400 LOC total
- **Testing:** ~100 LOC
- **Total:** ~500 LOC, 2-3 hours

---

## Priority Order (Implement in This Sequence)

1. **Search Keywords** - Most critical for discovery
2. **AI Tool Patterns** - Key for detection
3. **Visual Keywords** - Important for Gemini prompts
4. **Common Video Titles** - Nice to have
5. **False Positive Filters** - Last (can hardcode initially)

---

## Quick Start Command

```bash
# 1. Update backend
cd services/api-service
# Add endpoints to config_ai_assistant.py

# 2. Update frontend
cd services/frontend-service/app/web
# Update ConfigGeneratorPage.tsx

# 3. Test locally
docker-compose restart api-service frontend-service

# 4. Verify
open http://localhost:5173/config
# Click edit on each section, test add/remove/suggest
```

---

## Files to Modify

**Backend:**
- `services/api-service/app/routers/config.py` - List endpoint
- `services/api-service/app/routers/config_ai_assistant.py` - 5 new suggest endpoints

**Frontend:**
- `services/frontend-service/app/web/src/pages/ConfigGeneratorPage.tsx` - Main UI
- `services/frontend-service/app/web/src/api/config.ts` - API client (optional)

**Total:** 2 backend files, 1-2 frontend files

---

## Current Background Processes Status

You have several background processes running:
- `3d8341` - Discovery run (max_quota=100)
- `373e5d` - Video scan (LonM6llEvIE)
- `a967c4` - Risk analyzer logs
- `3eb872` - Firestore priority check
- `c39d7a` - Videos with scan priority
- `1589b1` - Discovery run (max_quota=1000)

Check their status when ready:
```bash
# Check outputs
./scripts/check-background-tasks.sh

# Or individually
docker-compose logs risk-analyzer-service --tail=20
```
