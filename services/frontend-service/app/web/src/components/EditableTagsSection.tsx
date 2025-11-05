import React, { useState } from 'react';

interface ColorScheme {
  displayBg: string;
  displayText: string;
  editBorder: string;
  editBg: string;
  itemBg: string;
  itemText: string;
}

interface EditableTagsSectionProps {
  title: string;
  items: string[];
  onUpdate: (items: string[]) => Promise<void>;
  onSuggestMore: (userPrompt?: string) => Promise<string[]>;
  isEditing: boolean;
  onToggleEdit: () => void;
  colorScheme?: ColorScheme;
}

const EditableTagsSection: React.FC<EditableTagsSectionProps> = ({
  title,
  items,
  onUpdate,
  onSuggestMore,
  isEditing,
  onToggleEdit,
  colorScheme = {
    displayBg: 'bg-blue-100',
    displayText: 'text-blue-800',
    editBorder: 'border-blue-300',
    editBg: 'bg-blue-50',
    itemBg: 'bg-blue-100',
    itemText: 'text-blue-800'
  }
}) => {
  const [localItems, setLocalItems] = useState<string[]>(items);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [saving, setSaving] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [geminiPrompt, setGeminiPrompt] = useState('');

  // Sync local items with prop changes
  React.useEffect(() => {
    setLocalItems(items);
  }, [items]);

  const handleRemove = (index: number) => {
    const newItems = localItems.filter((_, i) => i !== index);
    setLocalItems(newItems);
  };

  const handleAddManual = () => {
    if (!inputValue.trim()) return;

    // Split by comma and add each item
    const newItems = inputValue
      .split(',')
      .map(item => item.trim())
      .filter(item => item && !localItems.includes(item));

    if (newItems.length > 0) {
      setLocalItems([...localItems, ...newItems]);
      setInputValue('');
    }
  };

  const handleSuggestMore = async () => {
    setLoadingSuggestions(true);
    try {
      const suggestions = await onSuggestMore(geminiPrompt.trim() || undefined);
      // Add suggestions that don't already exist
      const newItems = suggestions.filter(s => !localItems.includes(s));
      setLocalItems([...localItems, ...newItems]);
      setGeminiPrompt(''); // Clear the prompt after successful suggestion
    } catch (error) {
      console.error('Failed to get suggestions:', error);
      alert('Failed to get suggestions. Please try again.');
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(localItems);
      onToggleEdit();
    } catch (error) {
      console.error('Failed to save:', error);
      alert('Failed to save changes. Please try again.');
      setLocalItems(items); // Revert on error
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setLocalItems(items); // Revert changes
    onToggleEdit();
  };

  const handleDeleteAll = () => {
    setLocalItems([]);
  };

  if (!isEditing) {
    return (
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-sm font-semibold text-gray-700">{title}</h4>
          <button
            onClick={onToggleEdit}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            Edit
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {localItems.length === 0 ? (
            <span className="text-sm text-gray-400 italic">No items yet</span>
          ) : (
            localItems.map((item, index) => (
              <span
                key={index}
                className={`inline-block ${colorScheme.displayBg} ${colorScheme.displayText} text-xs px-2 py-1 rounded`}
              >
                {item}
              </span>
            ))
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`mb-4 border ${colorScheme.editBorder} rounded-lg p-4 ${colorScheme.editBg}`}>
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-sm font-semibold text-gray-700">{title}</h4>
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            onClick={handleCancel}
            className="px-3 py-1 bg-gray-400 text-white text-xs rounded hover:bg-gray-500"
          >
            Cancel
          </button>
        </div>
      </div>

      <div className="mb-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-600">
            {localItems.length} {localItems.length === 1 ? 'item' : 'items'}
          </span>
          {localItems.length > 0 && (
            <button
              onClick={handleDeleteAll}
              className="text-xs text-red-600 hover:text-red-800 font-medium"
              title="Delete all items"
            >
              🗑️ Delete All
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {localItems.length === 0 ? (
            <span className="text-sm text-gray-400 italic">No items yet</span>
          ) : (
            localItems.map((item, index) => (
              <span
                key={index}
                className={`inline-flex items-center ${colorScheme.itemBg} ${colorScheme.itemText} text-xs px-2 py-1 rounded group`}
              >
                {item}
                <button
                  onClick={() => handleRemove(index)}
                  className="ml-2 text-red-600 hover:text-red-800 font-bold opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Remove"
                >
                  ×
                </button>
              </span>
            ))
          )}
        </div>
      </div>

      {/* Manual Input */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-gray-700 mb-1">
          Add manually (comma-separated):
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddManual();
              }
            }}
            placeholder="e.g., item1, item2, item3"
            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm px-3 py-2 border"
          />
          <button
            onClick={handleAddManual}
            disabled={!inputValue.trim()}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>
      </div>

      {/* Gemini-Aided Input */}
      <div className="mb-3 border-t pt-3">
        <label className="block text-xs font-medium text-gray-700 mb-1">
          🤖 Ask Gemini to help (optional):
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={geminiPrompt}
            onChange={(e) => setGeminiPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !loadingSuggestions) {
                e.preventDefault();
                handleSuggestMore();
              }
            }}
            placeholder="e.g., 'supporting characters' or 'main villains'"
            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 text-sm px-3 py-2 border"
            disabled={loadingSuggestions}
          />
          <button
            onClick={handleSuggestMore}
            disabled={loadingSuggestions}
            className="px-4 py-2 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loadingSuggestions ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Asking...
              </>
            ) : (
              'Ask Gemini'
            )}
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Describe what you want (e.g., "villains from the movies") and Gemini will suggest specific items
        </p>
      </div>
    </div>
  );
};

export default EditableTagsSection;
