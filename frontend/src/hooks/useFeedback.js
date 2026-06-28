import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api';
import { supabase } from '../supabaseClient';

export function useFeedback() {
  const [flagged, setFlagged] = useState([]);
  const [negativeFeedback, setNegativeFeedback] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFeedback = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Flagged Responses from API
      const flaggedData = await apiFetch('/api/admin/flagged-responses?status=pending&limit=100', {
        headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' }
      });
      setFlagged(flaggedData.items || []);

      // 2. Fetch Negative Feedback from Supabase
      if (supabase) {
        const { data: fData, error: fErr } = await supabase
          .from('feedback')
          .select('*, chats(question, answer)')
          .eq('rating', -1)
          .order('submitted_at', { ascending: false })
          .limit(50);
          
        if (fErr) throw fErr;
        setNegativeFeedback(fData || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFeedback();
  }, [fetchFeedback]);

  const approveFlagged = async (id) => {
    await apiFetch(`/api/admin/flagged-responses/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' },
      body: JSON.stringify({ admin_note: 'Approved from operations center.' }),
    });
    fetchFeedback();
  };

  const rejectFlagged = async (id) => {
    await apiFetch(`/api/admin/flagged-responses/${id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' },
      body: JSON.stringify({ admin_note: 'Rejected from operations center.' }),
    });
    fetchFeedback();
  };

  const deleteNegativeFeedback = async (id) => {
    // Optimistically remove from UI first
    setNegativeFeedback(prev => prev.filter(n => n.id !== id));
    if (supabase) {
      await supabase.from('feedback').delete().eq('id', id);
    }
  };

  return { flagged, negativeFeedback, loading, error, refetch: fetchFeedback, approveFlagged, rejectFlagged, deleteNegativeFeedback };
}
