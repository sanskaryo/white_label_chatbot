export function formatCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return new Intl.NumberFormat('en-IN').format(value);
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('en-IN', { maximumFractionDigits: digits });
}

export function formatShortDay(dayText) {
  if (!dayText) return '';
  const d = new Date(dayText);
  if (isNaN(d.getTime())) return dayText.slice(5);
  return d.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function parseAnswer(raw) {
  const suggestionMatch = raw.match(/\[SUGGESTIONS:\s*([^\]]+)\]/i);
  const rawSuggestions = suggestionMatch ? suggestionMatch[1].split('|').map((s) => s.trim()).filter(Boolean) : [];
  
  // Deduplicate case-insensitively
  const suggestions = [];
  const seen = new Set();
  for (const s of rawSuggestions) {
    const lowerS = s.toLowerCase();
    if (!seen.has(lowerS)) {
      seen.add(lowerS);
      suggestions.push(s);
    }
  }

  const body = raw.replace(/\[SUGGESTIONS:[^\]]*\]/gi, '').trim();

  const lines = body.split(/\n/);
  const htmlLines = [];
  let inList = false;

  const inlineFormat = (text) =>
    text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/_([^_]+)_/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
      .replace(/(https?:\/\/[^\s<"]+)/g, (url) => body.includes(`](${url})`) ? url : `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`);

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (inList) { htmlLines.push('</ul>'); inList = false; }
      continue;
    }
    if (/^#{1,3}\s/.test(line)) {
      if (inList) { htmlLines.push('</ul>'); inList = false; }
      const level = line.match(/^(#+)/)[1].length;
      const tag = level <= 2 ? 'h3' : 'h4';
      htmlLines.push(`<${tag}>${inlineFormat(line.replace(/^#+\s*/, ''))}</${tag}>`);
      continue;
    }
    if (/^[-*]\s/.test(line)) {
      if (!inList) { htmlLines.push('<ul style="margin-left: 20px; margin-top: 4px; list-style-type: disc;">'); inList = true; }
      htmlLines.push(`<li>${inlineFormat(line.replace(/^[-*]\s*/, ''))}</li>`);
      continue;
    }
    if (inList) { htmlLines.push('</ul>'); inList = false; }
    htmlLines.push(`<p style="margin-bottom: 8px;">${inlineFormat(line)}</p>`);
  }
  if (inList) htmlLines.push('</ul>');

  return { bodyHtml: htmlLines.join('\n'), suggestions };
}
