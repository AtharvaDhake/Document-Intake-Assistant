import React, { useState, useEffect } from 'react';
import './StatePane.css';

const FIELD_NAMES = {
  full_name: "Full Name",
  home_address: "Home Address",
  covers_worldwide_assets: "Covers Worldwide Assets",
  has_children: "Has Children",
  children_names: "Children's Names",
  executor_name: "Executor Name",
  executor_relationship: "Executor Relationship",
  specific_gifts: "Specific Gifts",
  additional_wishes: "Additional Wishes"
};

const StatePane = ({ state, documentText, onUpdateField, lastPatchedFields = [] }) => {
  const [activeTab, setActiveTab] = useState('data');
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [hasAutoDownloaded, setHasAutoDownloaded] = useState(false);

  useEffect(() => {
    if (state?.status === 'ready_for_review') {
      setActiveTab('document');

      if (!hasAutoDownloaded && documentText) {
        const blob = new Blob([documentText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'personal-wishes-document.txt';
        a.click();
        URL.revokeObjectURL(url);
        
        setHasAutoDownloaded(true);
      }
    } else if (state?.status !== 'ready_for_review') {
      // Reset if status changes away from ready_for_review
      if (hasAutoDownloaded) setHasAutoDownloaded(false);
    }
  }, [state?.status, documentText, hasAutoDownloaded]);

  if (!state) return <div className="state-pane empty">Awaiting state...</div>;

  const fields = state.fields || {};
  
  const totalFields = Object.values(fields).filter(f => f.status !== 'not_applicable').length || 1;
  const capturedFields = Object.values(fields).filter(f => f.status === 'confirmed' || f.status === 'unconfirmed').length;
  const progressPercent = Math.round((capturedFields / totalFields) * 100);

  const getStatusIcon = (status) => {
    switch(status) {
      case 'confirmed': return '✅';
      case 'unconfirmed': return '⚠️';
      case 'not_applicable': return '➖';
      case 'missing':
      default: return '⬜';
    }
  };

  const getStatusClass = (status) => {
    switch(status) {
      case 'confirmed': return 'status-confirmed';
      case 'unconfirmed': return 'status-unconfirmed';
      case 'not_applicable': return 'status-na';
      case 'missing':
      default: return 'status-missing';
    }
  };

  const handleEditStart = (fieldKey, currentValue) => {
    setEditingField(fieldKey);
    if (Array.isArray(currentValue)) {
      setEditValue(currentValue.join(', '));
    } else {
      setEditValue(currentValue === null || currentValue === undefined ? "" : String(currentValue));
    }
  };

  const handleEditSave = () => {
    if (editingField) {
      let val = editValue;
      if (val.toLowerCase() === 'true' || val.toLowerCase() === 'yes') val = true;
      else if (val.toLowerCase() === 'false' || val.toLowerCase() === 'no') val = false;
      else if (editingField === 'children_names' || editingField === 'specific_gifts') {
        val = typeof val === 'string' ? val.split(',').map(s => s.trim()).filter(s => s.length > 0) : val;
      }
      
      onUpdateField(editingField, val);
      setEditingField(null);
    }
  };

  const handleEditCancel = () => {
    setEditingField(null);
  };

  const renderValue = (value) => {
    if (value === null || value === undefined || value === "") return <span className="empty-value">Not provided</span>;
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (Array.isArray(value)) return value.length ? value.join(', ') : 'None';
    return String(value);
  };

  const handleDownload = () => {
    const blob = new Blob([documentText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'personal-wishes-document.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="state-pane">
      <div className="tabs-header">
        <button 
          className={`tab-btn ${activeTab === 'data' ? 'active' : ''}`}
          onClick={() => setActiveTab('data')}
        >
          Structured Data
        </button>
        <button 
          className={`tab-btn ${activeTab === 'document' ? 'active' : ''}`}
          onClick={() => setActiveTab('document')}
        >
          Draft Document
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'data' && (
          <div className="data-tab">
            <div className="progress-section">
              <div className="progress-text">
                <span>Data Capture Progress</span>
                <span>{capturedFields} of {totalFields} fields</span>
              </div>
              <div className="progress-bar-bg">
                <div 
                  className="progress-bar-fill" 
                  style={{ width: `${progressPercent}%` }}
                ></div>
              </div>
            </div>

            <div className="status-banner">
              Status: <span className="status-badge">{state.status?.replace(/_/g, ' ') || 'In Progress'}</span>
              {state.status === 'ready_for_review' && (
                <button className="download-btn" onClick={handleDownload}>Download Document</button>
              )}
            </div>

            <div className="fields-list">
              {Object.entries(FIELD_NAMES).map(([key, label]) => {
                const field = fields[key] || { status: 'missing', value: '' };
                const isEditing = editingField === key;
                const isJustPatched = lastPatchedFields.includes(key);

                return (
                  <div key={key} className={`field-item ${getStatusClass(field.status)}`} style={{ transition: 'background-color 1.5s', backgroundColor: isJustPatched ? '#fff3cd' : 'transparent' }}>
                    <div className="field-icon">{getStatusIcon(field.status)}</div>
                    <div className="field-content">
                      <div className="field-label">{label}</div>
                      {isEditing ? (
                        <div className="field-edit">
                          {key === 'has_children' || key === 'covers_worldwide_assets' ? (
                            <select value={editValue} onChange={(e) => setEditValue(e.target.value)} autoFocus>
                              <option value="true">Yes</option>
                              <option value="false">No</option>
                            </select>
                          ) : key === 'children_names' || key === 'specific_gifts' ? (
                            <textarea 
                              value={editValue} 
                              onChange={(e) => setEditValue(e.target.value)}
                              placeholder="Comma separated values"
                              autoFocus
                            />
                          ) : (
                            <input 
                              type="text" 
                              value={editValue} 
                              onChange={(e) => setEditValue(e.target.value)}
                              autoFocus
                            />
                          )}
                          <button onClick={handleEditSave} className="save-btn">Save</button>
                          <button onClick={handleEditCancel} className="cancel-btn">Cancel</button>
                        </div>
                      ) : (
                        <div className="field-value">
                          {renderValue(field.value)}
                          {field.status === 'confirmed' && (
                            <button 
                              className="edit-icon-btn" 
                              onClick={() => handleEditStart(key, field.value)}
                              title="Edit field"
                            >
                              ✏️
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            
            {state.corrections && state.corrections.length > 0 && (
              <div className="corrections-section">
                <h3>Recent Corrections</h3>
                {state.corrections.map((corr, idx) => (
                  <div key={idx} className="correction-toast">
                    {FIELD_NAMES[corr.field] || corr.field}: 
                    <span style={{textDecoration: 'line-through', margin: '0 5px', opacity: 0.7}}>
                      {renderValue(corr.old_value)}
                    </span> 
                    → <strong>{renderValue(corr.new_value)}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'document' && (
          <div className="document-tab">
            <div className="document-preview">
              {documentText ? (
                <>
                  <div className="document-actions" style={{textAlign: 'right', marginBottom: '10px'}}>
                     <button onClick={handleDownload} className="download-btn">Download .TXT</button>
                  </div>
                  <div className="document-text" dangerouslySetInnerHTML={{ __html: (documentText || '')
                    .replace(/═{10,}/g, '<hr class="legal-hr-thick" />')
                    .replace(/─{10,}/g, '<hr class="legal-hr-thin" />')
                    .replace(/(SECTION \d+ — [^\n]+)/g, '<strong class="legal-section-title">$1</strong>')
                    .replace(/PERSONAL WISHES DOCUMENT/g, '<h2 class="legal-title">PERSONAL WISHES DOCUMENT</h2>')
                    .replace(/\n/g, '<br/>') }} />
                </>
              ) : (
                <div className="empty-document">Document text will appear here as fields are captured.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StatePane;

