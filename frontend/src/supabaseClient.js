import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://jfpdteyodpkpdhnoyuas.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

const isLocalBypass =
  !supabaseAnonKey ||
  supabaseAnonKey.includes('placeholder') ||
  supabaseAnonKey.includes('signature');

let supabaseClient;

if (isLocalBypass) {
  console.log('Running in local bypass mode. Supabase calls will be handled locally.');

  const listeners = new Set();

  const notify = (event, session) => {
    for (const listener of listeners) {
      listener(event, session);
    }
  };

  const getSessionFromStorage = () => {
    try {
      const stored = localStorage.getItem('admin_session');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  };

  supabaseClient = {
    auth: {
      getSession: async () => {
        const session = getSessionFromStorage();
        return { data: { session }, error: null };
      },
      signInWithPassword: async ({ email, password }) => {
        const session = {
          access_token: 'local-mock-token-' + Math.random().toString(36).substring(2),
          user: {
            id: 'local-admin-uuid',
            email: email || 'admin@example.com',
            role: 'authenticated',
          },
        };
        localStorage.setItem('admin_session', JSON.stringify(session));
        notify('SIGNED_IN', session);
        return { data: { session }, error: null };
      },
      signOut: async () => {
        localStorage.removeItem('admin_session');
        notify('SIGNED_OUT', null);
        return { error: null };
      },
      onAuthStateChange: (callback) => {
        listeners.add(callback);
        const session = getSessionFromStorage();
        callback('INITIAL_SESSION', session);

        return {
          data: {
            subscription: {
              unsubscribe: () => {
                listeners.delete(callback);
              },
            },
          },
        };
      },
    },
    from: (tableName) => {
      const builder = {
        select: (columns, options) => builder,
        eq: (col, val) => builder,
        neq: (col, val) => builder,
        gt: (col, val) => builder,
        gte: (col, val) => builder,
        lt: (col, val) => builder,
        lte: (col, val) => builder,
        order: (col, options) => builder,
        limit: (num) => builder,
        range: (from, to) => builder,
        single: () => {
          return Promise.resolve({ data: null, error: null, count: 0 });
        },
        then: (onfulfilled) => {
          const result = { data: [], error: null, count: 0 };
          return Promise.resolve(onfulfilled ? onfulfilled(result) : result);
        },
      };
      return builder;
    },
    channel: (name) => {
      const channelObj = {
        on: (event, filter, callback) => channelObj,
        subscribe: () => channelObj,
      };
      return channelObj;
    },
    removeChannel: (channel) => {},
  };
} else {
  supabaseClient = createClient(supabaseUrl, supabaseAnonKey);
}

export const supabase = supabaseClient;
