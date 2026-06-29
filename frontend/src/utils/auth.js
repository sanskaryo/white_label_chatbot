// WHAT DOES THIS FILE DO: Admin role resolution utility with session caching

// ================== IMPORTS ==================
import { apiFetch } from './api';
// ================== IMPORTS ==================


// =========== VARIABLES : caching ===========
const CACHE_KEY = 'admin_role';
// =========== VARIABLES : caching ===========


// =========== FUNCTIONS ===========

// ROLE: Fetch and cache user role from backend
export async function getRoleFromSession(session, force = false) {
  // Fetch role from /api/admin/rbac/me and cache in sessionStorage

  // FLOW-1: Return default if no session or email
  if (!session?.user?.email) {
    return { role: null, email: null, department_id: null, department_name: null,
             department_slug: null, full_name: null, pending_counts: {} };
  }

  // FLOW-2: Normalize email for matching
  const email = session.user.email.toLowerCase().trim();

  // FLOW-3: Return cached result if force not set and cache hit with same email
  if (!force) {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed.email === email) return parsed;
      } catch {
        // skip bad cache
      }
    }
  }

  // FLOW-4: Fetch role data from backend API
  try {
    const data = await apiFetch('/api/admin/rbac/me', {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': email,
      },
    });

    // FLOW-5: Build result dict with role and department info
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

    // FLOW-6: Cache result in sessionStorage
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(result));
    return result;

  } catch {
    // FLOW-7: Return defaults on API failure
    return { role: null, email, department_id: null, department_name: null,
             department_slug: null, full_name: null, pending_counts: {} };
  }
}


// ROLE: Clear cached role from sessionStorage
export function clearRoleCache() {
  // Remove cached role entry so it reloads on next check

  sessionStorage.removeItem(CACHE_KEY);
}


// ROLE: Check if role is super_admin
export function isSuperAdmin(role) {
  // Return true if role is super_admin

  return role === 'super_admin';
}


// ROLE: Check if role has admin access
export function isAnyAdmin(role) {
  // Return true if role is super_admin or dept_admin

  return role === 'super_admin' || role === 'dept_admin';
}

// =========== FUNCTIONS ===========
