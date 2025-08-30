Complete Core Architectural Flow
1. INTAKE LAYER (Stateless)
   POST /analyze
   ├── Stream document to memory (BytesIO)
   ├── Extract text (PyMuPDF/python-docx)
   ├── Generate SHA-256 hash (internal only)
   ├── Check if hash exists in permanent storage
   │   └── If exists: return cached results with NEW session token
   ├── Quick citation scan (eyecite)
   └── Return: No citations → exit with message
             Has citations → continue
   
   POST /verify
   ├── Stream document to memory
   ├── Generate SHA-256 hash
   ├── Check if hash exists in database
   └── Return: exists with timestamp or never processed

2. PROCESSING LAYER (Memory only)
   ├── Extract all citations with eyecite (deduped)
   ├── Log processing metrics (document size, citation count)
   ├── Batch citations (250 max per request)
   ├── Call CourtListener API with rate limiting (60/min)
   ├── Calculate confidence scores per citation
   │   ├── 100 = exact match
   │   ├── -20 = citation mismatch
   │   ├── -15 = no case name
   │   └── -10 = multiple clusters
   └── Handle 429 rate limits with retry

3. STORAGE LAYER (Permanent audit trail)
   SQLite database: results.db
   Table: results
   ├── hash_id (PRIMARY KEY) - SHA-256 (never exposed)
   ├── data (TEXT) - JSON with all results + confidence
   ├── created_at (TIMESTAMP) - fraud protection
   └── last_accessed (TIMESTAMP) - analytics
   
   Table: sessions
   ├── token (PRIMARY KEY) - random URL-safe token
   ├── hash_id (FOREIGN KEY) - links to results
   └── expires_at (TIMESTAMP) - 1 hour TTL

4. RETRIEVAL LAYER
   GET /results/{token}
   ├── Validate token and expiry
   ├── Retrieve results via hash_id
   └── Return JSON (no hash exposed)
   
   GET /view/{token}
   ├── Validate token and expiry
   ├── Retrieve results via hash_id
   └── Return HTML with threshold slider (client-side filtering)

5. SECURITY LAYER
   ├── Rate limiting: 10 requests/minute per IP
   ├── Security headers (X-Frame-Options, CSP, etc.)
   ├── Session tokens expire in 1 hour
   ├── Hash values never exposed to users
   ├── File size limit: 50MB
   └── Allowed formats: PDF, DOCX, TXT only
