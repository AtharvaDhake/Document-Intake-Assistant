import React, { useState } from 'react';
import { FieldEditorRow, renderValue } from './FieldEditorRow';

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

const DataTab = ({ state, onUpdateField, lastPatchedFields, handleDownload }) => {
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState("");

  const fields = state.fields || {};
  const totalFields = Object.keys(FIELD_NAMES).length;
  const capturedFields = Object.values(fields).filter(
    f => f.status === 'confirmed' || f.status === 'not_applicable'
  ).length;
  const progressPercent = Math.round((capturedFields / totalFields) * 100);

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

  return (
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
            <FieldEditorRow
              key={key}
              fieldKey={key}
              label={label}
              field={field}
              isEditing={isEditing}
              isJustPatched={isJustPatched}
              editValue={editValue}
              onEditStart={handleEditStart}
              onEditChange={setEditValue}
              onEditSave={handleEditSave}
              onEditCancel={handleEditCancel}
            />
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
  );
};

export { DataTab, FIELD_NAMES };
