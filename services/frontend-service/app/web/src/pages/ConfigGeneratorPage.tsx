import React, { useState, useEffect } from 'react';
import EditableTagsSection from '../components/EditableTagsSection';
import { useAuth } from '../contexts/AuthContext';

interface IPConfig {
  id: string;
  name: string;
  owner: string;
  type: string;
  tier: string;
  characters: string[];
  priority: string;
  high_priority_keywords: string[];
  medium_priority_keywords: string[];
  low_priority_keywords: string[];
  ai_tool_patterns?: string[];
  visual_keywords?: string[];
  false_positive_filters?: string[];
}

interface GeneratedConfig {
  name: string;
  owner: string;
  description: string;
  main_characters: string[];
  high_priority_keywords: string[];
  medium_priority_keywords: string[];
  low_priority_keywords: string[];
  visual_keywords: string[];
  character_variations: string[];
  ai_tool_patterns: string[];
  common_video_titles: string[];
  false_positive_filters: string[];
  priority_weight: number;
  monitoring_strategy: string;
  reasoning: string;
}

export const ConfigGeneratorPage: React.FC = () => {
  const { user } = useAuth();
  const [view, setView] = useState<'list' | 'detail' | 'generate' | 'deleted'>('list');
  const [configs, setConfigs] = useState<IPConfig[]>([]);
  const [deletedConfigs, setDeletedConfigs] = useState<any[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<IPConfig | null>(null);

  // Check if user can edit (admin or editor only)
  const canEdit = user?.role === 'admin' || user?.role === 'editor';

  // AI Generation form state
  const [ipName, setIpName] = useState('');
  const [company, setCompany] = useState('');
  const [explanation, setExplanation] = useState('');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'critical'>('high');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedConfig, setGeneratedConfig] = useState<GeneratedConfig | null>(null);


  // Toast notification state
  const [toast, setToast] = useState<{message: string, type: 'success' | 'error'} | null>(null);

  // Delete confirmation modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Section editing states
  const [editingCharacters, setEditingCharacters] = useState(false);
  const [editingKeywords, setEditingKeywords] = useState(false);
  const [editingAIPatterns, setEditingAIPatterns] = useState(false);
  const [editingVisualKeywords, setEditingVisualKeywords] = useState(false);
  const [editingVideoTitles, setEditingVideoTitles] = useState(false);
  const [editingFalsePositives, setEditingFalsePositives] = useState(false);

  // Section data (loaded from Firestore)
  const [characters, setCharacters] = useState<string[]>([]);
  const [highPriorityKeywords, setHighPriorityKeywords] = useState<string[]>([]);
  const [mediumPriorityKeywords, setMediumPriorityKeywords] = useState<string[]>([]);
  const [lowPriorityKeywords, setLowPriorityKeywords] = useState<string[]>([]);
  const [aiPatterns, setAIPatterns] = useState<string[]>([]);
  const [visualKeywords, setVisualKeywords] = useState<string[]>([]);
  const [videoTitles, setVideoTitles] = useState<string[]>([]);
  const [falsePositives, setFalsePositives] = useState<string[]>([]);

  // Show toast helper
  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Discovery handler
  const handleDiscoverForIP = async (ipId: string, ipName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click

    try {
      const response = await fetch(`/api/discovery/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip_id: ipId, max_quota: 1000 })  // Use 1000 quota for IP-specific run
      });

      if (!response.ok) {
        throw new Error(`Discovery failed: ${response.statusText}`);
      }

      const data = await response.json();
      showToast(`🔍 Discovery started for "${ipName}"! (Run ID: ${data.run_id.substring(0, 8)}...)`, 'success');
    } catch (err) {
      console.error('Discovery error:', err);
      showToast(`Failed to start discovery: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  };

  // Delete config handler
  const handleDeleteConfig = () => {
    setShowDeleteModal(true);
  };

  const confirmDeleteConfig = async () => {
    if (!selectedConfig) return;

    setShowDeleteModal(false);

    try {
      const response = await fetch(`/api/config/${selectedConfig.id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete configuration');
      }

      const result = await response.json();
      showToast(result.message, 'success');

      // Go back to list and reload configs
      setView('list');
      setSelectedConfig(null);
      await loadConfigs();
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'Failed to delete configuration',
        'error'
      );
    }
  };

  // Load existing configs
  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      // Load from API
      const response = await fetch('/api/config/list');
      if (!response.ok) {
        throw new Error('Failed to load configurations');
      }

      const data = await response.json();

      // Transform API response to IPConfig format
      const configs: IPConfig[] = data.configs.map((config: any) => ({
        id: config.id,
        name: config.name,
        owner: config.owner,
        type: config.type || 'franchise',
        tier: config.tier || '1',
        characters: config.characters || [],
        priority: config.priority || 'medium'
      }));

      setConfigs(configs);
    } catch (err) {
      console.error('Failed to load configs:', err);
    }
  };

  const loadDeletedConfigs = async () => {
    try {
      const response = await fetch('/api/config/list-deleted');
      if (!response.ok) {
        throw new Error('Failed to load deleted configurations');
      }

      const data = await response.json();
      setDeletedConfigs(data.configs);
    } catch (err) {
      console.error('Failed to load deleted configs:', err);
    }
  };

  const handleRestoreConfig = async (configId: string, configName: string) => {
    try {
      const response = await fetch(`/api/config/${configId}/restore`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to restore configuration');
      }

      const result = await response.json();
      showToast(result.message, 'success');

      // Reload both lists
      await loadDeletedConfigs();
      await loadConfigs();
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'Failed to restore configuration',
        'error'
      );
    }
  };

  const loadConfigData = async (configId: string) => {
    try {
      const response = await fetch('/api/config/list');
      if (!response.ok) {
        throw new Error('Failed to load configuration data');
      }

      const data = await response.json();
      const config = data.configs.find((c: any) => c.id === configId);

      if (config) {
        setCharacters(config.characters || []);
        setHighPriorityKeywords(config.high_priority_keywords || []);
        setMediumPriorityKeywords(config.medium_priority_keywords || []);
        setLowPriorityKeywords(config.low_priority_keywords || []);
        setAIPatterns(config.ai_tool_patterns || []);
        setVisualKeywords(config.visual_keywords || []);
        setVideoTitles(config.common_video_titles || []);
        setFalsePositives(config.false_positive_filters || []);
      }
    } catch (err) {
      console.error('Failed to load config data:', err);
    }
  };

  // Load config data when entering detail view
  useEffect(() => {
    if (view === 'detail' && selectedConfig) {
      loadConfigData(selectedConfig.id);
    }
  }, [view, selectedConfig]);

  const handleGenerate = async () => {
    if (!ipName.trim() || !company.trim()) {
      setError('Please enter both IP name and company');
      return;
    }

    setLoading(true);
    setError(null);
    setGeneratedConfig(null);

    try {
      const response = await fetch('/api/config/ai/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: ipName,
          company: company,
          priority: priority,
          explanation: explanation || undefined, // Only send if provided
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate configuration');
      }

      const data = await response.json();
      setGeneratedConfig(data);

      // Populate editable states with generated data for immediate editing
      setCharacters(data.main_characters || []);
      setHighPriorityKeywords(data.high_priority_keywords || []);
      setMediumPriorityKeywords(data.medium_priority_keywords || []);
      setLowPriorityKeywords(data.low_priority_keywords || []);
      setAIPatterns(data.ai_tool_patterns || []);
      setVisualKeywords(data.visual_keywords || []);
      setVideoTitles(data.common_video_titles || []);
      setFalsePositives(data.false_positive_filters || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Handler functions for editable sections

  // Characters
  const updateCharacters = async (newCharacters: string[]) => {
    // If editing generated config (not yet saved), just update local state
    if (!selectedConfig && generatedConfig) {
      setCharacters(newCharacters);
      return;
    }

    // Otherwise, save to backend
    const response = await fetch(`/api/config/${selectedConfig!.id}/characters`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: newCharacters })
    });
    if (!response.ok) throw new Error('Failed to update characters');
    setCharacters(newCharacters);
    // Also update selectedConfig so the header count updates
    if (selectedConfig) {
      selectedConfig.characters = newCharacters;
    }
    showToast('Characters updated successfully!');
  };

  const suggestCharacters = async (userPrompt?: string): Promise<string[]> => {
    const currentIpName = selectedConfig?.name || generatedConfig?.name || ipName;
    const response = await fetch('/api/config/ai/suggest-characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip_name: currentIpName,
        existing_items: characters,
        user_prompt: userPrompt
      })
    });
    if (!response.ok) throw new Error('Failed to get suggestions');
    const data = await response.json();
    return data.suggestions;
  };

  // Keywords
  const updateKeywords = async (newKeywords: string[]) => {
    // If editing generated config (not yet saved), just update local state
    if (!selectedConfig && generatedConfig) {
      setKeywords(newKeywords);
      return;
    }

    const response = await fetch(`/api/config/${selectedConfig!.id}/keywords`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: newKeywords })
    });
    if (!response.ok) throw new Error('Failed to update keywords');
    setKeywords(newKeywords);
    showToast('Keywords updated successfully!');
  };

  const suggestKeywords = async (userPrompt?: string): Promise<string[]> => {
    const currentIpName = selectedConfig?.name || generatedConfig?.name || ipName;
    const response = await fetch('/api/config/ai/suggest-keywords', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip_name: currentIpName,
        existing_items: keywords,
        user_prompt: userPrompt
      })
    });
    if (!response.ok) throw new Error('Failed to get suggestions');
    const data = await response.json();
    return data.suggestions;
  };

  // AI Patterns
  const updateAIPatterns = async (newPatterns: string[]) => {
    // If editing generated config (not yet saved), just update local state
    if (!selectedConfig && generatedConfig) {
      setAIPatterns(newPatterns);
      return;
    }

    const response = await fetch(`/api/config/${selectedConfig!.id}/ai-patterns`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: newPatterns })
    });
    if (!response.ok) throw new Error('Failed to update AI patterns');
    setAIPatterns(newPatterns);
    showToast('AI patterns updated successfully!');
  };

  const suggestAIPatterns = async (userPrompt?: string): Promise<string[]> => {
    const response = await fetch('/api/config/ai/suggest-ai-patterns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip_name: selectedConfig!.name,
        existing_items: aiPatterns,
        user_prompt: userPrompt
      })
    });
    if (!response.ok) throw new Error('Failed to get suggestions');
    const data = await response.json();
    return data.suggestions;
  };

  // Visual Keywords
  const updateVisualKeywords = async (newKeywords: string[]) => {
    // If editing generated config (not yet saved), just update local state
    if (!selectedConfig && generatedConfig) {
      setVisualKeywords(newKeywords);
      return;
    }

    const response = await fetch(`/api/config/${selectedConfig!.id}/visual-keywords`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: newKeywords })
    });
    if (!response.ok) throw new Error('Failed to update visual keywords');
    setVisualKeywords(newKeywords);
    showToast('Visual keywords updated successfully!');
  };

  const suggestVisualKeywords = async (userPrompt?: string): Promise<string[]> => {
    const response = await fetch('/api/config/ai/suggest-visual-keywords', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip_name: selectedConfig!.name,
        existing_items: visualKeywords,
        user_prompt: userPrompt
      })
    });
    if (!response.ok) throw new Error('Failed to get suggestions');
    const data = await response.json();
    return data.suggestions;
  };

  // Video Titles
  const updateVideoTitles = async (newTitles: string[]) => {
    // If editing generated config (not yet saved), just update local state
    if (!selectedConfig && generatedConfig) {
      setVideoTitles(newTitles);
      return;
    }

    const response = await fetch(`/api/config/${selectedConfig!.id}/video-titles`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: newTitles })
    });
    if (!response.ok) throw new Error('Failed to update video titles');
    setVideoTitles(newTitles);
    showToast('Video titles updated successfully!');
  };

  const suggestVideoTitles = async (userPrompt?: string): Promise<string[]> => {
    const response = await fetch('/api/config/ai/suggest-video-titles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip_name: selectedConfig!.name,
        existing_items: videoTitles,
        user_prompt: userPrompt
      })
    });
    if (!response.ok) throw new Error('Failed to get suggestions');
    const data = await response.json();
    return data.suggestions;
  };

  // False Positive Filters
  const updateFalsePositives = async (newFilters: string[]) => {
    // If editing generated config (not yet saved), just update local state
    if (!selectedConfig && generatedConfig) {
      setFalsePositives(newFilters);
      return;
    }

    const response = await fetch(`/api/config/${selectedConfig!.id}/false-positive-filters`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: newFilters })
    });
    if (!response.ok) throw new Error('Failed to update false positive filters');
    setFalsePositives(newFilters);
    showToast('False positive filters updated successfully!');
  };

  const suggestFalsePositives = async (userPrompt?: string): Promise<string[]> => {
    const response = await fetch('/api/config/ai/suggest-false-positive-filters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip_name: selectedConfig!.name,
        existing_items: falsePositives,
        user_prompt: userPrompt
      })
    });
    if (!response.ok) throw new Error('Failed to get suggestions');
    const data = await response.json();
    return data.suggestions;
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-800';
      case 'medium': return 'bg-orange-100 text-orange-800';
      case 'low': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // List View
  if (view === 'list') {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        {/* Toast Notification */}
        {toast && (
          <div className={`fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white font-medium z-50 animate-fade-in-down`}>
            <div className="flex items-center gap-2">
              {toast.type === 'success' ? (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {toast.message}
            </div>
          </div>
        )}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="mb-8 flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">IP Configuration</h1>
              <p className="mt-2 text-gray-600">
                Manage intellectual property monitoring configurations
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setView('deleted');
                  loadDeletedConfigs();
                }}
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
              >
                <svg className="-ml-1 mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Deleted Configs
              </button>
              <button
                onClick={() => setView('generate')}
                disabled={!canEdit}
                className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white ${
                  canEdit
                    ? 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                    : 'bg-gray-400 cursor-not-allowed opacity-60'
                }`}
                title={!canEdit ? `${user?.role} role cannot create IP configurations` : ''}
              >
                <svg className="-ml-1 mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add New IP
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white shadow rounded-lg p-6">
              <div className="text-sm font-medium text-gray-500">Total IPs</div>
              <div className="mt-2 text-3xl font-bold text-gray-900">{configs.length}</div>
            </div>
            <div className="bg-white shadow rounded-lg p-6">
              <div className="text-sm font-medium text-gray-500">High Priority</div>
              <div className="mt-2 text-3xl font-bold text-red-600">
                {configs.filter(c => c.priority === 'high').length}
              </div>
            </div>
            <div className="bg-white shadow rounded-lg p-6">
              <div className="text-sm font-medium text-gray-500">Total Characters</div>
              <div className="mt-2 text-3xl font-bold text-blue-600">
                {configs.reduce((sum, c) => sum + c.characters.length, 0)}
              </div>
            </div>
          </div>

          {/* Config Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {configs.map((config) => (
              <div
                key={config.id}
                onClick={() => {
                  setSelectedConfig(config);
                  setView('detail');
                }}
                className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow cursor-pointer border-2 border-transparent hover:border-blue-500"
              >
                <h3 className="text-xl font-semibold text-gray-900 mb-2">{config.name}</h3>
                <p className="text-sm text-gray-600 mb-3">{config.owner}</p>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm">
                    <span className="text-gray-500">Priority: </span>
                    <span className="font-medium text-gray-900">{config.priority}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={(e) => handleDiscoverForIP(config.id, config.name, e)}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors flex items-center justify-center gap-2"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    Discover Videos
                  </button>
                  <div className="flex items-center">
                    <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Detail View
  if (view === 'detail' && selectedConfig) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        {/* Toast Notification */}
        {toast && (
          <div className={`fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white font-medium z-50`}>
            <div className="flex items-center gap-2">
              {toast.type === 'success' ? (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {toast.message}
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteModal && (
          <div className="fixed inset-0 bg-gray-600/75 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
              <div className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                    <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Delete Configuration</h3>
                    <p className="text-sm text-gray-500">This action cannot be undone</p>
                  </div>
                </div>
                <p className="text-gray-700 mb-6">
                  Are you sure you want to delete <span className="font-semibold">"{selectedConfig.name}"</span>?
                  All associated data will be permanently removed.
                </p>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setShowDeleteModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={confirmDeleteConfig}
                    className="px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Back Button and Actions */}
          <div className="mb-6 flex items-center justify-between">
            <button
              onClick={() => setView('list')}
              className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
            >
              <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to list
            </button>

            <button
              onClick={handleDeleteConfig}
              disabled={!canEdit}
              className={`inline-flex items-center px-4 py-2 border border-red-300 text-sm font-medium rounded-md ${
                canEdit
                  ? 'text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500'
                  : 'text-gray-400 bg-gray-100 cursor-not-allowed opacity-60'
              } transition-colors`}
              title={!canEdit ? `${user?.role} role cannot delete configurations` : ''}
            >
              <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete Configuration
            </button>
          </div>

          {/* Header */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{selectedConfig.name}</h1>
            <p className="text-gray-600 mb-4">{selectedConfig.owner}</p>
            <div className="flex gap-4 text-sm">
              <div>
                <span className="text-gray-500">Priority: </span>
                <span className={`font-medium px-2 py-1 rounded ${getPriorityColor(selectedConfig.priority)}`}>
                  {selectedConfig.priority.toUpperCase()}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {/* Characters */}
            <div className="bg-white shadow rounded-lg p-6">
              <EditableTagsSection
                title="Characters"
                items={characters}
                onUpdate={updateCharacters}
                onSuggestMore={suggestCharacters}
                isEditing={editingCharacters}
                onToggleEdit={() => setEditingCharacters(!editingCharacters)}
                colorScheme={{
                  displayBg: 'bg-purple-100',
                  displayText: 'text-purple-800',
                  editBorder: 'border-purple-300',
                  editBg: 'bg-purple-50',
                  itemBg: 'bg-purple-100',
                  itemText: 'text-purple-800'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Main characters from {selectedConfig.name}
              </p>
            </div>

            {/* High Priority Keywords */}
            <div className="bg-white shadow rounded-lg p-6 border-l-4 border-red-500">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-bold px-2 py-1 bg-red-100 text-red-800 rounded">🔴 HIGH PRIORITY</span>
                <span className="text-xs text-gray-500">Scan every 3 days</span>
              </div>
              <EditableTagsSection
                title="High Priority Keywords"
                items={highPriorityKeywords}
                onUpdate={async (newItems) => {
                  setHighPriorityKeywords(newItems);
                  if (selectedConfig) {
                    const response = await fetch(`/api/config/${selectedConfig.id}/high-priority-keywords`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ values: newItems })
                    });
                    if (response.ok) {
                      showToast('High priority keywords updated!');
                    }
                  }
                }}
                onSuggestMore={async () => []}
                isEditing={editingKeywords}
                onToggleEdit={() => setEditingKeywords(!editingKeywords)}
                colorScheme={{
                  displayBg: 'bg-red-50',
                  displayText: 'text-red-900',
                  editBorder: 'border-red-300',
                  editBg: 'bg-red-50',
                  itemBg: 'bg-red-100',
                  itemText: 'text-red-900',
                  button: 'bg-red-600',
                  buttonHover: 'hover:bg-red-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Broad keywords (character + "ai") - most efficient, scanned most often
              </p>
            </div>

            {/* Medium Priority Keywords */}
            <div className="bg-white shadow rounded-lg p-6 border-l-4 border-yellow-500">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-bold px-2 py-1 bg-yellow-100 text-yellow-800 rounded">🟡 MEDIUM PRIORITY</span>
                <span className="text-xs text-gray-500">Scan every 7 days</span>
              </div>
              <EditableTagsSection
                title="Medium Priority Keywords"
                items={mediumPriorityKeywords}
                onUpdate={async (newItems) => {
                  setMediumPriorityKeywords(newItems);
                  if (selectedConfig) {
                    const response = await fetch(`/api/config/${selectedConfig.id}/medium-priority-keywords`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ values: newItems })
                    });
                    if (response.ok) {
                      showToast('Medium priority keywords updated!');
                    }
                  }
                }}
                onSuggestMore={async () => []}
                isEditing={false}
                onToggleEdit={() => {}}
                colorScheme={{
                  displayBg: 'bg-yellow-50',
                  displayText: 'text-yellow-900',
                  editBorder: 'border-yellow-300',
                  editBg: 'bg-yellow-50',
                  itemBg: 'bg-yellow-100',
                  itemText: 'text-yellow-900',
                  button: 'bg-yellow-600',
                  buttonHover: 'hover:bg-yellow-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Popular AI tools (Sora, Runway, Kling, Pika) - scanned weekly
              </p>
            </div>

            {/* Low Priority Keywords */}
            <div className="bg-white shadow rounded-lg p-6 border-l-4 border-green-500">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-bold px-2 py-1 bg-green-100 text-green-800 rounded">🟢 LOW PRIORITY</span>
                <span className="text-xs text-gray-500">Scan every 14 days</span>
              </div>
              <EditableTagsSection
                title="Low Priority Keywords"
                items={lowPriorityKeywords}
                onUpdate={async (newItems) => {
                  setLowPriorityKeywords(newItems);
                  if (selectedConfig) {
                    const response = await fetch(`/api/config/${selectedConfig.id}/low-priority-keywords`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ values: newItems })
                    });
                    if (response.ok) {
                      showToast('Low priority keywords updated!');
                    }
                  }
                }}
                onSuggestMore={async () => []}
                isEditing={false}
                onToggleEdit={() => {}}
                colorScheme={{
                  displayBg: 'bg-green-50',
                  displayText: 'text-green-900',
                  editBorder: 'border-green-300',
                  editBg: 'bg-green-50',
                  itemBg: 'bg-green-100',
                  itemText: 'text-green-900',
                  button: 'bg-green-600',
                  buttonHover: 'hover:bg-green-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Niche AI tools (Luma, Veo, Minimax, etc.) - scanned bi-weekly
              </p>
            </div>

            {/* AI Tool Patterns */}
            <div className="bg-white shadow rounded-lg p-6">
              <EditableTagsSection
                title="AI Tool Patterns"
                items={aiPatterns}
                onUpdate={updateAIPatterns}
                onSuggestMore={suggestAIPatterns}
                isEditing={editingAIPatterns}
                onToggleEdit={() => setEditingAIPatterns(!editingAIPatterns)}
                colorScheme={{
                  displayBg: 'bg-orange-50',
                  displayText: 'text-orange-900',
                  editBorder: 'border-orange-300',
                  editBg: 'bg-orange-50',
                  itemBg: 'bg-orange-100',
                  itemText: 'text-orange-900'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Specific combinations of IP + AI tools to detect
              </p>
            </div>

            {/* Visual Detection Markers */}
            <div className="bg-white shadow rounded-lg p-6">
              <EditableTagsSection
                title="Visual Detection Markers"
                items={visualKeywords}
                onUpdate={updateVisualKeywords}
                onSuggestMore={suggestVisualKeywords}
                isEditing={editingVisualKeywords}
                onToggleEdit={() => setEditingVisualKeywords(!editingVisualKeywords)}
                colorScheme={{
                  displayBg: 'bg-green-100',
                  displayText: 'text-green-800',
                  editBorder: 'border-green-300',
                  editBg: 'bg-green-50',
                  itemBg: 'bg-green-100',
                  itemText: 'text-green-800'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Key visual elements for vision analysis
              </p>
            </div>

            {/* Common Video Titles */}
            <div className="bg-white shadow rounded-lg p-6">
              <EditableTagsSection
                title="Common Video Title Patterns"
                items={videoTitles}
                onUpdate={updateVideoTitles}
                onSuggestMore={suggestVideoTitles}
                isEditing={editingVideoTitles}
                onToggleEdit={() => setEditingVideoTitles(!editingVideoTitles)}
                colorScheme={{
                  displayBg: 'bg-gray-50',
                  displayText: 'text-gray-700',
                  editBorder: 'border-gray-300',
                  editBg: 'bg-gray-50',
                  itemBg: 'bg-gray-100',
                  itemText: 'text-gray-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Common title patterns to search for on YouTube
              </p>
            </div>

            {/* False Positive Filters */}
            <div className="bg-white shadow rounded-lg p-6">
              <EditableTagsSection
                title="False Positive Filters"
                items={falsePositives}
                onUpdate={updateFalsePositives}
                onSuggestMore={suggestFalsePositives}
                isEditing={editingFalsePositives}
                onToggleEdit={() => setEditingFalsePositives(!editingFalsePositives)}
                colorScheme={{
                  displayBg: 'bg-yellow-100',
                  displayText: 'text-yellow-800',
                  editBorder: 'border-yellow-300',
                  editBg: 'bg-yellow-50',
                  itemBg: 'bg-yellow-100',
                  itemText: 'text-yellow-800'
                }}
              />
              <p className="text-xs text-gray-500 mt-2">
                Keywords that indicate non-infringing content
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Generate View (Configuration Manager Form)
  if (view === 'generate') {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white font-medium z-50`}>
          <div className="flex items-center gap-2">
            {toast.type === 'success' ? (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
            {toast.message}
          </div>
        </div>
      )}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button */}
        <button
          onClick={() => {
            setView('list');
            setIpName('');
            setCompany('');
            setGeneratedConfig(null);
            setError(null);
          }}
          className="mb-6 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to list
        </button>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Configuration Manager</h1>
          <p className="mt-2 text-gray-600">
            Enter an IP name and company to generate a complete monitoring configuration
          </p>
        </div>

        {/* Input Form */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="ipName" className="block text-sm font-medium text-gray-700">
                IP Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="ipName"
                value={ipName}
                onChange={(e) => setIpName(e.target.value)}
                placeholder="e.g., Harry Potter, Star Wars"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="company" className="block text-sm font-medium text-gray-700">
                Company <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="e.g., Warner Bros, Disney"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
                disabled={loading}
              />
            </div>

            <div className="sm:col-span-2">
              <label htmlFor="explanation" className="block text-sm font-medium text-gray-700">
                Additional Context (Optional)
              </label>
              <p className="mt-1 text-xs text-gray-500 mb-2">
                Provide any specific details, character lists, or special instructions to consider when generating the configuration.
              </p>
              <textarea
                id="explanation"
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
                placeholder="e.g., Focus on the main trilogy characters only, include Mandalorian series, exclude animated versions..."
                rows={4}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
                disabled={loading}
              />
            </div>

            <div className="sm:col-span-2">
              <label htmlFor="priority" className="block text-sm font-medium text-gray-700">
                Business Priority
              </label>
              <select
                id="priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as any)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
                disabled={loading}
              >
                <option value="low">Low - Minor IP, selective monitoring</option>
                <option value="medium">Medium - Standard monitoring</option>
                <option value="high">High - Valuable franchise, aggressive monitoring</option>
                <option value="critical">Critical - Flagship IP, maximum protection</option>
              </select>
            </div>
          </div>

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div className="mt-6">
            <button
              onClick={handleGenerate}
              disabled={loading || !canEdit}
              className="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              title={!canEdit ? `${user?.role} role cannot generate IP configurations` : ''}
            >
              {loading ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating configuration...
                </>
              ) : (
                <>
                  <svg className="-ml-1 mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Generate Configuration
                </>
              )}
            </button>
          </div>
        </div>

        {/* Generated Config Display */}
        {generatedConfig && (
          <div className="space-y-6">
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-semibold text-gray-900">Generated Configuration</h2>
                <button
                  onClick={async () => {
                    setLoading(true);
                    setError(null);

                    try {
                      // Build config from current edited state (not original generated config)
                      const configToSave = {
                        ...generatedConfig,
                        main_characters: characters,
                        high_priority_keywords: highPriorityKeywords,
                        medium_priority_keywords: mediumPriorityKeywords,
                        low_priority_keywords: lowPriorityKeywords,
                        ai_tool_patterns: aiPatterns,
                        visual_keywords: visualKeywords,
                        common_video_titles: videoTitles,
                        false_positive_filters: falsePositives,
                      };

                      const response = await fetch('/api/config/ai/save', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(configToSave),
                      });

                      if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || 'Failed to save configuration');
                      }

                      await response.json();

                      showToast(`Successfully saved ${ipName}!`);

                      // Reset form and go back to list view
                      setView('list');
                      setIpName('');
                      setCompany('');
                      setGeneratedConfig(null);
                      loadConfigs();
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Failed to save configuration');
                    } finally {
                      setLoading(false);
                    }
                  }}
                  disabled={loading || !canEdit}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={!canEdit ? `${user?.role} role cannot save configurations` : ''}
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Saving...
                    </>
                  ) : (
                    <>
                      <svg className="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                      </svg>
                      Save Configuration
                    </>
                  )}
                </button>
              </div>

              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm font-medium text-gray-500">Name</dt>
                  <dd className="mt-1 text-sm text-gray-900">{generatedConfig.name}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Owner</dt>
                  <dd className="mt-1 text-sm text-gray-900">{generatedConfig.owner}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-sm font-medium text-gray-500">Description</dt>
                  <dd className="mt-1 text-sm text-gray-900">{generatedConfig.description}</dd>
                </div>
              </dl>
            </div>

            {/* Editable Sections */}
            <EditableTagsSection
              title="Characters"
              items={characters}
              onUpdate={updateCharacters}
              onSuggestMore={suggestCharacters}
              isEditing={editingCharacters}
              onToggleEdit={() => setEditingCharacters(!editingCharacters)}
              colorScheme={{
                displayBg: 'bg-purple-100',
                displayText: 'text-purple-800',
                editBorder: 'border-purple-300',
                editFocus: 'focus:ring-purple-500 focus:border-purple-500',
                buttonBg: 'bg-purple-600',
                buttonHover: 'hover:bg-purple-700'
              }}
            />

            {/* High Priority Keywords */}
            <div className="border-l-4 border-red-500 pl-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold px-2 py-1 bg-red-100 text-red-800 rounded">🔴 HIGH PRIORITY</span>
                <span className="text-xs text-gray-500">Scan every 3 days</span>
              </div>
              <EditableTagsSection
                title="High Priority Keywords"
                items={highPriorityKeywords}
                onUpdate={async (newItems) => setHighPriorityKeywords(newItems)}
                onSuggestMore={async () => []}
                isEditing={editingKeywords}
                onToggleEdit={() => setEditingKeywords(!editingKeywords)}
                colorScheme={{
                  displayBg: 'bg-red-50',
                  displayText: 'text-red-900',
                  editBorder: 'border-red-300',
                  editFocus: 'focus:ring-red-500 focus:border-red-500',
                  buttonBg: 'bg-red-600',
                  buttonHover: 'hover:bg-red-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-1">Character + "ai" - broad, efficient</p>
            </div>

            {/* Medium Priority Keywords */}
            <div className="border-l-4 border-yellow-500 pl-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold px-2 py-1 bg-yellow-100 text-yellow-800 rounded">🟡 MEDIUM PRIORITY</span>
                <span className="text-xs text-gray-500">Scan every 7 days</span>
              </div>
              <EditableTagsSection
                title="Medium Priority Keywords"
                items={mediumPriorityKeywords}
                onUpdate={async (newItems) => setMediumPriorityKeywords(newItems)}
                onSuggestMore={async () => []}
                isEditing={false}
                onToggleEdit={() => {}}
                colorScheme={{
                  displayBg: 'bg-yellow-50',
                  displayText: 'text-yellow-900',
                  editBorder: 'border-yellow-300',
                  editFocus: 'focus:ring-yellow-500 focus:border-yellow-500',
                  buttonBg: 'bg-yellow-600',
                  buttonHover: 'hover:bg-yellow-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-1">Popular tools (Sora, Runway, Kling, Pika)</p>
            </div>

            {/* Low Priority Keywords */}
            <div className="border-l-4 border-green-500 pl-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold px-2 py-1 bg-green-100 text-green-800 rounded">🟢 LOW PRIORITY</span>
                <span className="text-xs text-gray-500">Scan every 14 days</span>
              </div>
              <EditableTagsSection
                title="Low Priority Keywords"
                items={lowPriorityKeywords}
                onUpdate={async (newItems) => setLowPriorityKeywords(newItems)}
                onSuggestMore={async () => []}
                isEditing={false}
                onToggleEdit={() => {}}
                colorScheme={{
                  displayBg: 'bg-green-50',
                  displayText: 'text-green-900',
                  editBorder: 'border-green-300',
                  editFocus: 'focus:ring-green-500 focus:border-green-500',
                  buttonBg: 'bg-green-600',
                  buttonHover: 'hover:bg-green-700'
                }}
              />
              <p className="text-xs text-gray-500 mt-1">Niche tools (Luma, Veo, Minimax, Gen-2, Gen-3)</p>
            </div>

            <EditableTagsSection
              title="AI Tool Patterns"
              items={aiPatterns}
              onUpdate={updateAIPatterns}
              onSuggestMore={suggestAIPatterns}
              isEditing={editingAIPatterns}
              onToggleEdit={() => setEditingAIPatterns(!editingAIPatterns)}
              colorScheme={{
                displayBg: 'bg-orange-50',
                displayText: 'text-orange-900',
                editBorder: 'border-orange-300',
                editFocus: 'focus:ring-orange-500 focus:border-orange-500',
                buttonBg: 'bg-orange-600',
                buttonHover: 'hover:bg-orange-700'
              }}
            />

            <EditableTagsSection
              title="Visual Detection Markers"
              items={visualKeywords}
              onUpdate={updateVisualKeywords}
              onSuggestMore={suggestVisualKeywords}
              isEditing={editingVisualKeywords}
              onToggleEdit={() => setEditingVisualKeywords(!editingVisualKeywords)}
              colorScheme={{
                displayBg: 'bg-green-100',
                displayText: 'text-green-800',
                editBorder: 'border-green-300',
                editFocus: 'focus:ring-green-500 focus:border-green-500',
                buttonBg: 'bg-green-600',
                buttonHover: 'hover:bg-green-700'
              }}
            />

            <EditableTagsSection
              title="Common Video Title Patterns"
              items={videoTitles}
              onUpdate={updateVideoTitles}
              onSuggestMore={suggestVideoTitles}
              isEditing={editingVideoTitles}
              onToggleEdit={() => setEditingVideoTitles(!editingVideoTitles)}
              colorScheme={{
                displayBg: 'bg-gray-50',
                displayText: 'text-gray-700',
                editBorder: 'border-gray-300',
                editFocus: 'focus:ring-gray-500 focus:border-gray-500',
                buttonBg: 'bg-gray-600',
                buttonHover: 'hover:bg-gray-700'
              }}
            />

            <EditableTagsSection
              title="False Positive Filters"
              items={falsePositives}
              onUpdate={updateFalsePositives}
              onSuggestMore={suggestFalsePositives}
              isEditing={editingFalsePositives}
              onToggleEdit={() => setEditingFalsePositives(!editingFalsePositives)}
              colorScheme={{
                displayBg: 'bg-yellow-100',
                displayText: 'text-yellow-800',
                editBorder: 'border-yellow-300',
                editFocus: 'focus:ring-yellow-500 focus:border-yellow-500',
                buttonBg: 'bg-yellow-600',
                buttonHover: 'hover:bg-yellow-700'
              }}
            />

            {/* Reasoning */}
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 shadow rounded-lg p-6 border border-blue-100">
              <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                <svg className="h-5 w-5 mr-2 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Configuration Analysis
              </h3>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{generatedConfig.reasoning}</p>
            </div>
          </div>
        )}
      </div>
    </div>
    );
  }

  // Deleted Configs View
  if (view === 'deleted') {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        {/* Toast Notification */}
        {toast && (
          <div className={`fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white font-medium z-50`}>
            <div className="flex items-center gap-2">
              {toast.type === 'success' ? (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {toast.message}
            </div>
          </div>
        )}

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="mb-8 flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Deleted Configurations</h1>
              <p className="mt-2 text-gray-600">
                Restore or permanently remove deleted IP configurations
              </p>
            </div>
            <button
              onClick={() => setView('list')}
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
            >
              <svg className="-ml-1 mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to Active Configs
            </button>
          </div>

          {deletedConfigs.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-12 text-center">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <h3 className="mt-4 text-lg font-medium text-gray-900">No deleted configurations</h3>
              <p className="mt-2 text-sm text-gray-500">All your configurations are active.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {deletedConfigs.map((config) => (
                <div
                  key={config.id}
                  className="bg-white shadow rounded-lg p-6 border-l-4 border-red-400"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-xl font-semibold text-gray-900 mb-2">{config.name}</h3>
                      <div className="text-sm text-gray-600 space-y-1">
                        <p><span className="font-medium">Characters:</span> {config.characters?.length || 0}</p>
                        <p><span className="font-medium">Priority:</span> {config.priority}</p>
                        <p><span className="font-medium">Deleted videos:</span> {config.deleted_video_count || 0}</p>
                        <p><span className="font-medium">Deleted at:</span> {config.deleted_at ? new Date(config.deleted_at).toLocaleString() : 'Unknown'}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRestoreConfig(config.id, config.name)}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-colors"
                    >
                      <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Restore
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Default fallback (should not reach here)
  return null;
};
