import { api } from './client'
import type { VideoListResponse, VideoMetadata, VideoStatus } from '../types'

export interface VideoListParams {
  status?: VideoStatus
  has_ip_match?: boolean
  channel_id?: string
  infringement_status?: string  // actionable|tolerated|clean
  sort_by?: string
  sort_desc?: boolean
  limit?: number
  offset?: number
}

export const videosAPI = {
  list: (params?: VideoListParams) => {
    const searchParams = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value))
        }
      })
    }
    const query = searchParams.toString()
    return api.get<VideoListResponse>(`/videos${query ? `?${query}` : ''}`)
  },
  getVideo: (videoId: string) => api.get<VideoMetadata>(`/videos/${videoId}`),
  scanVideo: (videoId: string) => api.post<{ success: boolean; message: string }>(`/videos/${videoId}/scan`, {}),
  listProcessing: () => api.get<{ processing_videos: VideoMetadata[]; count: number }>(`/videos/processing/list`),
}
