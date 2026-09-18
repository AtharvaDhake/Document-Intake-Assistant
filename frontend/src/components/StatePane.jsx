import React, { useState, useEffect } from 'react';
import './StatePane.css';

import html2pdf from 'html2pdf.js';

const FIELD_NAMES = {
  full_name: "Full Name",
  home_address: "Home Address",
  has_children: "Has Children",
  children_names: "Children's Names",
  executor_name: "Executor Name",
  executor_relationship: "Executor Relationship",
  covers_worldwide_assets: "Covers Worldwide Assets",
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
    }
  }, [state?.status]);

  useEffect(() => {
    if (state?.status === 'ready_for_review' && activeTab === 'document') {
      if (!hasAutoDownloaded && documentText) {
        // Adding a tiny delay guarantees the DOM has painted the element
        setTimeout(() => {
          handleDownload();
          setHasAutoDownloaded(true);
        }, 100);
      }
    } else if (state?.status !== 'ready_for_review') {
      if (hasAutoDownloaded) setHasAutoDownloaded(false);
    }
  }, [state?.status, documentText, activeTab, hasAutoDownloaded]);

  if (!state) return (
    <div className="state-pane" style={{ padding: '20px' }}>
      <div style={{ height: '30px', backgroundColor: '#e0e0e0', borderRadius: '4px', marginBottom: '20px', width: '40%', animation: 'pulse 1.5s infinite' }}></div>
      <div style={{ height: '80px', backgroundColor: '#e0e0e0', borderRadius: '8px', marginBottom: '12px', animation: 'pulse 1.5s infinite' }}></div>
      <div style={{ height: '80px', backgroundColor: '#e0e0e0', borderRadius: '8px', marginBottom: '12px', animation: 'pulse 1.5s infinite' }}></div>
      <div style={{ height: '80px', backgroundColor: '#e0e0e0', borderRadius: '8px', marginBottom: '12px', animation: 'pulse 1.5s infinite' }}></div>
    </div>
  );

  const fields = state.fields || {};
  const totalFields = Object.keys(FIELD_NAMES).length;
  const capturedFields = Object.values(fields).filter(
    f => f.status === 'confirmed' || f.status === 'not_applicable'
  ).length;
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
    const element = document.getElementById('document-preview-content');
    if (!element) return;
    const opt = {
      margin:       0.5,
      filename:     'personal-wishes-document.pdf',
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2 },
      jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save();
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
                <button className="download-btn" onClick={handleDownload}>Download PDF</button>
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
                              onKeyDown={(e) => e.key === 'Enter' && handleEditSave()}
                            />
                          )}
                          <button className="save-btn" onClick={handleEditSave}>Save</button>
                          <button className="cancel-btn" onClick={handleEditCancel}>Cancel</button>
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

            <div className="json-output-section" style={{ marginTop: '32px' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '12px', color: 'var(--text-secondary)' }}>Raw JSON Data</h3>
              <pre style={{
                backgroundColor: '#282c34', 
                color: '#abb2bf', 
                padding: '16px', 
                borderRadius: '8px', 
                overflowX: 'auto',
                fontSize: '0.9rem'
              }}>
                {JSON.stringify(
                  Object.keys(fields).reduce((acc, key) => {
                    if (fields[key].status === 'confirmed' || fields[key].status === 'unconfirmed') {
                      acc[key] = fields[key].value;
                    }
                    return acc;
                  }, {}), 
                  null, 
                  2
                )}
              </pre>
            </div>
          </div>
        )}

        {activeTab === 'document' && (
          <div className="document-tab">
            <div className="document-preview">
              {documentText ? (
                <>
                  <div className="document-actions" style={{textAlign: 'right', marginBottom: '10px', position: 'relative', zIndex: 10}}>
                     <button onClick={handleDownload} className="download-btn">Download PDF</button>
                  </div>
                  <div id="document-preview-content" className="document-text" dangerouslySetInnerHTML={{ __html: documentText.replace(/\n? *═{10,} *\n?/g, '<hr class="legal-hr-thick" />').replace(/\n? *─{10,} *\n?/g, '<hr class="legal-hr-thin" />').replace(/(<hr class="legal-hr-thin" \/>)(SECTION \d+ — [^<]+)(<hr class="legal-hr-thin" \/>)/g, '<div class="legal-section-header">$1<strong class="legal-section-title">$2</strong>$3</div>').replace(/\n/g, '<br/>') }} />
                </>
              ) : (
                <div className="empty-document">Draft will appear here once ready for review.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StatePane;

