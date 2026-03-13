const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:4000/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> ?? {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets multipart boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    // Try refresh
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json();
    }
    // Clear auth — React auth context will handle redirect
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    throw new ApiError(401, 'Session expired');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText);
  }

  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// ───────── Auth ─────────

export function signup(email: string, password: string, full_name?: string) {
  return request<{ user: { id: string; email: string } }>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name }),
  });
}

export function login(email: string, password: string) {
  return request<{ access_token: string; refresh_token: string; user: { id: string; email: string } }>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ email, password }) },
  );
}

export function getMe() {
  return request<{ profile: { id: string; email: string; full_name: string; role: string } }>('/auth/me');
}

// ───────── Subjects ─────────

export interface SubjectWithAssessments {
  id: number;
  name: string;
  assessments: { id: number; name: string }[];
}

export function getSubjects() {
  return request<{ subjects: SubjectWithAssessments[] }>('/subjects');
}

// ───────── Assignments ─────────

export function uploadAssignment(file: File, assessmentId: number) {
  const form = new FormData();
  form.append('file', file);
  form.append('assessment_id', String(assessmentId));
  return request<{ assignment: { id: string; status: string } }>('/assignments', {
    method: 'POST',
    body: form,
  });
}

export interface HistoryEntry {
  id: string;
  fileName: string;
  subject: string;
  assessmentType: string;
  status: string;
  submittedAt: string;
  overallScore: number | null;
  maxOverallScore: number | null;
}

export function getHistory() {
  return request<{ history: HistoryEntry[] }>('/assignments');
}

export function getAssignment(id: string) {
  return request<{ assignment: any }>(`/assignments/${id}`);
}

// ───────── Feedback ─────────

export interface FeedbackCriterion {
  criterion_id: number;
  criterion: string;
  score: number;
  max_score: number;
  feedback: string;
  band?: string;
  improvement?: string;
  evidence_quotes?: string[];
  band_analysis?: Record<string, string>;
}

export interface FeedbackResult {
  id: string;
  criteria: FeedbackCriterion[];
  overallScore: number;
  maxOverallScore: number;
  feedback: string;
  assignmentText: string;
  processedAt: string;
}

export interface FeedbackResponse {
  assignment: {
    id: string;
    fileName: string;
    status: string;
    subject: string;
    assessmentType: string;
    submittedAt?: string;
  };
  result: FeedbackResult | null;
}

export function getFeedback(assignmentId: string) {
  return request<FeedbackResponse>(`/feedback/${assignmentId}`);
}
