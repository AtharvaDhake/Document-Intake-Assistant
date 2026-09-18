const API_BASE = '/api';

export const createSession = async () => {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
};

export const getSession = async (id) => {
  const res = await fetch(`${API_BASE}/sessions/${id}`);
  if (!res.ok) throw new Error('Failed to get session');
  return res.json();
};

export const sendMessage = async (id, message) => {
  const res = await fetch(`${API_BASE}/sessions/${id}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });
  if (!res.ok) throw new Error('Failed to send message');
  return res.json();
};

export const getDocument = async (id) => {
  const res = await fetch(`${API_BASE}/sessions/${id}/document`);
  if (!res.ok) throw new Error('Failed to get document');
  return res.json();
};

export const updateField = async (id, fieldName, value) => {
  const res = await fetch(`${API_BASE}/sessions/${id}/fields/${fieldName}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value })
  });
  if (!res.ok) throw new Error('Failed to update field');
  return res.json();
};
