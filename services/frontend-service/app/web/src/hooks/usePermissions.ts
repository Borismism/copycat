import { useAuth } from '../contexts/AuthContext'

export function usePermissions() {
  const { user } = useAuth()

  return {
    // Admin: Full access
    isAdmin: user?.role === 'admin',

    // Editor: Can start scans, edit configs, manage channels
    canEdit: user?.role === 'admin' || user?.role === 'editor',

    // Legal: Can edit legal fields only
    canEditLegalFields: user?.role === 'admin' || user?.role === 'legal',

    // Read: View-only (internal users)
    isReadOnly: user?.role === 'read',

    // Client: External client view (simplified dashboard)
    isClient: user?.role === 'client',

    // Role-specific permissions
    canTriggerDiscovery: user?.role === 'admin' || user?.role === 'editor',
    canStartScans: user?.role === 'admin' || user?.role === 'editor',
    canEditIPConfig: user?.role === 'admin' || user?.role === 'editor',
    canManageUsers: user?.role === 'admin',
    canEditChannelEnforcement: user?.role === 'admin' || user?.role === 'legal',

    // View permissions
    canViewCosts: user?.role === 'admin' || user?.role === 'editor' || user?.role === 'read', // Hide from clients
    canViewQuota: user?.role === 'admin' || user?.role === 'editor' || user?.role === 'read', // Hide from clients
    canViewAdminMetrics: user?.role === 'admin' || user?.role === 'editor' || user?.role === 'read', // Hide from clients

    // User info
    user,
  }
}
