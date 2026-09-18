import React, { useState, useRef, useEffect } from 'react';
import './ChatPane.css';

const ChatPane = ({ messages, onSendMessage, isTyping, onReset }) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const submitTurn = (e) => {
    e.preventDefault();
    if (inputValue.trim()) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  return (
    <div className="chat-pane">
      <div className="chat-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Document Intake Assistant</h2><button onClick={onReset} className="reset-btn" title="Save Document and Restart Session">Save & Restart</button>
      </div>
      
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message-wrapper ${msg.role}`}>
            <div className={`message-bubble ${msg.role}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="message-wrapper assistant">
            <div className="message-bubble assistant typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={submitTurn}>
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submitTurn(e);
            }
          }}
          placeholder="Type your message here... (Shift+Enter for new line)"
          disabled={isTyping}
          rows={2}
          style={{ resize: 'none', fontFamily: 'inherit', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', width: '100%', boxSizing: 'border-box' }}
        />
        <button type="submit" disabled={isTyping || !inputValue.trim()}>
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatPane;

