# InciteRewrite Platform - System Architecture

## Executive Summary

InciteRewrite is a microservices-based content rewriting platform designed for high availability, scalability, and real-time collaboration. The architecture emphasizes security, performance, and maintainability while supporting concurrent document editing and AI-powered content enhancement.

## 1. System Architecture Overview

### 1.1 Microservices Architecture Decision

**Decision: Microservices over Monolith**

**Rationale:**
- **Scalability**: Independent scaling of high-demand services (AI processing, real-time collaboration)
- **Technology Flexibility**: Different services can use optimal tech stacks
- **Fault Isolation**: Service failures don't cascade across the entire platform
- **Team Autonomy**: Separate teams can develop and deploy services independently
- **Performance**: Critical services (document processing) can be optimized independently

**Trade-offs Considered:**
- Increased operational complexity
- Network latency between services
- Distributed system challenges (eventual consistency, service discovery)

### 1.2 High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Mobile Client  │    │   Admin Panel   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Load Balancer       │
                    │     (NGINX/HAProxy)     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     API Gateway         │
                    │   (Rate Limiting,       │
                    │   Auth, Routing)        │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
    ┌─────▼─────┐      ┌─────────▼─────────┐      ┌─────▼─────┐
    │   Auth    │      │     Document      │      │Analytics  │
    │  Service  │      │     Service       │      │ Service   │
    └───────────┘      └───────────────────┘      └───────────┘
          │                      │                      │
          │            ┌─────────▼─────────┐            │
          │            │   Rewrite AI      │            │
          │            │    Service        │            │
          │            └───────────────────┘            │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Message Queue        │
                    │     (Redis/RabbitMQ)    │
                    └─────────────────────────┘
```

## 2. Service Architecture

### 2.1 Core Services

#### Authentication Service
- **Responsibility**: User authentication, authorization, JWT management
- **Technology**: Node.js with Express, bcrypt for hashing
- **Database**: PostgreSQL (users, roles, permissions)
- **Port**: 3001

#### Document Service
- **Responsibility**: Document CRUD, versioning, collaboration
- **Technology**: Node.js with Express, Socket.IO for real-time
- **Database**: PostgreSQL (documents, versions, collaborations)
- **Port**: 3002

#### Rewrite AI Service
- **Responsibility**: AI-powered content rewriting, processing queues
- **Technology**: Python with FastAPI, TensorFlow/PyTorch
- **Database**: Redis for caching, PostgreSQL for model metadata
- **Port**: 3003

#### Analytics Service
- **Responsibility**: Usage metrics, performance tracking, reporting
- **Technology**: Node.js with Express, ClickHouse for time-series data
- **Database**: PostgreSQL + ClickHouse
- **Port**: 3004

### 2.2 Infrastructure Services

#### API Gateway
- **Technology**: Kong/Express Gateway
- **Features**: 
  - Route management
  - Rate limiting (100 req/min per user)
  - Authentication validation
  - Request/response transformation
  - Metrics collection

#### Load Balancer
- **Technology**: NGINX/HAProxy
- **Strategy**: Round-robin with health checks
- **SSL Termination**: Yes
- **Sticky Sessions**: For WebSocket connections

## 3. API Design

### 3.1 RESTful API Structure

```
BASE_URL: https://api.inciterewrite.com/v1

Authentication Endpoints:
POST   /auth/register          - User registration
POST   /auth/login             - User login
POST   /auth/refresh           - Token refresh
POST   /auth/logout            - User logout
POST   /auth/reset-password    - Password reset

Document Endpoints:
GET    /documents              - List user documents
POST   /documents              - Create new document
GET    /documents/:id          - Get document by ID
PUT    /documents/:id          - Update document
DELETE /documents/:id          - Delete document
GET    /documents/:id/versions - Get document versions
POST   /documents/:id/rewrite  - Request AI rewrite

Analytics Endpoints:
GET    /analytics/usage        - User usage statistics
GET    /analytics/performance  - System performance metrics
POST   /analytics/events       - Track custom events

Admin Endpoints:
GET    /admin/users            - List all users
GET    /admin/system/health    - System health check
GET    /admin/metrics          - System metrics
```

### 3.2 WebSocket Endpoints

```
Real-time Collaboration:
ws://api.inciterewrite.com/ws/documents/:id

Events:
- document:cursor-position
- document:text-change
- document:user-joined
- document:user-left
- document:save-status
- document:rewrite-progress
```

### 3.3 Authentication Flow

```
1. User Login:
   POST /auth/login
   → Returns: { accessToken (JWT, 15min), refreshToken (7 days) }

2. API Request:
   Header: Authorization: Bearer <accessToken>
   → API Gateway validates JWT
   → Forwards to service with user context

3. Token Refresh:
   POST /auth/refresh
   Body: { refreshToken }
   → Returns: New accessToken

4. WebSocket Auth:
   Connection: ws://api.../ws?token=<accessToken>
   → Validates token on connection
```

### 3.4 Rate Limiting Strategy

```
Tier 1 (Free Users):
- 100 requests/hour
- 5 document rewrites/day
- 2 concurrent WebSocket connections

Tier 2 (Pro Users):
- 1000 requests/hour
- 50 document rewrites/day
- 10 concurrent WebSocket connections

Tier 3 (Enterprise):
- 10000 requests/hour
- Unlimited rewrites
- 100 concurrent connections
```

### 3.5 Error Handling Patterns

```javascript
Standard Error Response:
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Document title is required",
    "details": {
      "field": "title",
      "constraint": "required"
    },
    "timestamp": "2024-01-15T10:30:00Z",
    "requestId": "req_123456"
  }
}

Error Categories:
- 400: Client errors (validation, malformed requests)
- 401: Authentication errors
- 403: Authorization errors
- 404: Resource not found
- 429: Rate limit exceeded
- 500: Internal server errors
- 503: Service unavailable
```

## 4. Database Design

### 4.1 Database Strategy

**Primary Database**: PostgreSQL 14+
- ACID compliance for critical data
- JSON columns for flexible document metadata
- Full-text search capabilities
- Robust indexing and query optimization

**Caching Layer**: Redis 6+
- Session storage
- API response caching
- Real-time collaboration state
- Queue management

**Analytics Database**: ClickHouse (Optional)
- Time-series data for analytics
- High-performance aggregations
- Columnar storage for reporting

### 4.2 Core Tables

#### Users Table
```sql
users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  tier VARCHAR(20) DEFAULT 'free',
  email_verified BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login TIMESTAMP,
  metadata JSONB
);
```

#### Documents Table
```sql
documents (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(500) NOT NULL,
  content TEXT,
  content_type VARCHAR(50) DEFAULT 'text/plain',
  status VARCHAR(20) DEFAULT 'draft',
  word_count INTEGER DEFAULT 0,
  language VARCHAR(10) DEFAULT 'en',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  metadata JSONB,
  search_vector tsvector
);
```

#### Document Versions Table
```sql
document_versions (
  id SERIAL PRIMARY KEY,
  document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  content TEXT NOT NULL,
  change_summary TEXT,
  created_by INTEGER REFERENCES users(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  metadata JSONB,
  UNIQUE(document_id, version_number)
);
```

### 4.3 Indexing Strategy

```sql
-- Performance indexes
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_updated_at ON documents(updated_at DESC);
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_document_versions_document_id ON document_versions(document_id);

-- Composite indexes
CREATE INDEX idx_documents_user_status ON documents(user_id, status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
```

## 5. Caching Strategy

### 5.1 Redis Configuration

```
Cache Layers:
1. API Response Cache (TTL: 5 minutes)
   - Document metadata
   - User profiles
   - System configuration

2. Session Cache (TTL: 24 hours)
   - JWT refresh tokens
   - User sessions
   - Temporary authentication data

3. Real-time State (TTL: 1 hour)
   - Active document collaborations
   - User presence indicators
   - WebSocket connection mappings

4. Queue Management (No TTL)
   - AI rewrite job queues
   - Email notification queues
   - Background processing tasks
```

### 5.2 Cache Invalidation

```javascript
Patterns:
- Write-through: Update cache when database changes
- Time-based: TTL expiration
- Event-driven: Invalidate on specific actions
- Manual: Admin controls for cache clearing
```

## 6. Security Architecture

### 6.1 Authentication & Authorization

#### JWT Strategy
```javascript
Access Token Structure:
{
  "sub": "user_id",
  "email": "user@example.com",
  "tier": "pro",
  "permissions": ["document:read", "document:write"],
  "iat": 1642248000,
  "exp": 1642248900, // 15 minutes
  "iss": "inciterewrite.com"
}

Refresh Token:
- Stored in httpOnly cookie
- 7-day expiration
- Rotating tokens for enhanced security
```

#### Password Security
```javascript
bcrypt Configuration:
- Salt rounds: 12
- Pepper: Environment-specific secret
- Password requirements:
  - Minimum 8 characters
  - At least 1 uppercase letter
  - At least 1 lowercase letter
  - At least 1 number
  - At least 1 special character
```

### 6.2 API Key Management

```javascript
API Key Structure:
- Format: ik_live_[32_char_random_string]
- Scoped permissions per key
- Rate limiting per key
- Audit logging for all key usage
- Automatic key rotation (optional)

Storage:
- Hash API keys in database (SHA-256)
- Never store plain text keys
- Environment-specific key prefixes
```

### 6.3 CORS & Security Headers

```javascript
CORS Configuration:
allowedOrigins: [
  'https://app.inciterewrite.com',
  'https://admin.inciterewrite.com'
],
credentials: true,
maxAge: 86400

Security Headers:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security: max-age=31536000
- Content-Security-Policy: default-src 'self'
```

## 7. Performance & Scalability

### 7.1 Performance Targets

```
Response Time Targets:
- API responses: < 200ms (95th percentile)
- Document loading: < 500ms
- Real-time collaboration: < 50ms latency
- AI rewriting: < 30 seconds

Throughput Targets:
- 1000 concurrent users
- 10,000 API requests/minute
- 500 concurrent document editing sessions
```

### 7.2 Scalability Strategy

```
Horizontal Scaling:
- Stateless service design
- Load balancer distribution
- Database read replicas
- CDN for static assets

Auto-scaling Triggers:
- CPU usage > 70%
- Memory usage > 80%
- Queue depth > 100 jobs
- Response time > 500ms
```

## 8. Deployment Architecture

### 8.1 Container Strategy

```dockerfile
# Each service in separate container
# Multi-stage builds for optimization
# Health checks for container orchestration
# Environment-specific configurations
```

### 8.2 Infrastructure

```
Production Environment:
- Kubernetes cluster (3 nodes minimum)
- PostgreSQL cluster with read replicas
- Redis cluster for high availability
- NGINX ingress controller
- Prometheus + Grafana monitoring
```

## 9. Monitoring & Observability

### 9.1 Logging Strategy

```javascript
Log Levels:
- ERROR: System errors, exceptions
- WARN: Performance issues, deprecated APIs
- INFO: User actions, system events
- DEBUG: Detailed execution flow

Structured Logging:
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "document-service",
  "userId": "123",
  "action": "document:create",
  "duration": 145,
  "metadata": {...}
}
```

### 9.2 Metrics Collection

```
Business Metrics:
- User registration rate
- Document creation rate
- AI rewrite success rate
- User engagement metrics

Technical Metrics:
- Response time percentiles
- Error rate by service
- Database query performance
- Cache hit rates
```

## 10. Disaster Recovery

### 10.1 Backup Strategy

```
Database Backups:
- Daily automated backups
- Point-in-time recovery (7 days)
- Cross-region backup replication
- Monthly backup testing

Application State:
- Redis snapshots every 6 hours
- Configuration backups
- Code repository mirrors
```

### 10.2 Recovery Procedures

```
RTO (Recovery Time Objective): 4 hours
RPO (Recovery Point Objective): 1 hour

Failure Scenarios:
- Single service failure: Auto-restart, circuit breaker
- Database failure: Failover to read replica
- Complete system failure: Multi-region deployment
```

## 11. Future Considerations

### 11.1 Planned Enhancements

- GraphQL API layer for flexible queries
- Event-driven architecture with Kafka
- Machine learning model serving infrastructure
- Multi-tenant data isolation
- Advanced real-time collaboration features

### 11.2 Technology Evolution

- Microservices mesh (Istio/Linkerd)
- Serverless functions for specific tasks
- Advanced caching strategies (CDN, edge computing)
- AI/ML pipeline automation

---

## Architecture Decision Records (ADRs)

### ADR-001: Microservices vs Monolith
- **Status**: Accepted
- **Decision**: Microservices architecture
- **Rationale**: Scalability requirements and team autonomy
- **Consequences**: Increased operational complexity, better fault isolation

### ADR-002: Database Choice
- **Status**: Accepted  
- **Decision**: PostgreSQL as primary database
- **Rationale**: ACID compliance, JSON support, full-text search
- **Consequences**: Single database technology, proven reliability

### ADR-003: Real-time Communication
- **Status**: Accepted
- **Decision**: WebSockets with Socket.IO
- **Rationale**: Low latency for collaboration features
- **Consequences**: Stateful connections, scaling complexity

### ADR-004: Authentication Strategy
- **Status**: Accepted
- **Decision**: JWT with refresh tokens
- **Rationale**: Stateless authentication, secure token rotation
- **Consequences**: Token management overhead, enhanced security