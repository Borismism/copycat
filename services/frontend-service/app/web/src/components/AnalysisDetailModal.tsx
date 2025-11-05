import { Fragment, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import type { VisionAnalysis } from '../types'

interface AnalysisDetailModalProps {
  isOpen: boolean
  onClose: () => void
  analysis: VisionAnalysis
  videoTitle: string
  videoId: string
}

export default function AnalysisDetailModal({
  isOpen,
  onClose,
  analysis,
  videoTitle,
  videoId,
}: AnalysisDetailModalProps) {
  const [isRescanning, setIsRescanning] = useState(false)
  const [rescanSuccess, setRescanSuccess] = useState(false)

  const handleRescan = async () => {
    setIsRescanning(true)
    setRescanSuccess(false)
    try {
      // Trigger immediate scan via API
      const response = await fetch(`http://localhost:8080/api/videos/${videoId}/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      if (response.ok) {
        setRescanSuccess(true)
        // Auto-close after brief success message
        setTimeout(() => {
          onClose()
        }, 1500)
      } else {
        const error = await response.text()
        console.error('Rescan failed:', error)
      }
    } catch (error) {
      console.error('Rescan error:', error)
    } finally {
      setIsRescanning(false)
    }
  }

  const getActionBadgeColor = (action: string) => {
    switch (action) {
      case 'immediate_takedown':
        return 'bg-red-100 text-red-800'
      case 'monitor':
        return 'bg-yellow-100 text-yellow-800'
      case 'safe_harbor':
      case 'ignore':
        return 'bg-green-100 text-green-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-40" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden rounded-2xl bg-white text-left align-middle shadow-xl transition-all">
                {/* Header */}
                <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 text-white">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <Dialog.Title as="h3" className="text-lg font-semibold">
                        Copyright Analysis Report
                      </Dialog.Title>
                      <p className="mt-1 text-sm opacity-90 line-clamp-1">{videoTitle}</p>
                      <p className="text-xs opacity-75 mt-0.5">Video ID: {videoId}</p>
                    </div>
                    <button
                      onClick={onClose}
                      className="ml-4 text-white/80 hover:text-white transition-colors"
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Body */}
                <div className="p-6 max-h-[70vh] overflow-y-auto space-y-6">
                  {/* Overall Summary */}
                  <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 border-2 border-blue-200">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-bold text-gray-900">Overall Assessment</h3>
                      <div className={`inline-flex items-center px-4 py-2 rounded-full text-sm font-bold ${getActionBadgeColor(analysis.overall_recommendation || 'ignore')}`}>
                        {(analysis.overall_recommendation || 'ignore').replace(/_/g, ' ').toUpperCase()}
                      </div>
                    </div>
                    {analysis.overall_notes && (
                      <p className="text-sm text-gray-700 leading-relaxed">{analysis.overall_notes}</p>
                    )}
                  </div>

                  {/* Per-IP Results */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-gray-900 border-b pb-2">IP Analysis Results ({analysis.ip_results?.length || 0})</h3>
                    {analysis.ip_results && analysis.ip_results.length > 0 ? (
                      analysis.ip_results.map((ipResult, idx) => (
                        <div key={idx} className="border-2 rounded-lg p-5 bg-white shadow-sm">
                          {/* IP Header */}
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <h4 className="text-lg font-semibold text-gray-900">{ipResult.ip_name}</h4>
                              <p className="text-xs text-gray-500 mt-0.5">ID: {ipResult.ip_id}</p>
                            </div>
                            <div className="flex flex-wrap justify-end gap-2">
                              <div className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ${
                                ipResult.contains_infringement
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-green-100 text-green-800'
                              }`}>
                                {ipResult.contains_infringement ? 'INFRINGEMENT DETECTED' : 'NO INFRINGEMENT'}
                              </div>
                              {ipResult.content_type && (
                                <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                  {ipResult.content_type.replace(/_/g, ' ').toUpperCase()}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Infringement Likelihood */}
                          <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium text-gray-700">Infringement Likelihood</span>
                              <span className="text-2xl font-bold text-gray-900">{ipResult.infringement_likelihood}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full transition-all ${
                                  ipResult.infringement_likelihood >= 70 ? 'bg-red-500' :
                                  ipResult.infringement_likelihood >= 40 ? 'bg-yellow-500' :
                                  'bg-green-500'
                                }`}
                                style={{ width: `${ipResult.infringement_likelihood}%` }}
                              />
                            </div>
                          </div>

                          {/* Fair Use - ALWAYS show */}
                          {ipResult.fair_use_reasoning && (
                            <div className={`mb-4 p-3 rounded-lg border ${ipResult.fair_use_applies ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                              <div className="flex items-center gap-2 mb-2">
                                <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-bold ${ipResult.fair_use_applies ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                  {ipResult.fair_use_applies ? 'FAIR USE APPLIES' : 'NOT FAIR USE'}
                                </div>
                              </div>
                              <p className="text-sm text-gray-700 leading-relaxed">{ipResult.fair_use_reasoning}</p>
                            </div>
                          )}

                          {/* AI Detection */}
                          {ipResult.is_ai_generated && (
                            <div className="mb-4 p-3 bg-orange-50 rounded-lg border border-orange-200">
                              <div className="flex items-center gap-2 mb-2">
                                <div className="inline-flex items-center px-2 py-1 rounded-full text-xs font-bold bg-orange-100 text-orange-800">
                                  AI-GENERATED CONTENT
                                </div>
                              </div>
                              {ipResult.ai_tools_detected && ipResult.ai_tools_detected.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                  <span className="text-xs text-gray-600 font-medium">Tools detected:</span>
                                  {ipResult.ai_tools_detected.map((tool, toolIdx) => (
                                    <span
                                      key={toolIdx}
                                      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800"
                                    >
                                      {tool}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Characters Detected */}
                          {ipResult.characters_detected && ipResult.characters_detected.length > 0 && (
                            <div className="mb-4">
                              <h5 className="text-sm font-semibold text-gray-900 mb-2 flex items-center">
                                <svg className="w-4 h-4 mr-1.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                                  />
                                </svg>
                                Characters Detected ({ipResult.characters_detected.length})
                              </h5>
                              <div className="space-y-2">
                                {ipResult.characters_detected.map((char, charIdx) => (
                                  <div key={charIdx} className="bg-gray-50 rounded p-3">
                                    <div className="flex items-start justify-between">
                                      <div className="flex-1">
                                        <div className="font-medium text-base">{char.name}</div>
                                        {char.description && (
                                          <div className="text-sm text-gray-600 mt-1">{char.description}</div>
                                        )}
                                        {char.timestamps && char.timestamps.length > 0 && (
                                          <div className="text-xs text-gray-500 mt-2">
                                            <span className="font-medium">Timestamps:</span> {char.timestamps.join(', ')}
                                          </div>
                                        )}
                                      </div>
                                      <div className="ml-4 text-right">
                                        {char.screen_time_seconds != null && (
                                          <>
                                            <div className="text-sm font-medium">{char.screen_time_seconds}s</div>
                                            <div className="text-xs text-gray-500">Screen Time</div>
                                          </>
                                        )}
                                        {char.prominence && (
                                          <span className={`inline-block mt-1 px-2 py-1 rounded-full text-xs ${
                                            char.prominence === 'primary' ? 'bg-red-100 text-red-800' :
                                            char.prominence === 'secondary' ? 'bg-yellow-100 text-yellow-800' :
                                            'bg-gray-100 text-gray-800'
                                          }`}>
                                            {char.prominence}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Reasoning */}
                          <div className="border-t pt-3">
                            <h5 className="text-sm font-semibold text-gray-900 mb-2 flex items-center">
                              <svg className="w-4 h-4 mr-1.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                />
                              </svg>
                              Analysis Reasoning
                            </h5>
                            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{ipResult.reasoning}</p>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center text-gray-500 py-8">
                        No IP analysis results available
                      </div>
                    )}
                  </div>
                </div>

                {/* Footer */}
                <div className="bg-gray-50 px-6 py-4 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleRescan}
                      disabled={isRescanning || rescanSuccess}
                      className={`px-4 py-2 rounded-lg transition-colors font-medium flex items-center gap-2 ${
                        rescanSuccess
                          ? 'bg-green-600 text-white'
                          : 'bg-orange-600 text-white hover:bg-orange-700'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {isRescanning && (
                        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      )}
                      {rescanSuccess && (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                      {rescanSuccess ? 'Scan Queued!' : isRescanning ? 'Starting...' : 'Rescan Video'}
                    </button>
                    {rescanSuccess && (
                      <span className="text-sm text-green-700">Watch Active Scans for progress</span>
                    )}
                  </div>
                  <button
                    onClick={onClose}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                  >
                    Close
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
