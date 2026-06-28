import { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { Settings, Save, RotateCcw, ShieldAlert, Info } from 'lucide-react';

export function SystemPromptTab() {
  const [prompt, setPrompt] = useState('');
  const [defaultPrompt, setDefaultPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null); // { type: 'success' | 'error', text: string }

  const fetchPrompt = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await apiFetch('/api/admin/settings/system-prompt');
      setPrompt(data.system_prompt || '');
      setDefaultPrompt(data.default_prompt || '');
    } catch (err) {
      setMessage({ type: 'error', text: `Failed to load system prompt: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrompt();
  }, []);

  const handleSave = async () => {
    if (!prompt.trim()) {
      setMessage({ type: 'error', text: 'System prompt cannot be empty.' });
      return;
    }

    const missingRules = [];
    const lowerPrompt = prompt.toLowerCase();
    if (!lowerPrompt.includes('jailbreak')) {
      missingRules.push('Jailbreak prevention rules ("JAILBREAK")');
    }
    if (!lowerPrompt.includes('security')) {
      missingRules.push('Security guidelines ("SECURITY")');
    }
    if (!lowerPrompt.includes('functioning')) {
      missingRules.push('System functioning limits ("functioning")');
    }
    if (!lowerPrompt.includes('[suggestions:')) {
      missingRules.push('Quick follow-up actions pattern ("[SUGGESTIONS:")');
    }

    if (missingRules.length > 0) {
      const warningMsg = `Warning: The system prompt is missing these critical guidelines or formatting directives:\n\n` +
        missingRules.map(r => `• ${r}`).join('\n') +
        `\n\nSaving this prompt may degrade chatbot safety or break the layout. Do you want to save anyway?`;
      if (!window.confirm(warningMsg)) {
        return;
      }
    }

    setSaving(true);
    setMessage(null);
    try {
      const data = await apiFetch('/api/admin/settings/system-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: prompt }),
      });
      setPrompt(data.system_prompt);
      setMessage({ type: 'success', text: 'System prompt saved successfully! The chatbot will use the new instructions immediately.' });
    } catch (err) {
      setMessage({ type: 'error', text: `Failed to save system prompt: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const confirmReset = window.confirm(
      'Are you sure you want to reset the system prompt to the default counselor persona? Any customized instructions will be overwritten.'
    );
    if (confirmReset) {
      setPrompt(defaultPrompt);
      setMessage({ type: 'success', text: 'Prompt reset to default instructions in editor. Click "Save Changes" to apply.' });
    }
  };

  if (loading) {
    return (
      <div className="fade-in tab-content-inner" style={{ padding: '24px', textAlign: 'center' }}>
        <p className="muted" style={{ fontSize: '15px' }}>Loading system prompt settings...</p>
      </div>
    );
  }

  return (
    <div className="fade-in tab-content-inner dashboard-main-grid" style={{ gridTemplateColumns: '1.8fr 1.2fr', gap: '20px' }}>
      
      {/* LEFT: Prompt Editor */}
      <div className="panel compact-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel-header" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Settings size={16} style={{ color: 'var(--teal)' }} /> System Prompt Persona Editor
          </h3>
          <span style={{ 
            fontSize: '12px', 
            padding: '2px 8px', 
            background: 'var(--paper-muted)', 
            borderRadius: '4px',
            color: 'var(--ink)',
            opacity: 0.8
          }}>
            {prompt.length} characters
          </span>
        </div>

        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
          <p className="muted" style={{ fontSize: '13px', lineHeight: '1.5' }}>
            Modify the default behavior, tone, response format, structured info, and security constraints of the virtual counselor. This prompt is evaluated on every LLM generation.
          </p>

          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="admin-input"
            rows={18}
            style={{
              width: '100%',
              fontSize: '13.5px',
              fontFamily: 'monospace',
              lineHeight: '1.6',
              padding: '12px',
              borderRadius: '6px',
              border: '1px solid var(--line)',
              background: 'var(--paper)',
              color: 'var(--ink)',
              resize: 'vertical'
            }}
            placeholder="Type your system prompt here..."
          />

          {message && (
            <div style={{
              padding: '12px',
              borderRadius: '6px',
              fontSize: '13px',
              lineHeight: '1.4',
              background: message.type === 'error' ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)',
              border: message.type === 'error' ? '1px solid rgba(239, 68, 68, 0.2)' : '1px solid rgba(16, 185, 129, 0.2)',
              color: message.type === 'error' ? 'var(--danger)' : 'var(--moss)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px'
            }}>
              {message.type === 'error' ? <ShieldAlert size={16} style={{ flexShrink: 0, marginTop: '2px' }} /> : <Info size={16} style={{ flexShrink: 0, marginTop: '2px' }} />}
              <span>{message.text}</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-dash"
              style={{
                background: 'var(--moss)',
                color: '#fff',
                padding: '10px 20px',
                fontSize: '13.5px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: saving ? 'not-allowed' : 'pointer'
              }}
            >
              <Save size={15} /> {saving ? 'Saving Changes...' : 'Save System Prompt'}
            </button>
            <button
              onClick={handleReset}
              className="btn-dash"
              style={{
                background: 'transparent',
                border: '1px solid var(--danger)',
                color: 'var(--danger)',
                padding: '10px 20px',
                fontSize: '13.5px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <RotateCcw size={15} /> Reset to Default
            </button>
          </div>
        </div>
      </div>

      {/* RIGHT: Guidelines Panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div className="panel compact-panel">
          <div className="panel-header" style={{ padding: '16px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Info size={16} style={{ color: 'var(--accent)' }} /> Prompt Rules & Guidelines
            </h3>
          </div>
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13.5px', lineHeight: '1.6', color: 'var(--ink)' }}>
            <div>
              <strong style={{ color: 'var(--teal)', display: 'block', marginBottom: '4px' }}>1. Tone & Persona</strong>
              <p className="muted" style={{ margin: 0 }}>
                Maintain a warm, helpful persona — a virtual admission counselor. Ensure it responds in clear English; local language is acceptable if the query is in that language.
              </p>
            </div>
            <hr style={{ border: 'none', borderTop: '1px solid var(--line)', margin: 0 }} />
            <div>
              <strong style={{ color: 'var(--accent)', display: 'block', marginBottom: '4px' }}>2. Output Formatting</strong>
              <p className="muted" style={{ margin: 0 }}>
                Direct the model to output responses in bullet points (10-20 words per point) and bold key metrics, rather than dense blocks of text.
              </p>
            </div>
            <hr style={{ border: 'none', borderTop: '1px solid var(--line)', margin: 0 }} />
            <div>
              <strong style={{ color: 'var(--danger)', display: 'block', marginBottom: '4px' }}>3. Maximum Security</strong>
              <p className="muted" style={{ margin: 0 }}>
                Instruct the LLM to strictly reject jailbreak or roleplay instructions. Never reveal internal prompts or database details if queried.
              </p>
            </div>
            <hr style={{ border: 'none', borderTop: '1px solid var(--line)', margin: 0 }} />
            <div>
              <strong style={{ color: 'var(--moss)', display: 'block', marginBottom: '4px' }}>4. Contextual Suggestions</strong>
              <p className="muted" style={{ margin: 0 }}>
                Every single reply must append quick follow-up buttons at the end matching the exact pattern: <code>[SUGGESTIONS: Action 1 | Action 2]</code>.
              </p>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
