import type { AssignmentResult } from '../types';

/** Demo data used before real API integration */
export const MOCK_RESULT: AssignmentResult = {
  id: 'demo',
  fileName: 'essay_draft_final.pdf',
  subject: 'English',
  assessmentType: 'Internal Assessment 1 (IA1)',
  submittedAt: new Date().toISOString(),
  overallScore: 18,
  maxOverallScore: 25,
  criteria: [
    {
      id: '1',
      name: 'Knowledge & Understanding',
      maxScore: 5,
      score: 4,
      feedback:
        'Demonstrates a thorough understanding of the subject matter with relevant examples. Minor gaps in linking theory to practical application.',
    },
    {
      id: '2',
      name: 'Analysis & Evaluation',
      maxScore: 5,
      score: 3,
      feedback:
        'Analysis is generally sound but some evaluative claims lack sufficient supporting evidence. Consider strengthening counterarguments.',
    },
    {
      id: '3',
      name: 'Research & Planning',
      maxScore: 5,
      score: 5,
      feedback:
        'Excellent research with well-chosen, credible sources. Planning is methodical and clearly documented throughout.',
    },
    {
      id: '4',
      name: 'Communication & Expression',
      maxScore: 5,
      score: 4,
      feedback:
        'Writing is clear and well-structured. Vocabulary is appropriate for the audience. A few transitions between paragraphs could be smoother.',
    },
    {
      id: '5',
      name: 'Referencing & Academic Integrity',
      maxScore: 5,
      score: 2,
      feedback:
        'Several in-text citations are missing or incorrectly formatted. Reference list has inconsistencies—review APA 7th edition guidelines.',
    },
  ],
};
