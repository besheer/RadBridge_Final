export function draftWarningMessages(payload: unknown): string[] {
  if (!payload || typeof payload !== 'object') return [];
  const rows = (payload as Record<string, unknown>).draft_warnings;
  if (!Array.isArray(rows)) return [];
  const messages = rows.flatMap(row => {
    if (!row || typeof row !== 'object') return [];
    const ar = typeof row.message_ar === 'string' ? row.message_ar.trim() : '';
    const en = typeof row.message_en === 'string' ? row.message_en.trim() : '';
    return ar || en ? [[ar, en].filter(Boolean).join(' / ')] : [];
  });
  return [...new Set(messages)];
}
