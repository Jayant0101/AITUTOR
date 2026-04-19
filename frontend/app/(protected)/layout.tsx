import { redirect } from 'next/navigation'
import { getUser } from '@/lib/auth/getUser'

/**
 * Shared layout for all protected routes.
 * Enforces server-side authentication check before rendering children.
 */
export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getUser()

  if (!user) {
    redirect('/auth/login')
  }

  return <>{children}</>
}
