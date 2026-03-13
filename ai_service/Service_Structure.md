Qcaa_AI/
  ai_service/
    .env                 ← GEMINI_API_KEY, Supabase creds
    main.py              ← FastAPI app, POST /evaluate, runs on :5000
    config.py            ← Loads env vars, model constants
    text_extractor.py    ← PDF (pdfplumber) / DOCX (python-docx) / TXT → text
    context_builder.py   ← Fetch ISMG + mark allocs + curriculum from Supabase REST
    vector_search.py     ← Embed query (all-MiniLM-L6-v2) → match_qcaa_vectors RPC
    prompt_builder.py    ← Assemble system + user prompt for grading
    llm_client.py        ← Call Gemini 2.5 Flash (google-genai SDK, JSON mode)
    response_parser.py   ← Parse + validate LLM JSON, retry on failure
    requirements.txt     ← fastapi, uvicorn, google-genai, pdfplumber,
                            python-docx, sentence-transformers, requests
    Ai_Flow.md           ← Pipeline documentation
    Service_Structure.md ← This file

  LLM Config:
    Model:       gemini-2.5-flash-preview-05-20
    Provider:    Google AI (free tier)
    SDK:         google-genai
    Temperature: 0.2
    Max tokens:  8192
    JSON mode:   response_mime_type="application/json"

  Embedding Config:
    Model:     all-MiniLM-L6-v2 (sentence-transformers)
    Dimension: 384
    Runs:      locally on CPU (no API key needed)

  Feedback Output (per criterion):
    - Score (integer, within mark allocation range)
    - Band (A–E)
    - Detailed feedback paragraph with evidence from student work
    - Specific improvement suggestions to reach next band