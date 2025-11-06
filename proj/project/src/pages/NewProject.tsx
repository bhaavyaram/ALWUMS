import { useState } from 'react';
import { FileUpload } from '../components/FileUpload';
import { Loader2 } from 'lucide-react';

interface NewProjectProps {
  onBack: () => void;
  onProjectCreated: (projectId: string) => void;
}

export function NewProject({ onBack, onProjectCreated }: NewProjectProps) {
  const [projectName, setProjectName] = useState('');
  const [description, setDescription] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCreateProject = async () => {
    if (!projectName.trim()) {
      setError('Project name is required');
      return;
    }

    if (files.length === 0) {
      setError('Please select at least one file');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Create ZIP file from uploaded files
      const JSZip = (await import('jszip')).default;
      const zip = new JSZip();
      files.forEach((file) => {
        zip.file(file.name, file);
      });
      const zipBlob = await zip.generateAsync({ type: 'blob' });

      // Generate run ID
      const runId = crypto.randomUUID();

      // Upload to backend
      const formData = new FormData();
      formData.append('file', zipBlob, 'project.zip');

      console.log('Sending request to backend with runId:', runId);
      const response = await fetch(`http://localhost:8000/upgrade?run_id=${runId}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Backend response:', response.status, errorText);
        throw new Error(`Backend error: ${response.status} ${errorText}`);
      }

      // Verify response is a ZIP
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/zip')) {
        const text = await response.text();
        console.error('Unexpected response content-type:', contentType, 'Body:', text);
        throw new Error(`Expected ZIP file, got content-type: ${contentType}`);
      }

      // Download the result
      const blob = await response.blob();
      console.log('Received blob size:', blob.size, 'type:', blob.type);

      if (blob.size === 0) {
        throw new Error('Received empty response from backend');
      }

      const zipFileName = `upgraded_project_${runId}.zip`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = zipFileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      console.log('Download triggered for:', zipFileName);
      onProjectCreated(runId);
    } catch (err) {
      console.error('Fetch error details:', err);
      setError(`Failed to process project: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white border border-gray-200 rounded-lg p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Create New Project
        </h1>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Project Name *
            </label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="e.g., Legacy Payment System Upgrade"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the project and upgrade goals"
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Upload Files *
            </label>
            <FileUpload onFilesSelected={setFiles} />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex gap-4">
            <button
              onClick={handleCreateProject}
              disabled={loading}
              className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <span>Start Upgrade</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}