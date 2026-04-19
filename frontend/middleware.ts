import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'
import { checkRateLimit } from '@/lib/rate-limit'
import { logError } from '@/lib/logger'

/**
 * Middleware for session persistence, auth stability, and rate limiting.
 * Ensures the user's session is refreshed and protects APIs from abuse.
 */
export async function middleware(request: NextRequest) {
  // 1. Rate Limiting & Security Protection (Distributed Redis)
  const ip = request.ip || 'anonymous';
  if (request.nextUrl.pathname.startsWith('/api')) {
    // 1. CSRF Protection for mutations
    const method = request.method;
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const origin = request.headers.get('origin');
      const host = request.headers.get('host');
      if (origin && !origin.includes(host || '')) {
        return NextResponse.json({ error: 'CSRF Forbidden' }, { status: 403 });
      }
    }

    // 2. Rate Limiting Protection (Distributed Redis)
    const { success, limit, remaining, reset } = await checkRateLimit(ip);
    
    if (!success) {
      return NextResponse.json(
        { error: 'Too many requests', limit, remaining, reset },
        { 
          status: 429,
          headers: {
            'X-RateLimit-Limit': limit.toString(),
            'X-RateLimit-Remaining': remaining.toString(),
            'X-RateLimit-Reset': reset.toString(),
          }
        }
      );
    }
  }

  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            request.cookies.set(name, value)
          )
          response = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  try {
    // This will refresh session if expired - required for Server Components
    const { data: { user } } = await supabase.auth.getUser()

    // 2. Auth Protection for sensitive routes
    const protectedPaths = ['/chat', '/dashboard', '/progress', '/quiz', '/results', '/todos', '/upload', '/admin'];
    const isProtectedPath = protectedPaths.some(path => request.nextUrl.pathname.startsWith(path));

    if (isProtectedPath && !user) {
      const url = request.nextUrl.clone();
      url.pathname = '/auth/login';
      url.searchParams.set('redirectedFrom', request.nextUrl.pathname);
      return NextResponse.redirect(url);
    }
  } catch (error) {
    logError(error, "MIDDLEWARE_AUTH");
  }

  return response
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - Public assets (svg, png, etc.)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
