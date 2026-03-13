export interface RubricCriterion {
  id: string;
  name: string;
  maxScore: number;
  score: number;
  feedback: string;
}

export interface AssignmentResult {
  id: string;
  fileName: string;
  subject: string;
  assessmentType: string;
  submittedAt: string;
  criteria: RubricCriterion[];
  overallScore: number;
  maxOverallScore: number;
}

export interface HistoryEntry {
  id: string;
  fileName: string;
  subject: string;
  assessmentType: string;
  submittedAt: string;
  overallScore: number;
  maxOverallScore: number;
}
