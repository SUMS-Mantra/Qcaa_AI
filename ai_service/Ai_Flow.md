Student uploads assignment (PDF/DOCX/TXT)
        │
        ▼
┌─ 1. EXTRACT TEXT ────────────────────────┐
│  PDF  → pdfplumber                        │
│  DOCX → python-docx                       │
│  TXT  → direct read (utf-8)              │
│  Output: plain text string                │
└──────────────────────────────────────────┘
        │
        ▼
┌─ 2. IDENTIFY CONTEXT ───────────────────┐
│  From the request: subject + assessment   │
│  type (e.g. "Biology", "IA2")             │
│                                           │
│  Query qcaa_curriculum (Supabase REST)    │
│  for this subject + assessment:           │
│  • ISMG criteria + band descriptors       │
│  • Mark allocations (marks per criterion) │
│  • Assessment conditions & description    │
│  • Relevant unit/topic subject matter     │
└──────────────────────────────────────────┘
        │
        ▼
┌─ 3. VECTOR SEARCH — RAG ────────────────┐
│  Take first ~500 words of student text    │
│  + assessment type as search query        │
│                                           │
│  Embed locally (all-MiniLM-L6-v2, 384d)  │
│  → POST to match_qcaa_vectors() RPC      │
│  → Top 8 syllabus chunks returned        │
│                                           │
│  Filters by subject for relevance         │
│  Gives the LLM specific syllabus context  │
└──────────────────────────────────────────┘
        │
        ▼
┌─ 4. BUILD PROMPT ────────────────────────┐
│  SYSTEM:                                  │
│  "You are an expert QCAA assessment       │
│   marker for {subject} {assessment}.      │
│   Grade strictly against the ISMG.        │
│   For each criterion, provide:            │
│   - score (integer within mark range)     │
│   - band (A–E)                            │
│   - detailed feedback paragraph with      │
│     evidence from the student's work      │
│   - specific improvement suggestions      │
│     to reach the next band"               │
│                                           │
│  USER message includes:                   │
│  • ISMG criteria + band descriptors       │
│  • Mark allocation per criterion          │
│  • Syllabus context (from RAG chunks)     │
│  • Assessment conditions                  │
│  • Student's full submission text         │
│                                           │
│  Instruct: respond ONLY with valid JSON   │
│  matching the response schema             │
└──────────────────────────────────────────┘
        │
        ▼
┌─ 5. LLM CALL — Gemini 2.5 Flash ────────┐
│  Provider: Google AI (google-genai SDK)   │
│  Model: gemini-2.5-flash-preview-05-20   │
│  Tier: Free                               │
│  Context: 1M tokens                       │
│                                           │
│  response_mime_type: application/json     │
│  Temperature: 0.2 (consistent grading)    │
│  Max output tokens: 8192                  │
└──────────────────────────────────────────┘
        │
        ▼
┌─ 6. PARSE & VALIDATE ───────────────────┐
│  Parse JSON response                      │
│  Validate:                                │
│  • Each criterion score ≤ max marks       │
│  • All expected criteria present          │
│  • Feedback ≥ 20 words per criterion      │
│  • Overall score = sum of criteria scores │
│  • Band is one of A, B, C, D, E          │
│                                           │
│  If invalid → retry once with error hint  │
│  If retry fails → return partial + flag   │
└──────────────────────────────────────────┘
        │
        ▼
┌─ 7. RETURN RESULTS ─────────────────────┐
│  Response JSON:                           │
│  {                                        │
│    rubric_scores: [                       │
│      { criterion, score, max_score,       │
│        band, feedback, improvement }      │
│    ],                                     │
│    overall_score, max_overall_score,      │
│    feedback (overall summary),            │
│    model_version,                         │
│    syllabus_context_used: [...]           │
│  }                                        │
│                                           │
│  → Express backend stores in ai_results   │
│  → Frontend polls and renders feedback    │
│  → Audit log written                      │
└──────────────────────────────────────────┘