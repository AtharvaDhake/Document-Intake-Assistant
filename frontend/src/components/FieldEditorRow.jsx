import React from 'react';

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

const renderValue = (value) => {
  if (value === null || value === undefined || value === "") return <span className="empty-value">Not provided</span>;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'None';
  return String(value);
};

const FieldEditorRow = ({ 
  fieldKey, 
  label, 
  field, 
  isEditing, 
  isJustPatched, 
  editValue, 
  onEditStart, 
  onEditChange, 
  onEditSave, 
  onEditCancel 
}) => {
  return (
    <div className={`field-item ${getStatusClass(field.status)}`} style={{ transition: 'background-color 1.5s', backgroundColor: isJustPatched ? '#fff3cd' : 'transparent' }}>
      <div className="field-icon">{getStatusIcon(field.status)}</div>
      <div className="field-content">
        <div className="field-label">{label}</div>
        {isEditing ? (
          <div className="field-edit">
            {fieldKey === 'has_children' || fieldKey === 'covers_worldwide_assets' ? (
              <select value={editValue} onChange={(e) => onEditChange(e.target.value)} autoFocus>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            ) : fieldKey === 'children_names' || fieldKey === 'specific_gifts' ? (
              <textarea 
                value={editValue} 
                onChange={(e) => onEditChange(e.target.value)}
                placeholder="Comma separated values"
                autoFocus
              />
            ) : (
              <input 
                type="text" 
                value={editValue} 
                onChange={(e) => onEditChange(e.target.value)}
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && onEditSave()}
              />
            )}
            <button className="save-btn" onClick={onEditSave}>Save</button>
            <button className="cancel-btn" onClick={onEditCancel}>Cancel</button>
          </div>
        ) : (
          <div className="field-value">
            {renderValue(field.value)}
            {field.status === 'confirmed' && (
              <button 
                className="edit-icon-btn" 
                onClick={() => onEditStart(fieldKey, field.value)}
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
};

export { FieldEditorRow, renderValue };
