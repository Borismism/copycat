import { useState, useEffect } from 'react'
import { useAuth, UserRole } from '../contexts/AuthContext'
import { usersApi, RoleAssignment, CreateRoleRequest } from '../api/users'

export default function UserRolesPage() {
  const { user, actAs } = useAuth()
  const [assignments, setAssignments] = useState<RoleAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingAssignment, setEditingAssignment] = useState<{ identifier: string; assignment: RoleAssignment } | null>(null)

  useEffect(() => {
    loadRoles()
  }, [])

  const loadRoles = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await usersApi.listRoles()
      setAssignments(response.assignments)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load roles')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (identifier: string) => {
    if (!confirm('Are you sure you want to delete this role assignment?')) return

    try {
      await usersApi.deleteRole(identifier)
      await loadRoles()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete role')
    }
  }

  // Only admins can access this page
  if (user?.role !== 'admin') {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          Access denied. Only administrators can manage user roles.
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">User Role Management</h1>
          <p className="text-gray-600 mt-2">Manage user and domain-based role assignments</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          + Add Role Assignment
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">{error}</div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading roles...</div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  User/Domain
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Assigned By
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Assigned At
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Notes
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {assignments.map((assignment) => {
                const identifier = assignment.email
                  ? assignment.email.replace('@', '_at_').replace(/\./g, '_')
                  : assignment.domain!.replace(/\./g, '_')

                return (
                  <tr key={identifier}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {assignment.email ? (
                        <div className="flex items-center">
                          <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
                            USER
                          </span>
                          <span className="ml-2 text-sm font-medium text-gray-900">
                            {assignment.email}
                          </span>
                        </div>
                      ) : (
                        <div className="flex items-center">
                          <span className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded">
                            DOMAIN
                          </span>
                          <span className="ml-2 text-sm font-medium text-gray-900">
                            @{assignment.domain}
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-3 py-1 text-sm font-medium rounded-full ${
                          assignment.role === 'admin'
                            ? 'bg-purple-100 text-purple-800'
                            : assignment.role === 'editor'
                              ? 'bg-blue-100 text-blue-800'
                              : assignment.role === 'legal'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {assignment.role.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {assignment.assigned_by}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(assignment.assigned_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {assignment.notes || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex gap-3 justify-end">
                        {assignment.email && (
                          <button
                            onClick={() => actAs(assignment.email!)}
                            className="text-purple-600 hover:text-purple-900"
                            title="Act as this user"
                          >
                            Act As
                          </button>
                        )}
                        <button
                          onClick={() => setEditingAssignment({ identifier, assignment })}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(identifier)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {assignments.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No role assignments found. Click "Add Role Assignment" to create one.
            </div>
          )}
        </div>
      )}

      {showCreateModal && (
        <CreateRoleModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false)
            loadRoles()
          }}
        />
      )}

      {editingAssignment && (
        <EditRoleModal
          identifier={editingAssignment.identifier}
          assignment={editingAssignment.assignment}
          onClose={() => setEditingAssignment(null)}
          onUpdated={() => {
            setEditingAssignment(null)
            loadRoles()
          }}
        />
      )}
    </div>
  )
}

interface EditRoleModalProps {
  identifier: string
  assignment: RoleAssignment
  onClose: () => void
  onUpdated: () => void
}

function EditRoleModal({ identifier, assignment, onClose, onUpdated }: EditRoleModalProps) {
  const [role, setRole] = useState<UserRole>(assignment.role)
  const [notes, setNotes] = useState(assignment.notes || '')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await usersApi.updateRole(identifier, role, notes || undefined)
      onUpdated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role')
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Edit Role Assignment</h3>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-800 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Show user/domain (readonly) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {assignment.email ? 'User Email' : 'Domain'}
            </label>
            <div className="px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-sm text-gray-700">
              {assignment.email || `@${assignment.domain}`}
            </div>
          </div>

          {/* Role Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="read">Read - View-only access</option>
              <option value="legal">Legal - Edit legal fields</option>
              <option value="editor">Editor - Start scans, edit configs</option>
              <option value="admin">Admin - Full access</option>
            </select>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Why this role is assigned..."
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
              disabled={submitting}
            >
              {submitting ? 'Updating...' : 'Update'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

interface CreateRoleModalProps {
  onClose: () => void
  onCreated: () => void
}

function CreateRoleModal({ onClose, onCreated }: CreateRoleModalProps) {
  const [assignmentType, setAssignmentType] = useState<'email' | 'domain'>('email')
  const [email, setEmail] = useState('')
  const [domain, setDomain] = useState('')
  const [role, setRole] = useState<UserRole>('read')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const request: CreateRoleRequest = {
        role,
        notes: notes || undefined,
      }

      if (assignmentType === 'email') {
        request.email = email
      } else {
        request.domain = domain
      }

      await usersApi.createRole(request)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create role')
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Add Role Assignment</h3>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-800 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Assignment Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Assignment Type</label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="email"
                  checked={assignmentType === 'email'}
                  onChange={(e) => setAssignmentType(e.target.value as 'email')}
                  className="mr-2"
                />
                Specific User
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="domain"
                  checked={assignmentType === 'domain'}
                  onChange={(e) => setAssignmentType(e.target.value as 'domain')}
                  className="mr-2"
                />
                Entire Domain
              </label>
            </div>
          </div>

          {/* Email or Domain Input */}
          {assignmentType === 'email' ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="user@example.com"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Domain</label>
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="example.com"
              />
            </div>
          )}

          {/* Role Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="read">Read - View-only access</option>
              <option value="legal">Legal - Edit legal fields</option>
              <option value="editor">Editor - Start scans, edit configs</option>
              <option value="admin">Admin - Full access</option>
            </select>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Why this role is assigned..."
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
              disabled={submitting}
            >
              {submitting ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
