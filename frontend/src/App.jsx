import React, { useState, useEffect } from 'react';
import ChatPane from './components/ChatPane';
import StatePane from './components/StatePane';
import { createSession, sendMessage, getDocument, updateField, getSession } from './api';
import './App.css';

function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [documentText, setDocumentText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState(null);
  const [lastPatchedFields, setLastPatchedFields] = useState([]);

  useEffect(() => {
    const initSession = async () => {
      try {
        const savedId = localStorage.getItem('session_id');
        if (savedId) {
          try {
            const data = await getSession(savedId);
            if (data) {
              setSession({
                session_id: data.session_id,
                state: data,
                conversation_log: data.conversation_log || []
              });
              const docData = await getDocument(data.session_id);
              setDocumentText(docData.document_text);
              setLoading(false);
              return;
            }
          } catch (e) {
            console.warn("Failed to restore session, starting new one");
            localStorage.removeItem('session_id');
          }
        }
        
        const data = await createSession();
        localStorage.setItem('session_id', data.session_id);
        setSession({
          session_id: data.session_id,
          state: data.state,
          conversation_log: [{ role: 'assistant', content: data.assistant_message }]
        });
      } catch (err) {
        console.error("Failed to initialize session", err);
        setError("Failed to initialize session. Please check your connection.");
      } finally {
        setLoading(false);
      }
    };
    initSession();
  }, []);

  const handleReset = async () => {
    // 1. Download document if it exists
    if (documentText) {
      const blob = new Blob([documentText], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'personal-wishes-document.txt';
      a.click();
      URL.revokeObjectURL(url);
    }

    // 2. Clear state and start new session
    setLoading(true);
    try {
      localStorage.removeItem('session_id');
      const data = await createSession();
      localStorage.setItem('session_id', data.session_id);
      setSession({
        session_id: data.session_id,
        state: data.state,
        conversation_log: [{ role: 'assistant', content: data.assistant_message }]
      });
      setDocumentText("");
      setLastPatchedFields([]);
      setError(null);
    } catch (err) {
      console.error("Failed to reset session", err);
      setError("Failed to start a new session.");
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (message) => {
    if (!session) return;
    setError(null);
    setLastPatchedFields([]);
    
    // Optimistic update for user message
    const newMessage = { role: 'user', content: message, timestamp: new Date().toISOString() };
    setSession(prev => ({
      ...prev,
      conversation_log: [...prev.conversation_log, newMessage]
    }));
    setIsTyping(true);

    try {
      const data = await sendMessage(session.session_id, message);
      
      const patchedFields = (data.patch_applied || []).map(p => p.field);
      setLastPatchedFields(patchedFields);

      // Fetch document if state changed BEFORE updating session to prevent stale text download
      let newDocText = documentText;
      if (data.state) {
        const docData = await getDocument(session.session_id);
        newDocText = docData.document_text;
        setDocumentText(newDocText);
      }

      setSession(prev => ({
        ...prev,
        state: data.state,
        conversation_log: [...prev.conversation_log, { role: 'assistant', content: data.assistant_message }]
      }));
    } catch (err) {
      console.error("Failed to send message", err);
      setError("Failed to send message. Please try again.");
      // Revert optimistic update
      setSession(prev => ({
        ...prev,
        conversation_log: prev.conversation_log.slice(0, -1)
      }));
    } finally {
      setIsTyping(false);
    }
  };

  const handleUpdateField = async (fieldName, value) => {
    if (!session) return;
    setError(null);
    setLastPatchedFields([fieldName]);
    
    try {
      const data = await updateField(session.session_id, fieldName, value);
      
      const docData = await getDocument(session.session_id);
      setDocumentText(docData.document_text);
      
      setSession(prev => ({
        ...prev,
        state: data.state,
        conversation_log: [...prev.conversation_log, { role: 'assistant', content: data.assistant_message }]
      }));
    } catch (err) {
      console.error("Failed to update field", err);
      setError(`Failed to update ${fieldName}. Please try again.`);
    }
  };

  if (loading) {
    return <div className="loading-container">Initializing Assistant...</div>;
  }

  return (
    <div className="app-container">
      {error && (
        <div className="error-banner" style={{ background: '#ff4444', color: 'white', padding: '10px', textAlign: 'center' }}>
          ⚠️ {error} <button onClick={() => setError(null)} style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer', float: 'right' }}>✕</button>
        </div>
      )}
      <div className="disclaimer-banner">
        This is a fictional example document for demonstration purposes only. It is not legal advice and has no legal effect.
      </div>
      <div className="panes-container">
        <ChatPane messages={session?.conversation_log || []} onSendMessage={handleSendMessage} isTyping={isTyping} onReset={handleReset} />
        <StatePane 
          state={session?.state} 
          documentText={documentText}
          onUpdateField={handleUpdateField}
          lastPatchedFields={lastPatchedFields}
        />
      </div>
    </div>
  );
}

export default App;

