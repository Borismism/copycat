import { Navigate } from 'react-router-dom'
import { usePermissions } from '../hooks/usePermissions'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: string[]
  requireNotClient?: boolean
}

export default function ProtectedRoute({
  children,
  allowedRoles,
  requireNotClient = false
}: ProtectedRouteProps) {
  const { user, isClient } = usePermissions()

  // If route requires non-client users, redirect clients to dashboard
  if (requireNotClient && isClient) {
    return <Navigate to="/" replace />
  }

  // If specific roles are required, check user role
  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
