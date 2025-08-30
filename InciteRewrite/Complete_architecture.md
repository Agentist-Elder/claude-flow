Critical Eye InCite Detector™ - Complete Architecture
Project Overview
Legal citation verification system that validates citations against CourtListener's database without storing user documents. Privacy-first design using document hashing for permanent fraud protection audit trail. Hash values never exposed to users to prevent document tampering.
Core Requirements
Functional Requirements

Accept PDF, DOCX, TXT documents (max 50MB)
Extract legal citations using eyecite library
Verify citations against CourtListener API
Calculate confidence scores for each citation
Provide adjustable confidence threshold (50-100%)
Enable result retrieval via temporary session tokens (1 hour)
Verify document authenticity via re-upload
Zero document retention (memory-only processing)

Non-Functional Requirements

Stateless request handling
Attorney-client privilege protection
Permanent audit trail for fraud protection
Sub-5 second response for typical documents
Rate limiting on both client and API sides
Hash values never exposed to prevent tampering

System Architecture
API Endpoints
pythonPOST /analyze
  Input: multipart/form-data with document file
  Process: Hash → Check cache → Extract → Verify → Store permanently
  Output: JSON with session_token, confidence scores, and results (no hash)

POST /verify
  Input: multipart/form-data with document file
  Process: Hash → Check if exists in database
  Output: JSON with verified: true/false and timestamp if exists

GET /results/{session_token}
  Input: Session token (expires 1 hour)
  Output: JSON with results (no hash exposed)

GET /view/{session_token}
  Input: Session token (expires 1 hour)
  Output: HTML page with threshold slider

POST /delete/{hash_id}
  Input: SHA-256 hash (admin only)
  Output: Confirmation or 404

GET /robots.txt
  Output: Disallow result pages from indexing

GET /health
  Output: System status and CourtListener connectivity
Data Flow
1. Document Upload → Memory buffer (BytesIO)
2. Generate SHA-256 hash of original bytes (internal only)
3. Check permanent storage for existing results
4. If cached → return with new session token (no reprocessing)
5. Extract text without saving file
6. Extract citations with eyecite (with deduplication)
7. Batch citations for CourtListener (max 250)
8. Calculate confidence scores
9. Store permanently: hash → results + confidence
10. Create session token → hash mapping (1 hour TTL)
11. Return results with session token (not hash)
12. Document purged from memory
Data Models
Citation Result with Confidence
json{
  "citation": "123 F.3d 456",
  "found": true,
  "confidence": 85,
  "case_name": "Smith v. Jones",
  "url": "https://www.courtlistener.com/opinion/...",
  "error": null
}
User-Facing Response
json{
  "session_token": "URL_safe_random_token",
  "timestamp": "2024-01-15T10:30:00",
  "total_citations": 25,
  "verified": 20,
  "suspicious": 3,
  "not_found": 2,
  "default_threshold": 70,
  "citations": [...]
}
Internal Storage
json{
  "hash_id": "sha256_hash",
  "timestamp": "2024-01-15T10:30:00",
  "total_citations": 25,
  "verified": 20,
  "suspicious": 3,
  "not_found": 2,
  "default_threshold": 70,
  "citations": [...]
}
Database Schema
Table: results
sqlCREATE TABLE results (
    hash_id TEXT PRIMARY KEY,     -- SHA-256 of document (never exposed)
    data TEXT NOT NULL,            -- JSON results with confidence
    created_at TIMESTAMP NOT NULL, -- Fraud protection timestamp
    last_accessed TIMESTAMP        -- Analytics tracking
)
Table: sessions
sqlCREATE TABLE sessions (
    token TEXT PRIMARY KEY,        -- Random URL-safe token
    hash_id TEXT NOT NULL,         -- Links to results table
    expires_at TIMESTAMP NOT NULL, -- 1 hour from creation
    FOREIGN KEY (hash_id) REFERENCES results(hash_id)
)
No expiration on results. Permanent storage for audit trail. Sessions expire after 1 hour.
Confidence Scoring Algorithm
pythonconfidence = 100  # Start with perfect score
if returned_citation != requested_citation:
    confidence -= 20  # Citation mismatch
if not case_name:
    confidence -= 15  # Missing case name  
if multiple_clusters:
    confidence -= 10  # Ambiguous match

# Thresholds:
# >= 70%: Verified (default)
# 1-69%: Below threshold/suspicious
# 0%: Not found/hallucination
Security Features
Rate Limiting

Client-side: 10 requests/minute per IP
CourtListener API: 60 citations/minute
Automatic retry on 429 responses

Privacy Protection

No document storage
No user accounts
No tracking cookies
Hash values never exposed
Results accessible only via temporary session token

Security Headers

X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self' 'unsafe-inline'

Fraud Protection

Document hash stored permanently but never exposed
Verification requires document re-upload
Timestamp proves when document was first processed
Session tokens prevent hash manipulation

Logging

Document processing metrics (internal hash, size, citation count)
API verification results (verified/suspicious/not found)
Deletion events for audit trail
Verification attempts with timestamps
Format: timestamp - level - message

External Dependencies
Required Libraries
flask==3.0.0
pymupdf==1.23.8
python-docx==1.1.0
eyecite==2.5.1
requests==2.31.0
python-dotenv==1.0.0
External Services

CourtListener API v4

Endpoint: /api/rest/v4/citation-lookup/
Rate limit: 60 citations/minute
Batch limit: 250 citations/request
Auth: Token-based



Environment Configuration
bash# .env file
COURTLISTENER_API_TOKEN=your_token_here
MAX_FILE_SIZE=52428800  # 50MB
Deployment
Development
bashpython app.py  # Flask development server on port 5000
Production
bashgunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
Success Metrics

<5 second processing for 50-citation document
100% document privacy (zero retention)
Permanent fraud protection via hash verification
95%+ citation extraction accuracy
Client-side threshold adjustment without API calls
Zero hash exposure to users

Key Differentiators

No document storage - Memory-only processing
Permanent audit trail - Hash stored forever, never exposed
Fraud-proof verification - Requires document re-upload
Confidence scoring - Transparent match quality
User-controlled threshold - Adjust strictness without reprocessing
No authentication required - Complete anonymity
Session-based access - Results expire after 1 hour