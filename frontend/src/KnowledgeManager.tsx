import React, { useState, useEffect, useRef } from 'react';
import './KnowledgeManager.css';

interface KBStatus {
  total_chunks: number;
  unique_files: number;
  files: string[];
}

const KnowledgeManager: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [status, setStatus] = useState<KBStatus | null>(null);
  const [message, setMessage] = useState('');
  const [operation, setOperation] = useState<'add'|'replace'>('add');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch initial status
  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/kb/status');
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      } else {
        setMessage('Error fetching knowledge base status');
      }
    } catch (error) {
      setMessage('Network error when fetching status');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleDeleteAll = async () => {
    if (!window.confirm('Are you sure you want to delete the entire knowledge base?')) {
      return;
    }

    setDeleting(true);
    setMessage('');
    
    try {
      const response = await fetch('/api/kb/delete-all', {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setMessage('Knowledge base cleared successfully');
        fetchStatus();
      } else {
        const error = await response.json();
        setMessage(`Error: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      setMessage('Network error during delete operation');
    } finally {
      setDeleting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (files.length === 0) {
      setMessage('Please select files to upload');
      return;
    }

    setUploading(true);
    setMessage('');

    // If replacing, delete all first
    if (operation === 'replace') {
      try {
        const deleteResponse = await fetch('/api/kb/delete-all', {
          method: 'DELETE',
        });
        
        if (!deleteResponse.ok) {
          const error = await deleteResponse.json();
          setMessage(`Error clearing KB: ${error.detail || 'Unknown error'}`);
          setUploading(false);
          return;
        }
      } catch (error) {
        setMessage('Network error during replace operation');
        setUploading(false);
        return;
      }
    }

    // Now upload files
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await fetch('/api/kb/load', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        let successCount = 0;
        let errorCount = 0;
        
        Object.entries(result).forEach(([_filename, status]: [string, any]) => {
          if (status.status === 'success') {
            successCount++;
          } else {
            errorCount++;
          }
        });

        setMessage(`Upload complete: ${successCount} files successful, ${errorCount} failed`);
        fetchStatus();
        setFiles([]);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      } else {
        const error = await response.json();
        setMessage(`Error: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      setMessage('Network error during upload');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="knowledge-manager">
      <h2>Knowledge Base Manager</h2>
      
      <div className="kb-status">
        <h3>Current Status</h3>
        {status ? (
          <div>
            <p><strong>Total Chunks:</strong> {status.total_chunks}</p>
            <p><strong>Unique Files:</strong> {status.unique_files}</p>
            {status.files.length > 0 && (
              <>
                <p><strong>Files:</strong></p>
                <ul className="file-list">
                  {status.files.map((file, index) => (
                    <li key={index}>{file}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        ) : (
          <p>Loading status...</p>
        )}
      </div>

      <div className="kb-actions">
        <form onSubmit={handleSubmit}>
          <div className="operation-selector">
            <label>
              <input
                type="radio"
                name="operation"
                value="add"
                checked={operation === 'add'}
                onChange={() => setOperation('add')}
              />
              Add to Knowledge Base
            </label>
            <label>
              <input
                type="radio"
                name="operation"
                value="replace"
                checked={operation === 'replace'}
                onChange={() => setOperation('replace')}
              />
              Replace Knowledge Base
            </label>
          </div>
          
          <div className="file-input-container">
            <input
              type="file"
              multiple
              accept=".txt,.md"
              onChange={handleFileChange}
              ref={fileInputRef}
              disabled={uploading}
            />
            <p className="file-hint">Accept .txt and .md files</p>
          </div>
          
          {files.length > 0 && (
            <div className="selected-files">
              <p><strong>Selected Files:</strong> {files.length}</p>
              <ul>
                {Array.from(files).map((file, index) => (
                  <li key={index}>{file.name} ({Math.round(file.size / 1024)} KB)</li>
                ))}
              </ul>
            </div>
          )}
          
          <div className="button-group">
            <button 
              type="submit" 
              disabled={uploading || files.length === 0}
              className="upload-btn"
            >
              {uploading ? 'Uploading...' : operation === 'add' ? 'Upload Files' : 'Replace Knowledge Base'}
            </button>
            
            <button
              type="button"
              onClick={handleDeleteAll}
              disabled={deleting || status?.total_chunks === 0}
              className="delete-btn"
            >
              {deleting ? 'Deleting...' : 'Delete All Files'}
            </button>
          </div>
        </form>
        
        {message && <div className="status-message">{message}</div>}
      </div>
    </div>
  );
};

export default KnowledgeManager;