/**
 * auth.js — Role resolution utility for admin dashboard.
 *
 * Calls /api/admin/rbac/me with the user's Supabase email to determine role
 * and department. Results are cached in sessionStorage for the duration of the
 * browser session to avoid repeated round-trips.
 */

import { apiFetch } from './api';

const CACHE_KEY = 'admin_role';

/**
 * Fetch and cache the current user's role from the backend.
 *
 * @param {import('@supabase/supabase-js').Session} session — Supabase session object
 * @param {boolean} [force=false] — bypass cache and re-fetch
 * @returns {Promise<{role: string|null, email: string|null, department_id: number|null,
 *                    department_name: string|null, department_slug: string|null,
 *                    full_name: string|null, pending_counts: object}>}
 */
export async function getRoleFromSession(session, force = false) {
  if (!session?.user?.email) {
    return { role: null, email: null, department_id: null, department_name: null,
             department_slug: null, full_name: null, pending_counts: {} };
  }

  const email = session.user.email.toLowerCase().trim();

  if (!force) {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed.email === email) return parsed;
      } catch {
        // ignore bad cache
      }
    }
  }

  try {
    const data = await apiFetch('/api/admin/rbac/me', {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': email,
      },
    });

    const result = {
      role: data.role || null,
      email: data.email || email,
      department_id: data.department_id || null,
      department_name: data.department_name || null,
      department_slug: data.department_slug || null,
      institute_name: data.institute_name || null,
      full_name: data.full_name || null,
      pending_counts: data.pending_counts || {},
    };

    sessionStorage.setItem(CACHE_KEY, JSON.stringify(result));
    return result;
  } catch {
    return { role: null, email, department_id: null, department_name: null,
             department_slug: null, full_name: null, pending_counts: {} };
  }
}

/**
 * Clear the cached role from sessionStorage (e.g., on logout).
 */
export function clearRoleCache() {
  sessionStorage.removeItem(CACHE_KEY);
}

/**
 * Return true if the given role is a super_admin.
 * @param {string|null} role
 */
export function isSuperAdmin(role) {
  return role === 'super_admin';
}

/**
 * Return true if the given role has any admin access.
 * @param {string|null} role
 */
export function isAnyAdmin(role) {
  return role === 'super_admin' || role === 'dept_admin';
}
