// WHAT DOES THIS FILE DO: Formatting utilities for numbers, dates, and markdown rendering

// =========== FUNCTIONS ===========

// ROLE: Format number with locale-specific thousands separator
export function formatCount(value) {
  // Return formatted integer or dash if invalid

  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return new Intl.NumberFormat('en-IN').format(value);
}


// ROLE: Format decimal as percentage string
export function formatPercent(value, digits = 1) {
  // Return percentage string or dash if invalid

  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${(value * 100).toFixed(digits)}%`;
}


// ROLE: Format number with locale and decimal places
export function formatNumber(value, digits = 2) {
  // Return formatted number or dash if invalid

  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('en-IN', { maximumFractionDigits: digits });
}


// ROLE: Format date string to short day format
export function formatShortDay(dayText) {
  // Return short date like "Mon, Jan 15" or original text if invalid

  if (!dayText) return '';
  const d = new Date(dayText);
  if (isNaN(d.getTime())) return dayText.slice(5);
  return d.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });
}


// ROLE: Parse markdown answer into HTML and extract suggestions
export function parseAnswer(raw) {
  // Return object with HTML body and suggestion list

  // FLOW-1: Extract suggestions from [SUGGESTIONS: ...] block
  const suggestionMatch = raw.match(/\[SUGGESTIONS:\s*([^\]]+)\]/i);
  const rawSuggestions = suggestionMatch ? suggestionMatch[1].split('|').map((s) => s.trim()).filter(Boolean) : [];

  // FLOW-2: Deduplicate suggestions case-insensitively
  const suggestions = [];
  const seen = new Set();
  for (const s of rawSuggestions) {
    const lowerS = s.toLowerCase();
    if (!seen.has(lowerS)) {
      seen.add(lowerS);
      suggestions.push(s);
    }
  }

  // FLOW-3: Remove suggestions block from body
  const body = raw.replace(/\[SUGGESTIONS:[^\]]*\]/gi, '').trim();

  // FLOW-4: Parse lines and convert markdown to HTML
  const lines = body.split(/\n/);
  const htmlLines = [];
  let inList = false;

  // FLOW-5: Define inline markdown formatter
  const inlineFormat = (text) =>
    text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/_([^_]+)_/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
      .replace(/(https?:\/\/[^\s<"]+)/g, (url) => body.includes(`](${url})`) ? url : `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`);

  // FLOW-6: Process each line for block-level elements
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (inList) { htmlLines.push('</ul>'); inList = false; }
      continue;
    }

    // FLOW-7: Handle headings (# ## ###)
    if (/^#{1,3}\s/.test(line)) {
      if (inList) { htmlLines.push('</ul>'); inList = false; }
      const level = line.match(/^(#+)/)[1].length;
      const tag = level <= 2 ? 'h3' : 'h4';
      htmlLines.push(`<${tag}>${inlineFormat(line.replace(/^#+\s*/, ''))}</${tag}>`);
      continue;
    }

    // FLOW-8: Handle list items (- or *)
    if (/^[-*]\s/.test(line)) {
      if (!inList) { htmlLines.push('<ul style="margin-left: 20px; margin-top: 4px; list-style-type: disc;">'); inList = true; }
      htmlLines.push(`<li>${inlineFormat(line.replace(/^[-*]\s*/, ''))}</li>`);
      continue;
    }

    // FLOW-9: Handle regular paragraphs
    if (inList) { htmlLines.push('</ul>'); inList = false; }
    htmlLines.push(`<p style="margin-bottom: 8px;">${inlineFormat(line)}</p>`);
  }

  // FLOW-10: Close any open list at end
  if (inList) htmlLines.push('</ul>');

  return { bodyHtml: htmlLines.join('\n'), suggestions };
}

// =========== FUNCTIONS ===========
