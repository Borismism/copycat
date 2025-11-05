# Configuration Editor - Implementation Status & Completion Guide

## ✅ Completed Implementation (Backend)

### 1. Backend API Endpoints - DONE

**File:** `services/api-service/app/routers/config.py`

Added the following endpoints:

```
GET  /api/config/list                          # Lists all IP configs with all fields
PATCH /api/config/{config_id}/characters       # Update characters
PATCH /api/config/{config_id}/keywords         # Update search keywords
PATCH /api/config/{config_id}/ai-patterns      # Update AI tool patterns
PATCH /api/config/{config_id}/visual-keywords  # Update visual keywords
PATCH /api/config/{config_id}/video-titles     # Update common video titles
PATCH /api/config/{config_id}/false-positive-filters  # Update false positive filters
```

All endpoints:
- Accept `{"values": ["item1", "item2", ...]}` as request body
- Update the field in Firestore
- Return `{"success": true, "count": N}`

### 2. Gemini Suggestion Endpoints - DONE

**File:** `services/api-service/app/routers/config_ai_assistant.py`

Added 5 new suggestion endpoints:

```
POST /api/config/ai/suggest-keywords                # Suggest search keywords
POST /api/config/ai/suggest-ai-patterns             # Suggest AI tool patterns
POST /api/config/ai/suggest-visual-keywords         # Suggest visual keywords
POST /api/config/ai/suggest-video-titles            # Suggest common video titles
POST /api/config/ai/suggest-false-positive-filters  # Suggest false positive filters
```

All endpoints:
- Accept `{"ip_name": "...", "existing_items": [...]}` as request
- Call Gemini 2.5 Flash to generate 5-10 NEW suggestions
- Return `{"suggestions": ["new1", "new2", ...]}`
- Temperature: 0.8 (creative)
- Max output tokens: 4,096

### 3. API Service Restarted - DONE

The API service has been restarted and all new endpoints are live.

---

## ✅ Completed Implementation (Frontend)

### 1. Reusable Component - DONE

**File:** `services/frontend-service/app/web/src/components/EditableTagsSection.tsx`

Created a fully-featured editable section component with:
- Display mode (click "Edit" to enable editing)
- Edit mode with:
  - Remove buttons (X) on hover
  - "Suggest More with Gemini" button
  - Save/Cancel buttons
- Loading states for suggestions and saving
- Error handling with revert-on-error
- Toast-friendly callbacks

**Props:**
```typescript
{
  title: string;                          // Section title
  items: string[];                        // Current items
  onUpdate: (items) => Promise<void>;     // Save handler
  onSuggestMore: () => Promise<string[]>; // Gemini suggestion handler
  isEditing: boolean;                     // Edit state
  onToggleEdit: () => void;               // Toggle edit mode
}
```

---

## 🚧 Remaining Work (Frontend Integration)

### What Needs to Be Done

You need to update `ConfigGeneratorPage.tsx` to integrate the EditableTagsSection component for all 5 sections in the **Detail View**.

### Step-by-Step Instructions

#### 1. Add Imports

At the top of `ConfigGeneratorPage.tsx`, add:

```tsx
import EditableTagsSection from '../components/EditableTagsSection';
```

#### 2. Add State Management

Inside the `ConfigGeneratorPage` component, add state for each section:

```tsx
// Section editing states
const [editingKeywords, setEditingKeywords] = useState(false);
const [editingAIPatterns, setEditingAIPatterns] = useState(false);
const [editingVisualKeywords, setEditingVisualKeywords] = useState(false);
const [editingVideoTitles, setEditingVideoTitles] = useState(false);
const [editingFalsePositives, setEditingFalsePositives] = useState(false);

// Section data (load from Firestore)
const [keywords, setKeywords] = useState<string[]>([]);
const [aiPatterns, setAIPatterns] = useState<string[]>([]);
const [visualKeywords, setVisualKeywords] = useState<string[]>([]);
const [videoTitles, setVideoTitles] = useState<string[]>([]);
const [falsePositives, setFalsePositives] = useState<string[]>([]);
```

#### 3. Load Data from Firestore

Update `loadConfigs()` to also load section data when a config is selected:

```tsx
const loadConfigData = async (configId: string) => {
  try {
    const response = await fetch(`http://localhost:8080/api/config/list`);
    const data = await response.json();

    const config = data.configs.find(c => c.id === configId);
    if (config) {
      setKeywords(config.search_keywords || []);
      setAIPatterns(config.ai_tool_patterns || []);
      setVisualKeywords(config.visual_keywords || []);
      setVideoTitles(config.common_video_titles || []);
      setFalsePositives(config.false_positive_filters || []);
    }
  } catch (error) {
    console.error('Failed to load config data:', error);
  }
};

// Call this when entering detail view
useEffect(() => {
  if (view === 'detail' && selectedConfig) {
    loadConfigData(selectedConfig.id);
  }
}, [view, selectedConfig]);
```

#### 4. Create Handler Functions

Add handlers for updating and suggesting for each section:

```tsx
// Keywords
const updateKeywords = async (newKeywords: string[]) => {
  const response = await fetch(`http://localhost:8080/api/config/${selectedConfig!.id}/keywords`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values: newKeywords })
  });
  if (!response.ok) throw new Error('Failed to update keywords');
  setKeywords(newKeywords);
  showToast('Keywords updated successfully!');
};

const suggestKeywords = async (): Promise<string[]> => {
  const response = await fetch('http://localhost:8080/api/config/ai/suggest-keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ip_name: selectedConfig!.name,
      existing_items: keywords
    })
  });
  if (!response.ok) throw new Error('Failed to get suggestions');
  const data = await response.json();
  return data.suggestions;
};

// AI Patterns
const updateAIPatterns = async (newPatterns: string[]) => {
  const response = await fetch(`http://localhost:8080/api/config/${selectedConfig!.id}/ai-patterns`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values: newPatterns })
  });
  if (!response.ok) throw new Error('Failed to update AI patterns');
  setAIPatterns(newPatterns);
  showToast('AI patterns updated successfully!');
};

const suggestAIPatterns = async (): Promise<string[]> => {
  const response = await fetch('http://localhost:8080/api/config/ai/suggest-ai-patterns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ip_name: selectedConfig!.name,
      existing_items: aiPatterns
    })
  });
  if (!response.ok) throw new Error('Failed to get suggestions');
  const data = await response.json();
  return data.suggestions;
};

// Visual Keywords
const updateVisualKeywords = async (newKeywords: string[]) => {
  const response = await fetch(`http://localhost:8080/api/config/${selectedConfig!.id}/visual-keywords`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values: newKeywords })
  });
  if (!response.ok) throw new Error('Failed to update visual keywords');
  setVisualKeywords(newKeywords);
  showToast('Visual keywords updated successfully!');
};

const suggestVisualKeywords = async (): Promise<string[]> => {
  const response = await fetch('http://localhost:8080/api/config/ai/suggest-visual-keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ip_name: selectedConfig!.name,
      existing_items: visualKeywords
    })
  });
  if (!response.ok) throw new Error('Failed to get suggestions');
  const data = await response.json();
  return data.suggestions;
};

// Video Titles
const updateVideoTitles = async (newTitles: string[]) => {
  const response = await fetch(`http://localhost:8080/api/config/${selectedConfig!.id}/video-titles`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values: newTitles })
  });
  if (!response.ok) throw new Error('Failed to update video titles');
  setVideoTitles(newTitles);
  showToast('Video titles updated successfully!');
};

const suggestVideoTitles = async (): Promise<string[]> => {
  const response = await fetch('http://localhost:8080/api/config/ai/suggest-video-titles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ip_name: selectedConfig!.name,
      existing_items: videoTitles
    })
  });
  if (!response.ok) throw new Error('Failed to get suggestions');
  const data = await response.json();
  return data.suggestions;
};

// False Positive Filters
const updateFalsePositives = async (newFilters: string[]) => {
  const response = await fetch(`http://localhost:8080/api/config/${selectedConfig!.id}/false-positive-filters`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values: newFilters })
  });
  if (!response.ok) throw new Error('Failed to update false positive filters');
  setFalsePositives(newFilters);
  showToast('False positive filters updated successfully!');
};

const suggestFalsePositives = async (): Promise<string[]> => {
  const response = await fetch('http://localhost:8080/api/config/ai/suggest-false-positive-filters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ip_name: selectedConfig!.name,
      existing_items: falsePositives
    })
  });
  if (!response.ok) throw new Error('Failed to get suggestions');
  const data = await response.json();
  return data.suggestions;
};
```

#### 5. Replace Hardcoded Sections in Detail View

Find the sections in the detail view (lines 488-564) and replace them with EditableTagsSection:

**Replace Search Keywords section (lines 488-501):**
```tsx
{/* Search Keywords */}
<div className="bg-white shadow rounded-lg p-6">
  <EditableTagsSection
    title="Search Keywords"
    items={keywords}
    onUpdate={updateKeywords}
    onSuggestMore={suggestKeywords}
    isEditing={editingKeywords}
    onToggleEdit={() => setEditingKeywords(!editingKeywords)}
  />
  <p className="text-xs text-gray-500 mt-2">
    YouTube search queries optimized for AI-generated content
  </p>
</div>
```

**Replace AI Tool Patterns section (lines 503-516):**
```tsx
{/* AI Tool Patterns */}
<div className="bg-white shadow rounded-lg p-6">
  <EditableTagsSection
    title="AI Tool Patterns"
    items={aiPatterns}
    onUpdate={updateAIPatterns}
    onSuggestMore={suggestAIPatterns}
    isEditing={editingAIPatterns}
    onToggleEdit={() => setEditingAIPatterns(!editingAIPatterns)}
  />
  <p className="text-xs text-gray-500 mt-2">
    Specific combinations of IP + AI tools to detect
  </p>
</div>
```

**Replace Visual Detection Markers section (lines 518-531):**
```tsx
{/* Visual Detection Markers */}
<div className="bg-white shadow rounded-lg p-6">
  <EditableTagsSection
    title="Visual Detection Markers"
    items={visualKeywords}
    onUpdate={updateVisualKeywords}
    onSuggestMore={suggestVisualKeywords}
    isEditing={editingVisualKeywords}
    onToggleEdit={() => setEditingVisualKeywords(!editingVisualKeywords)}
  />
  <p className="text-xs text-gray-500 mt-2">
    Key visual elements for vision analysis
  </p>
</div>
```

**Replace Common Video Titles section (lines 533-549):**
```tsx
{/* Common Video Titles */}
<div className="bg-white shadow rounded-lg p-6">
  <EditableTagsSection
    title="Common Video Title Patterns"
    items={videoTitles}
    onUpdate={updateVideoTitles}
    onSuggestMore={suggestVideoTitles}
    isEditing={editingVideoTitles}
    onToggleEdit={() => setEditingVideoTitles(!editingVideoTitles)}
  />
  <p className="text-xs text-gray-500 mt-2">
    Common title patterns to search for on YouTube
  </p>
</div>
```

**Replace False Positive Filters section (lines 551-564):**
```tsx
{/* False Positive Filters */}
<div className="bg-white shadow rounded-lg p-6">
  <EditableTagsSection
    title="False Positive Filters"
    items={falsePositives}
    onUpdate={updateFalsePositives}
    onSuggestMore={suggestFalsePositives}
    isEditing={editingFalsePositives}
    onToggleEdit={() => setEditingFalsePositives(!editingFalsePositives)}
  />
  <p className="text-xs text-gray-500 mt-2">
    Keywords that indicate non-infringing content
  </p>
</div>
```

---

## 🧪 Testing Checklist

Once implemented, test each section:

### For Each Section:

1. **Display Mode:**
   - [ ] Section shows existing items from Firestore
   - [ ] Items display correctly in tags/badges
   - [ ] "Edit" button is visible

2. **Edit Mode:**
   - [ ] Click "Edit" → UI switches to edit mode
   - [ ] Existing items show with X buttons on hover
   - [ ] Click X → Item is removed from local state
   - [ ] Click "Cancel" → Changes are discarded

3. **Gemini Suggestions:**
   - [ ] Click "Suggest More with Gemini" → Shows loading spinner
   - [ ] Suggestions appear as new items
   - [ ] Suggestions don't duplicate existing items
   - [ ] Click X on suggestion → Removes it before saving

4. **Save Functionality:**
   - [ ] Click "Save" → Shows loading spinner
   - [ ] Success toast appears
   - [ ] Changes persist in Firestore
   - [ ] Refresh page → Changes are still there

5. **Error Handling:**
   - [ ] If save fails → Shows error
   - [ ] If save fails → Local state reverts to original
   - [ ] If Gemini fails → Shows error message

### Full Integration Test:

1. Navigate to Configuration Manager
2. Click on an existing IP config
3. Edit all 5 sections:
   - Remove some items
   - Add Gemini suggestions to each
   - Save each section
4. Refresh the page
5. Verify all changes persisted
6. Check Firestore emulator to confirm data

---

## 📋 Current File Structure

```
services/
├── api-service/app/routers/
│   ├── config.py                    # ✅ Updated with list + update endpoints
│   └── config_ai_assistant.py       # ✅ Updated with suggestion endpoints
│
└── frontend-service/app/web/src/
    ├── components/
    │   └── EditableTagsSection.tsx  # ✅ Created (reusable component)
    └── pages/
        └── ConfigGeneratorPage.tsx  # 🚧 Needs integration (follow guide above)
```

---

## 🎯 Summary

**✅ Backend: 100% Complete**
- 6 update endpoints (1 per field)
- 5 Gemini suggestion endpoints
- All tested and working

**✅ Frontend Component: 100% Complete**
- Reusable EditableTagsSection component
- Full edit/remove/suggest/save functionality

**🚧 Frontend Integration: Needs completion**
- Add state management for 5 sections
- Add handler functions (update + suggest for each)
- Replace hardcoded sections with EditableTagsSection
- Test end-to-end

**Estimated Time to Complete:** 30-45 minutes

**Lines of Code to Add:** ~200 lines in ConfigGeneratorPage.tsx

All backend infrastructure is ready. The frontend just needs to wire up the existing component!
