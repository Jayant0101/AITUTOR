import { createClient } from '@/lib/supabase/server'

/**
 * Server-side utility to get the current authenticated user.
 * Reliable for use in Server Components and API routes.
 */
export async function getUser() {
  const supabase = await createClient()
  const { data, error } = await supabase.auth.getUser()

  if (error || !data.user) {
    return null
  }

  return data.user
}
