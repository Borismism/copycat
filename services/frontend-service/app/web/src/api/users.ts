import type { UserRole } from '../contexts/AuthContext'

export interface RoleAssignment {
  email?: string
  domain?: string
  role: UserRole
  assigned_by: string
  assigned_at: string
  notes?: string
}

export interface RoleListResponse {
  assignments: RoleAssignment[]
  total: number
}

export interface CreateRoleRequest {
  email?: string
  domain?: string
  role: UserRole
  notes?: string
}

export const usersApi = {
  async listRoles(limit = 100, offset = 0): Promise<RoleListResponse> {
    const response = await fetch(`/api/users/roles?limit=${limit}&offset=${offset}`, {
      credentials: 'include',
    })
    if (!response.ok) {
      throw new Error(`Failed to list roles: ${response.statusText}`)
    }
    return response.json()
  },

  async createRole(request: CreateRoleRequest): Promise<RoleAssignment> {
    const response = await fetch('/api/users/roles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || 'Failed to create role')
    }
    return response.json()
  },

  async updateRole(identifier: string, role: UserRole, notes?: string): Promise<RoleAssignment> {
    const params = new URLSearchParams({ role })
    if (notes) params.append('notes', notes)

    const response = await fetch(`/api/users/roles/${identifier}?${params}`, {
      method: 'PUT',
      credentials: 'include',
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || 'Failed to update role')
    }
    return response.json()
  },

  async deleteRole(identifier: string): Promise<void> {
    const response = await fetch(`/api/users/roles/${identifier}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || 'Failed to delete role')
    }
  },
}
