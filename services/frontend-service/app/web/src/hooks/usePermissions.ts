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

    // Read: View-only
    isReadOnly: user?.role === 'read',

    // Role-specific permissions
    canTriggerDiscovery: user?.role === 'admin' || user?.role === 'editor',
    canStartScans: user?.role === 'admin' || user?.role === 'editor',
    canEditIPConfig: user?.role === 'admin' || user?.role === 'editor',
    canManageUsers: user?.role === 'admin',
    canEditChannelEnforcement: user?.role === 'admin' || user?.role === 'legal',

    // User info
    user,
  }
}
