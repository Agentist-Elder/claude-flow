# InciteRewrite API Usage Guide

## Overview

InciteRewrite is a privacy-first legal citation verification system that analyzes documents for legal citations and verifies them against the CourtListener database. The system implements a zero-storage policy for document content, using only document hashes for audit trails.

## Base URL

```
http://localhost:5000/api  (Development)
https://your-domain.com/api  (Production)
```

## Authentication

The current version uses session-based authentication without requiring API keys. Sessions are automatically created during document analysis and expire after 1 hour.

## API Endpoints

### 1. Analyze Document

Extracts legal citations from a document and creates a session for further operations.

**Endpoint:** `POST /api/analyze`

**Request:**
```json
{
  "document": "In Brown v. Board of Education, 347 U.S. 483 (1954), the Supreme Court held that racial segregation in public schools violates the Equal Protection Clause. See also 42 U.S.C. § 1983."
}
```

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-08-30T23:05:45.123Z",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "citations_found": 2,
    "status": "analysis_complete",
    "message": "Document analyzed successfully. Use session_id to verify citations."
  }
}
```

### 2. Verify Citations

Verifies the citations found in the analyzed document against the CourtListener database.

**Endpoint:** `POST /api/verify`

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "document": "Same document content as provided to /analyze"
}
```

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-08-30T23:06:00.123Z",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "verification_complete",
    "citations_found": 2,
    "citations_verified": 2,
    "overall_confidence": 0.85,
    "verification_rate": 1.0
  }
}
```

### 3. Get Results

Retrieves detailed verification results for a session.

**Endpoint:** `GET /api/results/{session_id}`

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-08-30T23:06:15.123Z",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "analysis_timestamp": "2025-08-30T23:05:45.123Z",
    "citations_found": 2,
    "citations_verified": 2,
    "overall_confidence": 0.85,
    "verification_rate": 1.0,
    "citation_details": [
      {
        "citation": "347 U.S. 483 (1954)",
        "type": "case_citation",
        "verified": true,
        "confidence": 0.9,
        "courtlistener_match": {
          "case_name": "Brown v. Board of Education of Topeka",
          "citation": "347 U.S. 483",
          "court": "Supreme Court",
          "date_filed": "1954-05-17",
          "url": "https://www.courtlistener.com/opinion/..."
        },
        "error": null
      },
      {
        "citation": "42 U.S.C. § 1983",
        "type": "statute_citation",
        "verified": true,
        "confidence": 0.8,
        "courtlistener_match": {},
        "error": null
      }
    ]
  }
}
```

### 4. View Session

Retrieves basic session information without detailed results.

**Endpoint:** `GET /api/view/{session_id}`

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-08-30T23:06:30.123Z",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-08-30T23:05:45.123Z",
    "expires_at": "2025-08-31T00:05:45.123Z",
    "status": "active",
    "has_results": true,
    "citations_found": 2,
    "citations_verified": 2
  }
}
```

### 5. Health Check

Checks system health and service status.

**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-08-30T23:06:45.123Z",
  "data": {
    "status": "healthy",
    "timestamp": "2025-08-30T23:06:45.123Z",
    "version": "1.0.0",
    "services": {
      "database": "healthy",
      "courtlistener": "healthy",
      "citation_processor": "healthy"
    },
    "courtlistener_status": {
      "available": true,
      "api_key_configured": true,
      "rate_limit_remaining": 85,
      "response_time": 0.245
    }
  }
}
```

## Workflow Examples

### Basic Citation Verification

```python
import requests

# Step 1: Analyze document
document_text = """
In Miranda v. Arizona, 384 U.S. 436 (1966), the Court established 
the requirement for police to inform suspects of their rights.
This builds upon 42 U.S.C. § 1983.
"""

response = requests.post('http://localhost:5000/api/analyze', json={
    'document': document_text
})

session_data = response.json()
session_id = session_data['data']['session_id']

# Step 2: Verify citations
verify_response = requests.post('http://localhost:5000/api/verify', json={
    'session_id': session_id,
    'document': document_text
})

# Step 3: Get detailed results
results_response = requests.get(f'http://localhost:5000/api/results/{session_id}')
results = results_response.json()

print(f"Found {results['data']['citations_found']} citations")
print(f"Verified {results['data']['citations_verified']} citations")
print(f"Overall confidence: {results['data']['overall_confidence']}")
```

### JavaScript Example

```javascript
class InciteRewriteClient {
    constructor(baseUrl = 'http://localhost:5000/api') {
        this.baseUrl = baseUrl;
    }

    async analyzeCitations(documentText) {
        const response = await fetch(`${this.baseUrl}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ document: documentText }),
        });
        
        return await response.json();
    }

    async verifyCitations(sessionId, documentText) {
        const response = await fetch(`${this.baseUrl}/verify`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                document: documentText
            }),
        });
        
        return await response.json();
    }

    async getResults(sessionId) {
        const response = await fetch(`${this.baseUrl}/results/${sessionId}`);
        return await response.json();
    }
}

// Usage
const client = new InciteRewriteClient();

async function verifyLegalDocument(documentText) {
    try {
        // Analyze
        const analysis = await client.analyzeCitations(documentText);
        const sessionId = analysis.data.session_id;
        
        // Verify
        await client.verifyCitations(sessionId, documentText);
        
        // Get results
        const results = await client.getResults(sessionId);
        
        console.log('Verification Results:', results.data);
    } catch (error) {
        console.error('Error:', error);
    }
}
```

## Error Handling

### Common Error Responses

**400 Bad Request**
```json
{
  "success": false,
  "timestamp": "2025-08-30T23:07:00.123Z",
  "error": {
    "message": "Missing 'document' field",
    "code": "E400",
    "status_code": 400
  }
}
```

**403 Forbidden**
```json
{
  "success": false,
  "timestamp": "2025-08-30T23:07:15.123Z",
  "error": {
    "message": "Document hash mismatch - document may have been modified",
    "code": "E403",
    "status_code": 403
  }
}
```

**404 Not Found**
```json
{
  "success": false,
  "timestamp": "2025-08-30T23:07:30.123Z",
  "error": {
    "message": "Invalid or expired session",
    "code": "E404",
    "status_code": 404
  }
}
```

## Rate Limits

- **CourtListener API**: 90 requests per hour (conservative limit)
- **Document Size**: Maximum 10MB per document
- **Session Limit**: No explicit limit, but sessions expire after 1 hour

## Privacy and Security

### Data Protection
- **Zero Storage**: Document content is never stored, only processed in memory
- **Hash-Only Audit**: Only SHA256 hashes stored for integrity verification
- **Automatic Expiry**: All session data expires after 1 hour
- **Secure Sessions**: UUID-based session identifiers

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## Citation Types Supported

### Case Citations
- Standard format: `347 U.S. 483 (1954)`
- Federal courts: `123 F.3d 456 (9th Cir. 2000)`
- State courts: `123 Cal. App. 4th 567 (2005)`

### Statute Citations
- U.S. Code: `42 U.S.C. § 1983`
- Code of Federal Regulations: `29 C.F.R. § 1630.2`
- State statutes: `Cal. Civ. Code § 1234`

### Constitutional Citations
- U.S. Constitution: `U.S. Const. amend. XIV`
- State constitutions: `Cal. Const. art. I, § 7`

### Rule Citations
- Federal Rules: `Fed. R. Civ. P. 12(b)(6)`
- Local rules: `Local R. 7.1`

## Best Practices

1. **Document Integrity**: Always provide the exact same document content to both `/analyze` and `/verify` endpoints
2. **Session Management**: Store session IDs securely and respect the 1-hour expiry
3. **Error Handling**: Implement proper error handling for all API calls
4. **Rate Limiting**: Respect CourtListener API limits by implementing appropriate delays
5. **Privacy**: Never log or store sensitive document content in your application

## Support

For technical support or API questions:
- Documentation: `/docs`
- Health Check: `/api/health`
- Repository: https://github.com/your-org/inciterewrite