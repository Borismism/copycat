// Frozen-time helper for demo mode.
//
// When VITE_DEMO_FROZEN_TIME is set at build time (ISO 8601,
// e.g. "2026-04-16T14:26:00Z"), `now()` returns that instant instead of
// the real clock. Pins the dashboard to a fixed moment so the site can
// serve as a static-looking demo.
//
// Unset the env var and rebuild to return to normal behavior.

const FROZEN_ISO = (import.meta.env.VITE_DEMO_FROZEN_TIME as string | undefined)?.trim() || ''
const FROZEN_DATE = FROZEN_ISO ? new Date(FROZEN_ISO) : null

export function now(): Date {
  return FROZEN_DATE ? new Date(FROZEN_DATE.getTime()) : new Date()
}

export function nowMs(): number {
  return FROZEN_DATE ? FROZEN_DATE.getTime() : Date.now()
}

export const isFrozen = FROZEN_DATE !== null
