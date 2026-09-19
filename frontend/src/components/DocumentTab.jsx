import React from 'react';
import DOMPurify from 'dompurify';

const DocumentTab = ({ documentText, handleDownload }) => {
  return (
    <div className="document-tab">
      <div className="document-preview">
        {documentText ? (
          <>
            <div className="document-actions" style={{textAlign: 'right', marginBottom: '10px', position: 'relative', zIndex: 10}}>
                <button onClick={handleDownload} className="download-btn">Download PDF</button>
            </div>
            <div 
              id="document-preview-content" 
              className="document-text" 
              dangerouslySetInnerHTML={{ 
                __html: DOMPurify.sanitize(
                  documentText
                    .replace(/\n? *═{10,} *\n?/g, '<hr class="legal-hr-thick" />')
                    .replace(/\n? *─{10,} *\n?/g, '<hr class="legal-hr-thin" />')
                    .replace(/(<hr class="legal-hr-thin" \/>)(SECTION \d+ — [^<]+)(<hr class="legal-hr-thin" \/>)/g, '<div class="legal-section-header">$1<strong class="legal-section-title">$2</strong>$3</div>')
                    .replace(/\n/g, '<br/>')
                ) 
              }} 
            />
          </>
        ) : (
          <div className="empty-document">Draft will appear here once ready for review.</div>
        )}
      </div>
    </div>
  );
};

export default DocumentTab;
