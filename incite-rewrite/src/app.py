import os
import hashlib
import json
import sqlite3
import time
import logging
from datetime import datetime
from io import BytesIO
from functools import wraps
from collections import defaultdict
from flask import Flask, request, jsonify, render_template_string
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv
from processor import DocumentProcessor
from citations import CitationExtractor
from courtlistener import CourtListenerClient
from storage import ResultStore

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 52428800))

processor = DocumentProcessor()
extractor = CitationExtractor()
courtlistener = CourtListenerClient(os.getenv('COURTLISTENER_API_TOKEN'))
storage = ResultStore()

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline'"
    return response

request_counts = defaultdict(list)

def rate_limit(max_requests=10, window=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            request_counts[ip] = [t for t in request_counts[ip] if now - t < window]
            
            if len(request_counts[ip]) >= max_requests:
                return jsonify({'error': 'Rate limit exceeded. Try again later.'}), 429
            
            request_counts[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/analyze', methods=['POST'])
@rate_limit(max_requests=10, window=60)
def analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        file_bytes = file.read()
        file_buffer = BytesIO(file_bytes)
        hash_id = hashlib.sha256(file_bytes).hexdigest()
        
        # Check cache
        cached = storage.retrieve(hash_id)
        if cached:
            session_token = storage.create_session(hash_id)
            cached['session_token'] = session_token
            if 'hash_id' in cached:
                del cached['hash_id']
            return jsonify(cached)
        
        # Validate file extension
        ext = os.path.splitext(file.filename)[1].lower()
        allowed = ['.pdf', '.docx', '.txt']
        if ext not in allowed:
            return jsonify({'error': f'File type {ext} not supported. Use PDF, DOCX, or TXT'}), 400
            
        # Extract text
        text = processor.extract_text(file_buffer, ext)
        
        if len(text) < 100:
            return jsonify({'error': 'Document too short or no text extracted'}), 400
        
        # Extract citations
        citations = extractor.extract_citations(text)
        if not citations:
            return jsonify({
                'session_token': None,
                'citations_found': False,
                'message': 'No legal citations found in document'
            })
        
        logger.info(f'Processing document: {hash_id[:8]}... ({len(file_bytes)} bytes)')
        
        # Verify citations with CourtListener
        results = courtlistener.verify_citations(citations)
        
        threshold = 70
        verified_count = sum(1 for r in results if r.get('confidence', 0) >= threshold)
        suspicious_count = sum(1 for r in results if 0 < r.get('confidence', 0) < threshold)
        not_found_count = sum(1 for r in results if r.get('confidence', 0) == 0)
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_citations': len(citations),
            'verified': verified_count,
            'suspicious': suspicious_count,
            'not_found': not_found_count,
            'default_threshold': threshold,
            'citations': results
        }
        
        logger.info(f'Verified {len(citations)} citations: {verified_count} verified, {suspicious_count} suspicious, {not_found_count} not found')
        
        # Store results and create session
        storage.store(hash_id, response)
        session_token = storage.create_session(hash_id)
        response['session_token'] = session_token
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f'Processing error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/verify', methods=['POST'])
@rate_limit(max_requests=10, window=60)
def verify():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        file_bytes = file.read()
        hash_id = hashlib.sha256(file_bytes).hexdigest()
        
        result = storage.check_hash_exists(hash_id)
        if result['exists']:
            return jsonify({
                'verified': True,
                'message': f"Document was previously processed on {result['created_at']}"
            })
        else:
            return jsonify({
                'verified': False,
                'message': 'Document has never been processed by this system'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results/<token>', methods=['GET'])
def get_results(token):
    hash_id = storage.get_hash_from_token(token)
    if not hash_id:
        return jsonify({'error': 'Invalid or expired token'}), 404
    
    results = storage.retrieve(hash_id)
    if not results:
        return jsonify({'error': 'Results not found'}), 404
    return jsonify(results)

@app.route('/view/<token>')
def view_results(token):
    hash_id = storage.get_hash_from_token(token)
    if not hash_id:
        return '<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1>Session expired or invalid</h1><p>Results are only available for 1 hour after processing.</p><a href="/">Process another document</a></body></html>', 404
    
    results = storage.retrieve(hash_id)
    if not results:
        return '<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1>Results not found</h1><a href="/">Process another document</a></body></html>', 404
    
    return render_template_string(VIEW_TEMPLATE, results=results)

@app.route('/delete/<hash_id>', methods=['POST'])
def delete_results(hash_id):
    conn = sqlite3.connect('results.db')
    conn.execute('DELETE FROM results WHERE hash_id = ?', (hash_id,))
    affected = conn.total_changes
    conn.commit()
    conn.close()
    
    if affected > 0:
        logger.info(f'Deleted results for hash: {hash_id[:8]}...')
        return jsonify({'message': 'Results deleted', 'hash_id': hash_id})
    else:
        return jsonify({'error': 'Results not found'}), 404

@app.route('/robots.txt')
def robots():
    return '''User-agent: *
Disallow: /view/
Disallow: /results/
Allow: /
''', 200, {'Content-Type': 'text/plain'}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'courtlistener_configured': bool(os.getenv('COURTLISTENER_API_TOKEN'))
    })

@app.route('/', methods=['GET'])
def index():
    return render_template_string(INDEX_TEMPLATE)

VIEW_TEMPLATE = '''
<html>
<head>
    <title>Citation Results</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f8f9fa; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .content { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .verified { color: #28a745; }
        .not-found { color: #dc3545; }
        .suspicious { color: #ff9800; }
        .summary { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .citation-item { padding: 10px 0; border-bottom: 1px solid #dee2e6; }
        .citation-item:last-child { border-bottom: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Citation Verification Results</h1>
    </div>
    <div class="content">
        <div class="summary">
            <h3>Summary</h3>
            <p>Processed: {{ results.get('timestamp', 'Unknown') }}</p>
            <p>Total Citations: {{ results.total_citations }}</p>
            <p><span class="verified">Verified: {{ results.get('verified', 0) }}</span> | 
               <span class="suspicious">Suspicious: {{ results.get('suspicious', 0) }}</span> |
               <span class="not-found">Not Found: {{ results.get('not_found', 0) }}</span></p>
        </div>
        <h3>Citation Details</h3>
        {% for c in results.citations %}
        <div class="citation-item">
            <strong>{{ c.citation }}</strong><br>
            {% set confidence = c.get('confidence', 0) %}
            {% if confidence >= results.get('default_threshold', 70) %}
                <span class="verified">✓ Verified ({{ confidence }}%)</span>
            {% elif confidence > 0 %}
                <span class="suspicious">⚠ Below threshold ({{ confidence }}%)</span>
            {% else %}
                <span class="not-found">✗ Not Found</span>
            {% endif %}
            
            {% if c.get('case_name') %} - {{ c.case_name }}{% endif %}
            {% if c.get('url') %} <a href="{{ c.url }}" target="_blank">[View on CourtListener]</a>{% endif %}
        </div>
        {% endfor %}
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
            <a href="/" style="text-decoration: none; color: #667eea;">← Check another document</a>
        </div>
    </div>
</body>
</html>
'''

INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Legal Citation Verifier</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f8f9fa; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }
        .header h1 { margin: 0; font-weight: 300; }
        .notice { background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .disclaimer { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .upload-box { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .verify-box { background: #e8f4f8; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .file-drop { border: 2px dashed #007bff; border-radius: 8px; padding: 60px; text-align: center; transition: all 0.3s; cursor: pointer; }
        .file-drop:hover { background: #f0f8ff; border-color: #0056b3; }
        .file-drop.dragover { background: #e7f3ff; border-color: #0056b3; }
        button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 40px; border-radius: 25px; font-size: 16px; cursor: pointer; margin-top: 20px; }
        button:hover { transform: translateY(-2px); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .results { background: white; padding: 30px; border-radius: 10px; margin-top: 30px; display: none; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .verified { color: #28a745; font-weight: bold; }
        .not-found { color: #dc3545; font-weight: bold; }
        .loading { text-align: center; color: #007bff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Legal Citation Verifier</h1>
        <p>Verify citations against CourtListener database</p>
    </div>
    
    <div class="notice">
        <strong>Privacy Notice:</strong> Your document is processed in memory only and immediately deleted. 
        Only citation results are stored, accessible via temporary session link.
    </div>
    
    <div class="disclaimer">
        <strong>Disclaimer:</strong> This tool verifies citations against CourtListener's database. 
        Not all valid cases may be in their database. Manual verification recommended for critical documents.
    </div>
    
    <div class="upload-box">
        <form id="uploadForm" enctype="multipart/form-data">
            <div class="file-drop" id="fileDrop">
                <p style="font-size: 48px; margin: 0;">📄</p>
                <p style="font-size: 18px; color: #6c757d;">Drop document here or click to select</p>
                <p style="color: #6c757d;">Supports PDF, DOCX, and TXT files up to 50MB</p>
                <input type="file" id="file" accept=".pdf,.docx,.txt" style="display: none;" required>
            </div>
            <center><button type="submit" id="submitBtn">Verify Citations</button></center>
        </form>
    </div>
    
    <div class="verify-box">
        <h3>Verify Previous Document</h3>
        <p>Upload a document to check if it was previously processed</p>
        <form id="verifyForm" enctype="multipart/form-data">
            <input type="file" id="verifyFile" accept=".pdf,.docx,.txt" required>
            <button type="submit">Verify Document</button>
        </form>
        <div id="verifyResult"></div>
    </div>
    
    <div id="results" class="results"></div>
    
    <script>
        const fileDrop = document.getElementById('fileDrop');
        const fileInput = document.getElementById('file');
        const form = document.getElementById('uploadForm');
        const resultsDiv = document.getElementById('results');
        const submitBtn = document.getElementById('submitBtn');
        
        fileDrop.onclick = () => fileInput.click();
        
        fileDrop.ondragover = (e) => {
            e.preventDefault();
            fileDrop.classList.add('dragover');
        };
        
        fileDrop.ondragleave = () => fileDrop.classList.remove('dragover');
        
        fileDrop.ondrop = (e) => {
            e.preventDefault();
            fileDrop.classList.remove('dragover');
            fileInput.files = e.dataTransfer.files;
            updateFileDisplay();
        };
        
        fileInput.onchange = updateFileDisplay;
        
        function updateFileDisplay() {
            if (fileInput.files[0]) {
                fileDrop.innerHTML = '<p style="font-size: 48px; margin: 0;">✅</p><p>Selected: ' + fileInput.files[0].name + '</p>';
            }
        }
        
        form.onsubmit = async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
            resultsDiv.style.display = 'block';
            resultsDiv.innerHTML = '<div class="loading">Extracting citations and verifying with CourtListener...</div>';
            
            let dots = 0;
            const progressInterval = setInterval(() => {
                dots = (dots + 1) % 4;
                const dotStr = '.'.repeat(dots);
                resultsDiv.innerHTML = '<div class="loading">Extracting citations and verifying with CourtListener' + dotStr + '</div>';
            }, 500);
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                displayResults(data);
            } catch (error) {
                resultsDiv.innerHTML = '<p style="color: red;">Error: ' + error + '</p>';
            } finally {
                clearInterval(progressInterval);
            }
            
            submitBtn.disabled = false;
            submitBtn.textContent = 'Verify Citations';
        };
        
        document.getElementById('verifyForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData();
            formData.append('file', document.getElementById('verifyFile').files[0]);
            
            const response = await fetch('/verify', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            const resultDiv = document.getElementById('verifyResult');
            if (data.verified) {
                resultDiv.innerHTML = '<p style="color: green;">' + data.message + '</p>';
            } else {
                resultDiv.innerHTML = '<p style="color: red;">' + data.message + '</p>';
            }
        };
        
        function displayResults(data) {
            if (data.error) {
                resultsDiv.innerHTML = '<p style="color: red;">Error: ' + data.error + '</p>';
                return;
            }
            
            if (data.citations_found === false) {
                resultsDiv.innerHTML = '<p>No legal citations found in document.</p>';
                return;
            }
            
            window.verificationData = data;
            
            let html = '<h2>Verification Results</h2>';
            html += '<p><strong>Session ID:</strong> ' + data.session_token.substring(0, 12) + '...</p>';
            html += '<p><a href="/view/' + data.session_token + '" target="_blank">View results (expires in 1 hour)</a></p>';
            
            html += '<div style="margin: 20px 0; padding: 15px; background: #fff3cd; border-radius: 5px;">';
            html += '<label><strong>Confidence Threshold:</strong> ';
            html += '<input type="range" id="threshold" min="50" max="100" value="70" style="width: 200px;">';
            html += ' <span id="thresholdValue">70</span>%</label>';
            html += '<p style="font-size: 12px; margin: 5px 0;">Adjust to be more strict (higher) or lenient (lower)</p>';
            html += '</div>';
            
            html += '<div id="summaryDiv">' + generateSummary(data.citations, 70) + '</div>';
            html += '<h3>Citation Details:</h3>';
            html += '<ol id="citationList">' + generateCitationList(data.citations, 70) + '</ol>';
            
            resultsDiv.innerHTML = html;
            
            document.getElementById('threshold').oninput = function() {
                const threshold = parseInt(this.value);
                document.getElementById('thresholdValue').textContent = threshold;
                document.getElementById('summaryDiv').innerHTML = generateSummary(window.verificationData.citations, threshold);
                document.getElementById('citationList').innerHTML = generateCitationList(window.verificationData.citations, threshold);
            };
        }
        
        function generateSummary(citations, threshold) {
            const verified = citations.filter(c => c.confidence >= threshold).length;
            const suspicious = citations.filter(c => c.confidence > 0 && c.confidence < threshold).length;
            const notFound = citations.filter(c => c.confidence === 0).length;
            
            let html = '<div style="padding: 15px; background: #f8f9fa; border-radius: 5px;">';
            html += '<strong>Summary at ' + threshold + '% threshold:</strong> ';
            html += citations.length + ' citations found | ';
            html += '<span class="verified">' + verified + ' verified</span> | ';
            html += '<span style="color: #ff9800;">' + suspicious + ' below threshold</span> | ';
            html += '<span class="not-found">' + notFound + ' not found</span>';
            html += '</div>';
            return html;
        }
        
        function generateCitationList(citations, threshold) {
            let html = '';
            citations.forEach(c => {
                html += '<li>';
                html += c.citation;
                
                if (c.confidence >= threshold) {
                    html += ' <span class="verified">✓ Verified (' + c.confidence + '%)</span>';
                } else if (c.confidence > 0) {
                    html += ' <span style="color: #ff9800;">⚠ Below threshold (' + c.confidence + '%)</span>';
                } else {
                    html += ' <span class="not-found">✗ Not Found</span>';
                }
                
                if (c.case_name) html += '<br>Case: ' + c.case_name;
                if (c.url) html += ' <a href="' + c.url + '" target="_blank">[View]</a>';
                html += '</li>';
            });
            return html;
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)