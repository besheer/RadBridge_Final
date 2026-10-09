import React from 'react';

export default function DraftWarnings({ messages }: { messages: string[] }) {
  if (!messages.length) return null;
  return (
    <details style={{ padding: '8px 14px', background: '#422006', color: '#fde68a', fontSize: '12px' }}>
      <summary style={{ cursor: 'pointer' }}>تنبيهات المسودة · Draft notices ({messages.length})</summary>
      <p>هذه التنبيهات لا تمنع حفظ المسودة. / These notices do not block saving the draft.</p>
      <ul>{messages.map(message => <li key={message} dir="auto">{message}</li>)}</ul>
    </details>
  );
}
