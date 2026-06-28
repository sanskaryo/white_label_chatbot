import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../supabaseClient';

export function useSupabaseSessions() {
  const [sessions, setSessions] = useState([]);
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLiveActivity = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (!supabase) throw new Error('Supabase client not initialized');
      
      const { data: s, error: sErr } = await supabase.from('sessions').select('*').order('started_at', { ascending: false }).limit(20);
      if (sErr) throw sErr;
      if (s) setSessions(s);

      const { data: c, error: cErr } = await supabase.from('chats').select('*').order('asked_at', { ascending: false }).limit(20);
      if (cErr) throw cErr;
      if (c) setChats(c);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLiveActivity();
    
    if (!supabase) return;

    const channel = supabase.channel('public:chats')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'chats' }, payload => {
         setChats(prev => [payload.new, ...prev].slice(0, 20));
      })
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'sessions' }, payload => {
         setSessions(prev => [payload.new, ...prev].slice(0, 20));
      })
      .subscribe();
      
    return () => { supabase.removeChannel(channel); };
  }, [fetchLiveActivity]);

  return { sessions, chats, loading, error, refetch: fetchLiveActivity };
}
