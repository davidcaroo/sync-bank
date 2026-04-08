import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

export const supabase = isSupabaseConfigured
	? createClient(supabaseUrl, supabaseAnonKey)
	: null

const FALLBACK_USER_NAME = import.meta.env.VITE_SUPABASE_USER_NAME || 'Auxiliar Contable'

export async function getSupabaseUserName() {
	if (!isSupabaseConfigured || !supabase) {
		return FALLBACK_USER_NAME
	}

	try {
		const { data } = await supabase.auth.getUser()
		const user = data?.user
		const metadataName = user?.user_metadata?.full_name || user?.user_metadata?.name
		const emailAlias = user?.email ? user.email.split('@')[0] : null

		return metadataName || emailAlias || FALLBACK_USER_NAME
	} catch {
		return FALLBACK_USER_NAME
	}
}
