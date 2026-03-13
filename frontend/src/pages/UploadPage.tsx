import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { getSubjects, uploadAssignment, type SubjectWithAssessments } from '../api';

const ACCEPTED_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
};

export default function UploadPage() {
  const navigate = useNavigate();
  const [subjects, setSubjects] = useState<SubjectWithAssessments[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [subjectId, setSubjectId] = useState('');
  const [assessmentId, setAssessmentId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  // Load subjects + assessment types from API
  useEffect(() => {
    getSubjects()
      .then(({ subjects: s }) => setSubjects(s))
      .catch(() => toast.error('Failed to load subjects'));
  }, []);

  const selectedSubject = subjects.find((s) => String(s.id) === subjectId);
  const assessments = selectedSubject?.assessments ?? [];

  const onDrop = useCallback((accepted: File[], rejected: unknown[]) => {
    if ((rejected as Array<unknown>).length > 0) {
      toast.error('Invalid file type. Please upload PDF, DOCX, or TXT.');
      return;
    }
    if (accepted.length > 0) {
      setFile(accepted[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 1,
    multiple: false,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) {
      toast.error('Please select a file to upload.');
      return;
    }
    if (!subjectId) {
      toast.error('Please select a subject.');
      return;
    }
    if (!assessmentId) {
      toast.error('Please select an assessment type.');
      return;
    }

    setUploading(true);
    setProgress(10);

    try {
      setProgress(30);
      const { assignment } = await uploadAssignment(file, Number(assessmentId));
      setProgress(100);
      toast.success('Assignment uploaded! AI grading has started.');
      navigate(`/feedback/${assignment.id}`);
    } catch {
      toast.error('Something went wrong. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const removeFile = () => setFile(null);

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload Assignment</h1>
      <p className="text-gray-500 mb-8">
        Upload your assignment file and select the subject and assessment type for AI grading.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Dropzone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Assignment File</label>
          {!file ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
                ${isDragActive
                  ? 'border-zima bg-zima/5'
                  : 'border-gray-300 hover:border-zima/50 hover:bg-gray-50'
                }`}
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-zima/10 flex items-center justify-center">
                  <svg className="w-6 h-6 text-zima" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    {isDragActive ? 'Drop your file here' : 'Drag & drop your file here'}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">PDF, DOCX, or TXT up to 10 MB</p>
                </div>
                <button
                  type="button"
                  className="text-sm font-medium text-zima hover:text-zima-light transition-colors"
                >
                  Browse files
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-lg bg-zima/10 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-zima" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
                  <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
              <button
                type="button"
                onClick={removeFile}
                className="p-1.5 rounded-lg hover:bg-gray-200 transition-colors text-gray-400 hover:text-gray-600"
                aria-label="Remove file"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Subject dropdown */}
        <div>
          <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-2">
            Subject
          </label>
          <select
            id="subject"
            value={subjectId}
            onChange={(e) => { setSubjectId(e.target.value); setAssessmentId(''); }}
            className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900
                       focus:border-zima focus:ring-2 focus:ring-zima/20 outline-none transition-all"
          >
            <option value="">Select a subject...</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Assessment Type dropdown */}
        <div>
          <label htmlFor="assessment-type" className="block text-sm font-medium text-gray-700 mb-2">
            Assessment Type
          </label>
          <select
            id="assessment-type"
            value={assessmentId}
            onChange={(e) => setAssessmentId(e.target.value)}
            disabled={!subjectId}
            className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900
                       focus:border-zima focus:ring-2 focus:ring-zima/20 outline-none transition-all
                       disabled:bg-gray-50 disabled:text-gray-400"
          >
            <option value="">{subjectId ? 'Select assessment type...' : 'Select a subject first'}</option>
            {assessments.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        {/* Progress bar */}
        {uploading && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 font-medium">
                {progress < 50 ? 'Uploading...' : progress < 100 ? 'AI is analyzing...' : 'Done!'}
              </span>
              <span className="text-zima font-semibold">{progress}%</span>
            </div>
            <div className="w-full h-2.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-zima rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={uploading}
          className="w-full py-3.5 rounded-xl bg-zima text-white font-semibold text-sm
                     shadow-lg shadow-zima/25 hover:bg-zima-light hover:shadow-zima-light/30
                     transition-all duration-200 active:scale-[0.98]
                     disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100"
        >
          {uploading ? 'Processing...' : 'Submit for Grading'}
        </button>
      </form>
    </div>
  );
}
