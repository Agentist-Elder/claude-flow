import os
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO
from flask import Flask, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv
from processor import DocumentProcessor
from citations import CitationExtractor
from courtlistener import CourtListenerClient
from storage import ResultStore

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 52428800))

processor = DocumentProcessor()
extractor = CitationExtractor()
courtlistener = CourtListenerClient(os.getenv('COURTLISTENER_API_TOKEN'))
storage = ResultStore()

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read file into memory
        file_bytes = file.read()
        file_buffer = BytesIO(file_bytes)
        
        # Generate hash from original bytes
        hash_id = hashlib.sha256(file_bytes).hexdigest()
        
        # Check if already processed
        cached = storage.retrieve(hash_id)
        if cached:
            return jsonify(cached)
        
        # Extract text
        ext = os.path.splitext(file.filename)[1].lower()
        text = processor.extract_text(file_buffer, ext)
        
        # Extract citations
        citations = extractor.extract_citations(text)
        if not citations:
            return jsonify({
                'hash_id': hash_id,
                'citations_found': False,
                'message': 'No legal citations found in document'
            })
        
        # Verify citations
        results = courtlistener.verify_citations(citations)
        
        # Prepare response
        response = {
            'hash_id': hash_id,
            'timestamp': datetime.utcnow().isoformat(),
            'total_citations': len(citations),
            'verified': sum(1 for r in results if r['found']),
            'not_found': sum(1 for r in results if not r['found']),
            'citations': results
        }
        
        # Store results
        storage.store(hash_id, response)
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results/<hash_id>', methods=['GET'])
def get_results(hash_id):
    results = storage.retrieve(hash_id)
    if not results:
        return jsonify({'error': 'Results not found'}), 404
    return jsonify(results)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'courtlistener_configured': bool(os.getenv('COURTLISTENER_API_TOKEN'))
    })

@app.route('/', methods=['GET'])
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Citation Verifier</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
            .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; }
            .results { margin-top: 30px; }
            .verified { color: green; }
            .not-found { color: red; }
        </style>
    </head>
    <body>
        <h1>Legal Citation Verifier</h1>
        <div class="upload-area">
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" id="file" accept=".pdf,.docx,.txt" required>
                <button type="submit">Verify Citations</button>
            </form>
        </div>
        <div id="results" class="results"></div>
        <script>
            document.getElementById('uploadForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData();
                formData.append('file', document.getElementById('file').files[0]);
                
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                const resultsDiv = document.getElementById('results');
                
                if (data.error) {
                    resultsDiv.innerHTML = '<p style="color:red">Error: ' + data.error + '</p>';
                } else if (!data.citations_found) {
                    resultsDiv.innerHTML = '<p>No citations found in document</p>';
                } else {
                    let html = '<h2>Results</h2>';
                    html += '<p>Document Hash: ' + data.hash_id + '</p>';
                    html += '<p>Total: ' + data.total_citations + ' | Verified: ' + data.verified + ' | Not Found: ' + data.not_found + '</p>';
                    html += '<ul>';
                    data.citations.forEach(c => {
                        const cls = c.found ? 'verified' : 'not-found';
                        html += '<li class="' + cls + '">' + c.citation + ' - ' + (c.found ? 'Verified' : 'Not Found') + '</li>';
                    });
                    html += '</ul>';
                    resultsDiv.innerHTML = html;
                }
            };
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)