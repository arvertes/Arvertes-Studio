import { createClient } from "@supabase/supabase-js";

export function createStudioAuth(config) {
  return createClient(config.supabaseUrl, config.supabaseKey, {
    auth: { flowType: "pkce", storage: sessionStorage, persistSession: true, autoRefreshToken: true },
  }).auth;
}
