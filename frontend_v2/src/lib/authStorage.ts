// Plain (non-React) auth storage so both the AuthProvider and the bare
// `api.ts` request helper can read/write the same session without a
// circular dependency on React context.

import type { Role, LoginResponse } from '../types/api';

export interface AuthUser {
  user_id: string;
  username: string;
  display_name: string;
  role: Role;
}

export interface StoredAuth {
  token: string;
  user: AuthUser;
}

const STORAGE_KEY = 'agentify_auth';

/** Dispatched on `window` when a request comes back 401 — the token has
 * expired or was revoked server-side. `AuthProvider` listens for this to
 * clear its state so `RequireAuth` redirects to `/login`. */
export const AUTH_EXPIRED_EVENT = 'agentify-auth-expired';

export function readStoredAuth(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredAuth) : null;
  } catch {
    return null;
  }
}

export function writeStoredAuth(response: LoginResponse): StoredAuth {
  const auth: StoredAuth = {
    token: response.access_token,
    user: {
      user_id: response.user_id,
      username: response.username,
      display_name: response.display_name,
      role: response.role,
    },
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
  return auth;
}

export function clearStoredAuth(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function getToken(): string | null {
  return readStoredAuth()?.token ?? null;
}
