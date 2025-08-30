"""
API routes for InciteRewrite legal citation verification system.
Privacy-first design with session-based access.
"""
from flask import Blueprint, request, jsonify, session, current_app
import hashlib
import json
from datetime import datetime
import logging

from src.database.models import SessionManager, ResultsManager
from src.citation.processor import citation_processor
from src.citation.courtlistener import courtlistener_service
from src.utils.security import require_session, validate_document_size
from src.utils.response import create_response, create_error_response

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/analyze', methods=['POST'])
def analyze_document():
    """
    Analyze document for legal citations.
    Returns session ID for privacy-first access to results.
    """
    try:
        # Validate request
        if not request.is_json:
            return create_error_response("Content-Type must be application/json", 400)
        
        data = request.get_json()
        
        if 'document' not in data:
            return create_error_response("Missing 'document' field", 400)
        
        document_text = data['document']
        
        # Validate document size
        if not validate_document_size(document_text):
            return create_error_response("Document exceeds maximum size limit", 413)
        
        # Generate document hash for audit trail
        document_hash = hashlib.sha256(document_text.encode('utf-8')).hexdigest()
        
        # Create new session
        session_id = SessionManager.create_session(document_hash)
        
        # Store session ID in Flask session
        session['current_session_id'] = session_id
        
        # Extract citations
        citations = citation_processor.extract_citations(document_text)
        
        logger.info(f"Analysis started for session {session_id}, found {len(citations)} citations")
        
        return create_response({
            'session_id': session_id,
            'citations_found': len(citations),
            'status': 'analysis_complete',
            'message': 'Document analyzed successfully. Use session_id to verify citations.'
        })
        
    except Exception as e:
        logger.error(f"Error in analyze_document: {e}")
        return create_error_response("Internal server error during analysis", 500)

@api_bp.route('/verify', methods=['POST'])
@require_session
def verify_citations():
    """
    Verify citations found in the analyzed document.
    Requires valid session from analyze step.
    """
    try:
        data = request.get_json() if request.is_json else {}
        session_id = data.get('session_id') or session.get('current_session_id')
        
        if not session_id:
            return create_error_response("Missing session_id", 400)
        
        # Verify session exists and is valid
        session_data = SessionManager.get_session(session_id)
        if not session_data:
            return create_error_response("Invalid or expired session", 404)
        
        # Check if we already have results for this session
        existing_results = ResultsManager.get_results(session_id)
        if existing_results:
            return create_response({
                'session_id': session_id,
                'status': 'already_verified',
                'message': 'Citations already verified. Use /results endpoint to retrieve.'
            })
        
        # Get document hash to re-extract citations
        document_hash = session_data['document_hash']
        
        # Since we don't store document content, we need the client to provide it again
        # or we extract from the original analysis stored in session
        if 'document' not in data:
            return create_error_response("Document content required for verification", 400)
        
        document_text = data['document']
        
        # Verify document hash matches
        provided_hash = hashlib.sha256(document_text.encode('utf-8')).hexdigest()
        if provided_hash != document_hash:
            return create_error_response("Document hash mismatch - document may have been modified", 403)
        
        # Re-extract citations
        citations = citation_processor.extract_citations(document_text)
        
        if not citations:
            # Store empty results
            result_id = ResultsManager.store_result(
                session_id=session_id,
                document_hash=document_hash,
                citations_found=0,
                citations_verified=0,
                confidence_score=0.0,
                verification_details="No citations found in document"
            )
            
            return create_response({
                'session_id': session_id,
                'status': 'verification_complete',
                'citations_found': 0,
                'citations_verified': 0,
                'overall_confidence': 0.0
            })
        
        # Verify citations with CourtListener
        verified_count = 0
        total_confidence = 0.0
        verification_details = []
        
        for citation in citations:
            try:
                # Verify with CourtListener
                verification_result = courtlistener_service.verify_citation(
                    citation.text, citation.citation_type
                )
                
                is_verified = verification_result['verified']
                confidence = verification_result['confidence']
                
                if is_verified:
                    verified_count += 1
                
                total_confidence += confidence
                
                verification_details.append({
                    'citation': citation.text,
                    'type': citation.citation_type,
                    'verified': is_verified,
                    'confidence': confidence,
                    'best_match': verification_result.get('best_match', {}),
                    'error': verification_result.get('error')
                })
                
            except Exception as e:
                logger.error(f"Error verifying citation {citation.text}: {e}")
                verification_details.append({
                    'citation': citation.text,
                    'type': citation.citation_type,
                    'verified': False,
                    'confidence': 0.0,
                    'error': str(e)
                })
        
        # Calculate overall confidence
        overall_confidence = total_confidence / len(citations) if citations else 0.0
        
        # Store results
        result_id = ResultsManager.store_result(
            session_id=session_id,
            document_hash=document_hash,
            citations_found=len(citations),
            citations_verified=verified_count,
            confidence_score=overall_confidence,
            verification_details=json.dumps(verification_details)
        )
        
        # Store individual citation details
        for detail in verification_details:
            ResultsManager.store_citation_detail(
                result_id=result_id,
                citation_text=detail['citation'],
                citation_type=detail['type'],
                verified=detail['verified'],
                confidence_score=detail['confidence'],
                courtlistener_match=json.dumps(detail.get('best_match', {})),
                error_message=detail.get('error')
            )
        
        logger.info(f"Verification complete for session {session_id}: {verified_count}/{len(citations)} verified")
        
        return create_response({
            'session_id': session_id,
            'status': 'verification_complete',
            'citations_found': len(citations),
            'citations_verified': verified_count,
            'overall_confidence': round(overall_confidence, 3),
            'verification_rate': round(verified_count / len(citations), 3) if citations else 0
        })
        
    except Exception as e:
        logger.error(f"Error in verify_citations: {e}")
        return create_error_response("Internal server error during verification", 500)

@api_bp.route('/results/<session_id>', methods=['GET'])
def get_results(session_id):
    """
    Retrieve verification results for a session.
    """
    try:
        # Verify session exists and is valid
        session_data = SessionManager.get_session(session_id)
        if not session_data:
            return create_error_response("Invalid or expired session", 404)
        
        # Get results
        results = ResultsManager.get_results(session_id)
        if not results:
            return create_error_response("No results found for session", 404)
        
        # Get detailed citation results
        citation_details = ResultsManager.get_citation_details(results['id'])
        
        # Parse verification details if available
        verification_summary = []
        if results.get('verification_details'):
            try:
                verification_summary = json.loads(results['verification_details'])
            except json.JSONDecodeError:
                logger.warning(f"Could not parse verification details for session {session_id}")
        
        response_data = {
            'session_id': session_id,
            'analysis_timestamp': results['analysis_timestamp'],
            'citations_found': results['citations_found'],
            'citations_verified': results['citations_verified'],
            'overall_confidence': round(results['confidence_score'], 3),
            'verification_rate': round(results['citations_verified'] / results['citations_found'], 3) if results['citations_found'] > 0 else 0,
            'citation_details': [
                {
                    'citation': detail['citation_text'],
                    'type': detail['citation_type'],
                    'verified': bool(detail['verified']),
                    'confidence': round(detail['confidence_score'], 3),
                    'courtlistener_match': json.loads(detail['courtlistener_match']) if detail['courtlistener_match'] else {},
                    'error': detail['error_message']
                }
                for detail in citation_details
            ]
        }
        
        return create_response(response_data)
        
    except Exception as e:
        logger.error(f"Error retrieving results: {e}")
        return create_error_response("Internal server error retrieving results", 500)

@api_bp.route('/view/<session_id>', methods=['GET'])
def view_session(session_id):
    """
    View basic session information without detailed results.
    """
    try:
        session_data = SessionManager.get_session(session_id)
        if not session_data:
            return create_error_response("Invalid or expired session", 404)
        
        results = ResultsManager.get_results(session_id)
        
        response_data = {
            'session_id': session_id,
            'created_at': session_data['created_at'],
            'expires_at': session_data['expires_at'],
            'status': session_data['status'],
            'has_results': results is not None,
            'citations_found': results['citations_found'] if results else None,
            'citations_verified': results['citations_verified'] if results else None
        }
        
        return create_response(response_data)
        
    except Exception as e:
        logger.error(f"Error viewing session: {e}")
        return create_error_response("Internal server error", 500)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint with service status.
    """
    try:
        # Check CourtListener service
        courtlistener_status = courtlistener_service.get_service_status() if courtlistener_service else {
            'available': False,
            'error': 'Service not initialized'
        }
        
        # Clean up expired sessions
        SessionManager.cleanup_expired_sessions()
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'services': {
                'database': 'healthy',
                'courtlistener': 'healthy' if courtlistener_status.get('available') else 'degraded',
                'citation_processor': 'healthy'
            },
            'courtlistener_status': courtlistener_status
        }
        
        return create_response(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return create_error_response("Health check failed", 500)