# InciteRewrite Deployment Guide

## ⚠️ PRODUCTION DEPLOYMENT WARNING

**CRITICAL:** This platform is **NOT CURRENTLY READY** for production deployment. 

**Current Production Readiness: 52.5%**

Please complete the [Production Readiness Action Plan](#production-readiness-action-plan) before deploying.

---

## Prerequisites

### System Requirements
- **Python:** 3.12+ (tested with 3.12.1)
- **Operating System:** Linux (Ubuntu 20.04+ recommended)
- **Memory:** Minimum 2GB RAM (4GB+ recommended)
- **Storage:** Minimum 1GB available space
- **Database:** SQLite (built-in) or PostgreSQL (for production)

### Required Dependencies
```bash
# Core dependencies
flask>=2.3.0
flask-cors>=4.0.0
gunicorn>=20.1.0
waitress>=2.1.0
python-dotenv>=1.0.0

# Testing dependencies (for validation)
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-html>=3.1.0
```

---

## Development Environment Setup

### 1. Clone and Setup
```bash
# Clone repository
git clone <repository-url>
cd incite-rewrite

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### 2. Environment Configuration
```bash
# Create .env file
cat > .env << EOF
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_PATH=./data/development.db
LOG_LEVEL=INFO
EOF
```

### 3. Database Initialization
```bash
# Create data directory
mkdir -p data

# Initialize database (currently requires manual setup)
python -c "
from src.auth.authentication import AuthenticationManager
from src.utils.text_processing import TextProcessor
auth = AuthenticationManager('./data/development.db')
text = TextProcessor('./data/development.db')
print('Database initialized')
"
```

### 4. Run Development Server
```bash
# Using Flask development server
export FLASK_APP=src.api.endpoints:create_app
flask run --host=0.0.0.0 --port=5000

# Or using Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "src.api.endpoints:create_app()"
```

---

## Testing and Validation

### Run Test Suite
```bash
# Full test suite with coverage
make test-coverage

# Specific test categories
make test-unit          # Unit tests
make test-integration   # Integration tests
make test-performance   # Performance tests
make test-e2e          # End-to-end tests

# Security validation (currently no tests)
make test-security
```

### Validation Checklist
- [ ] All tests pass (currently 59.3% pass rate ❌)
- [ ] 90%+ code coverage (currently unable to measure ❌)
- [ ] Performance benchmarks meet targets (partial ⚠️)
- [ ] Security validation complete (not implemented ❌)
- [ ] Database schema consistent (currently failing ❌)

---

## Production Deployment (DO NOT USE - FOR REFERENCE ONLY)

### ⚠️ Current Blocking Issues

**Before attempting production deployment, resolve:**

1. **Database Schema Issues**
   ```
   Error: no such table: users
   Error: no such table: text_documents  
   Error: no such table: query_log
   ```

2. **Test Suite Failures**
   - 31 failed tests, 19 errors
   - 59.3% pass rate (target: 90%+)
   - Critical integration failures

3. **Security Vulnerabilities**
   - No input sanitization (XSS vulnerability)
   - Missing rate limiting
   - Error message information disclosure

### Production Environment Setup (When Ready)

#### 1. Environment Configuration
```bash
# Production .env file
cat > .env << EOF
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
DATABASE_PATH=/var/lib/incite/production.db
LOG_LEVEL=WARNING
GUNICORN_WORKERS=4
GUNICORN_TIMEOUT=30
EOF
```

#### 2. Database Setup
```bash
# Create production database directory
sudo mkdir -p /var/lib/incite
sudo chown app:app /var/lib/incite

# Initialize production database
python scripts/init_production_db.py  # This script needs to be created
```

#### 3. Systemd Service (Ubuntu/CentOS)
```ini
# /etc/systemd/system/incite-rewrite.service
[Unit]
Description=InciteRewrite Text Processing API
After=network.target

[Service]
Type=forking
User=app
Group=app
WorkingDirectory=/opt/incite-rewrite
Environment=PATH=/opt/incite-rewrite/venv/bin
ExecStart=/opt/incite-rewrite/venv/bin/gunicorn \
          --bind 127.0.0.1:5000 \
          --workers 4 \
          --timeout 30 \
          --access-logfile /var/log/incite/access.log \
          --error-logfile /var/log/incite/error.log \
          "src.api.endpoints:create_app()"
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 4. Nginx Configuration
```nginx
# /etc/nginx/sites-available/incite-rewrite
server {
    listen 80;
    server_name your-domain.com;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Request size limits
        client_max_body_size 10M;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Rate limiting (requires nginx rate limiting module)
    location /api/auth {
        limit_req zone=auth burst=5 nodelay;
        proxy_pass http://127.0.0.1:5000;
        # ... other proxy settings
    }
}
```

---

## Docker Deployment (Not Currently Available)

**Status:** Docker configuration not implemented

### Required Docker Files (To Be Created)

```dockerfile
# Dockerfile (needs creation)
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements*.txt ./
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -s /bin/bash app && chown -R app:app /app
USER app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start command
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "src.api.endpoints:create_app()"]
```

```yaml
# docker-compose.yml (needs creation)
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - DATABASE_PATH=/app/data/production.db
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - app
    restart: unless-stopped
```

---

## Monitoring and Logging

### Application Monitoring (To Be Implemented)

```python
# Add to application (needs implementation)
import logging
import time
from flask import request, g

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Performance monitoring middleware
@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request  
def after_request(response):
    duration = time.time() - g.start_time
    
    # Log slow requests
    if duration > 1.0:
        app.logger.warning(f"Slow request: {request.method} {request.path} - {duration:.3f}s")
    
    # Add performance metrics
    response.headers['X-Response-Time'] = f"{duration:.3f}"
    return response
```

### Health Check Endpoint (Implemented)
```bash
# Check application health
curl http://your-domain.com/health

# Expected response:
{
  "status": "healthy",
  "timestamp": 1698765432.123,
  "version": "1.0.0"
}
```

### Log Files (To Be Configured)
```bash
# Application logs
/var/log/incite/application.log
/var/log/incite/error.log
/var/log/incite/access.log

# System logs
/var/log/incite/security.log
/var/log/incite/performance.log
```

---

## Security Considerations

### Current Security Status ❌
- **Input Sanitization:** Not implemented (XSS vulnerability)
- **Rate Limiting:** Not implemented (brute force vulnerability)  
- **Error Handling:** Exposes internal information
- **Authentication:** Basic implementation only
- **Security Testing:** No tests implemented

### Pre-Production Security Checklist
- [ ] Implement input sanitization for all user inputs
- [ ] Add rate limiting to authentication endpoints
- [ ] Fix error message information disclosure
- [ ] Implement security headers
- [ ] Add security monitoring and logging
- [ ] Complete security test suite
- [ ] Perform penetration testing

### Required Security Improvements
```python
# Example security implementations needed:

# 1. Input sanitization
import html
def sanitize_input(text: str) -> str:
    return html.escape(text.strip())

# 2. Rate limiting  
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    pass

# 3. Security headers
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response
```

---

## Production Readiness Action Plan

### Phase 1: Critical Fixes (1-2 weeks)
1. **Fix Database Schema Issues**
   - [ ] Resolve table creation problems across all environments
   - [ ] Fix test database initialization  
   - [ ] Ensure consistent schema

2. **Stabilize Test Suite**
   - [ ] Achieve minimum 85% test pass rate (currently 59.3%)
   - [ ] Fix all integration test failures
   - [ ] Resolve E2E test issues

3. **Implement Basic Security**
   - [ ] Add input sanitization
   - [ ] Implement rate limiting
   - [ ] Fix error message disclosure

### Phase 2: Security & Performance (2-3 weeks)
4. **Comprehensive Security Implementation**
   - [ ] Complete security test suite
   - [ ] Implement security headers
   - [ ] Add security monitoring

5. **Performance Optimization**
   - [ ] Fix concurrent operation issues
   - [ ] Optimize memory usage
   - [ ] Implement proper connection pooling

### Phase 3: Production Infrastructure (1-2 weeks)
6. **Deployment Infrastructure**
   - [ ] Create Docker configuration
   - [ ] Implement database migrations
   - [ ] Set up monitoring and logging
   - [ ] Create backup procedures

7. **Final Validation**
   - [ ] 90%+ test pass rate
   - [ ] Complete security validation
   - [ ] Load testing validation
   - [ ] Production environment testing

---

## Support and Maintenance

### Backup Procedures (To Be Implemented)
```bash
# Database backup
sqlite3 /var/lib/incite/production.db ".backup /backup/incite-$(date +%Y%m%d-%H%M%S).db"

# Log rotation
logrotate /etc/logrotate.d/incite-rewrite
```

### Update Procedures
```bash
# Application updates
git pull origin main
pip install -r requirements.txt
sudo systemctl restart incite-rewrite
```

### Troubleshooting
```bash
# Check service status
sudo systemctl status incite-rewrite

# View logs
sudo tail -f /var/log/incite/error.log

# Test database connectivity
python -c "from src.database.connection import DatabaseManager; print(DatabaseManager().health_check())"
```

---

## Conclusion

The InciteRewrite platform **requires significant work** before production deployment. While the core architecture is sound and follows London School TDD principles, **critical issues in database initialization, security, and test stability** must be resolved.

**Estimated Timeline to Production Readiness: 4-6 weeks**

**Do not attempt production deployment** until all items in the Production Readiness Action Plan are completed and validated.

For development and testing purposes, the current setup can be used with the understanding that it has known limitations and security vulnerabilities.