import React, { useState, useEffect } from 'react';
import './StatePane.css';
import html2pdf from 'html2pdf.js';
import { DataTab } from './DataTab';
import DocumentTab from './DocumentTab';

const StatePane = ({ state, documentText, onUpdateField, lastPatchedFields = [] }) => {
  const [activeTab, setActiveTab] = useState('data');
  const [hasAutoDownloaded, setHasAutoDownloaded] = useState(false);

  useEffect(() => {
    if (state?.status === 'ready_for_review') {
      setActiveTab('document');
    }
  }, [state?.status]);

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
          <DataTab 
            state={state} 
            onUpdateField={onUpdateField} 
            lastPatchedFields={lastPatchedFields} 
            handleDownload={handleDownload} 
          />
        )}

        {activeTab === 'document' && (
          <DocumentTab 
            documentText={documentText} 
            handleDownload={handleDownload} 
          />
        )}
      </div>
    </div>
  );
};

export default StatePane;
