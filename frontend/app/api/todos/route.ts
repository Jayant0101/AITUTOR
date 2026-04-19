import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { revalidatePath } from 'next/cache'
import { logError, logInfo } from '@/lib/logger'

/**
 * API route for Todos CRUD.
 * Implements strict field selection and multi-user safety.
 */
export async function GET() {
  try {
    const supabase = await createClient()
    
    // Strict field selection and ordering
    const { data, error } = await supabase
      .from('todos')
      .select('id, name, is_completed, created_at')
      .order('created_at', { ascending: false })

    if (error) throw error;

    return NextResponse.json(data)
  } catch (error) {
    logError(error, "TODOS_GET");
    return NextResponse.json({ error: "Failed to fetch todos" }, { status: 500 })
  }
}

export async function POST(request: Request) {
  try {
    const supabase = await createClient()
    const { name } = await request.json()

    // Verify auth session for safety
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    logInfo(`Creating todo for user ${user.id}`, "TODOS_POST");

    // Explicitly set user_id for RLS and multi-user safety
    const { data, error } = await supabase
      .from('todos')
      .insert([{ name, user_id: user.id }])
      .select('id, name, is_completed, created_at')
      .single()

    if (error) throw error;

    // Invalidate cache for the todos page
    revalidatePath('/todos')

    return NextResponse.json(data)
  } catch (error) {
    logError(error, "TODOS_POST");
    return NextResponse.json({ error: "Failed to create todo" }, { status: 500 })
  }
}
