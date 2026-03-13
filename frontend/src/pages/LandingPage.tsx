import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LandingPage() {
  const { user, loading } = useAuth();

  if (loading) return <div className="p-12 text-center text-gray-400">Loading...</div>;
  if (user) return <Navigate to="/upload" replace />;

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] px-4">
      <div className="max-w-xl text-center space-y-8">
        {/* Hero icon */}
        <div className="mx-auto w-20 h-20 rounded-2xl bg-zima/10 flex items-center justify-center">
          <svg className="w-10 h-10 text-zima" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>

        <div className="space-y-3">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 tracking-tight">
            QCAA AI Grader
          </h1>
          <p className="text-lg text-gray-500 max-w-md mx-auto">
            Upload your assignment and receive instant AI-powered feedback aligned to QCAA rubric criteria.
          </p>
        </div>

        <Link
          to="/login"
          className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-zima text-white font-semibold
                     shadow-lg shadow-zima/25 hover:bg-zima-light hover:shadow-zima-light/30
                     transition-all duration-200 active:scale-[0.98]"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          Get Started
        </Link>

        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-3 pt-4">
          {['AI-Powered Feedback', 'QCAA Aligned', 'Instant Results'].map((feat) => (
            <span
              key={feat}
              className="px-4 py-1.5 rounded-full bg-gray-100 text-sm text-gray-600 font-medium"
            >
              {feat}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
