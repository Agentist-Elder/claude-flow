from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import structlog
from datetime import datetime
import uuid
import json
import asyncio
import httpx
from enum import Enum

from ...database.connection import get_database
from ...models.user import User, Document, ProcessingJob
from ...api.routes.auth import get_current_user
from ...core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/text-processing", tags=["Text Processing"])


class AnalysisType(str, Enum):
    """Text analysis types."""
    READABILITY = "readability"
    SENTIMENT = "sentiment"
    STRUCTURE = "structure"
    GRAMMAR = "grammar"
    STYLE = "style"
    COMPREHENSIVE = "comprehensive"


class RewriteStyle(str, Enum):
    """Text rewrite styles."""
    FORMAL = "formal"
    CASUAL = "casual"
    ACADEMIC = "academic"
    BUSINESS = "business"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    SIMPLIFIED = "simplified"


class ProcessingStatus(str, Enum):
    """Processing job statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Pydantic models for request/response
class TextAnalysisRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=settings.MAX_TEXT_LENGTH, description="Text to analyze")
    document_id: Optional[str] = Field(None, description="Document ID to analyze")
    analysis_types: List[AnalysisType] = Field(default=[AnalysisType.COMPREHENSIVE], description="Types of analysis to perform")
    include_suggestions: bool = Field(default=True, description="Include improvement suggestions")


class TextRewriteRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=settings.MAX_TEXT_LENGTH, description="Text to rewrite")
    document_id: Optional[str] = Field(None, description="Document ID to rewrite")
    style: RewriteStyle = Field(default=RewriteStyle.FORMAL, description="Rewrite style")
    tone: Optional[str] = Field(None, description="Specific tone (e.g., 'professional', 'friendly')")
    target_audience: Optional[str] = Field(None, description="Target audience")
    preserve_meaning: bool = Field(default=True, description="Preserve original meaning")
    target_length: Optional[str] = Field(None, description="Target length ('shorter', 'longer', 'same')")


class AnalysisResult(BaseModel):
    analysis_id: str
    document_id: Optional[str]
    analysis_types: List[str]
    results: Dict[str, Any]
    suggestions: Optional[List[Dict[str, Any]]]
    metadata: Dict[str, Any]
    processed_at: datetime


class RewriteResult(BaseModel):
    rewrite_id: str
    document_id: Optional[str]
    original_text: str
    rewritten_text: str
    style: str
    changes_summary: Dict[str, Any]
    metadata: Dict[str, Any]
    processed_at: datetime


class ProcessingJobResponse(BaseModel):
    job_id: str
    document_id: Optional[str]
    job_type: str
    status: str
    progress: int
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class BatchProcessingRequest(BaseModel):
    document_ids: List[str] = Field(..., min_items=1, max_items=50, description="Document IDs to process")
    operation: str = Field(..., description="Operation type ('analyze' or 'rewrite')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")


async def get_text_from_request(
    text: Optional[str],
    document_id: Optional[str],
    db: AsyncSession,
    current_user: User
) -> tuple[str, Optional[Document]]:
    """
    Get text content from either direct text or document ID.
    
    Args:
        text: Direct text content
        document_id: Document ID
        db: Database session
        current_user: Current user
        
    Returns:
        Tuple of (text_content, document_object)
    """
    if text and document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either text or document_id, not both"
        )
    
    if not text and not document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either text or document_id must be provided"
        )
    
    if text:
        return text, None
    
    # Get text from document
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == current_user.id
            )
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have access"
        )
    
    return document.content, document


async def create_processing_job(
    db: AsyncSession,
    document_id: Optional[str],
    user_id: str,
    job_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> ProcessingJob:
    """Create a new processing job."""
    job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=document_id,
        user_id=user_id,
        job_type=job_type,
        status=ProcessingStatus.PENDING,
        metadata=json.dumps(metadata) if metadata else None
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return job


async def update_processing_job(
    db: AsyncSession,
    job_id: str,
    status: ProcessingStatus,
    progress: int = 0,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
) -> Optional[ProcessingJob]:
    """Update a processing job."""
    result_db = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id)
    )
    job = result_db.scalar_one_or_none()
    
    if not job:
        return None
    
    job.status = status
    job.progress = progress
    
    if status == ProcessingStatus.PROCESSING and not job.started_at:
        job.started_at = datetime.utcnow()
    elif status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
        job.completed_at = datetime.utcnow()
        job.progress = 100
    
    if result:
        job.result = json.dumps(result)
    if error_message:
        job.error_message = error_message
    
    await db.commit()
    await db.refresh(job)
    
    return job


async def perform_text_analysis(text: str, analysis_types: List[AnalysisType]) -> Dict[str, Any]:
    """
    Perform text analysis using AI service or built-in algorithms.
    
    This is a mock implementation. In production, you would integrate with
    actual AI services like OpenAI, Google Cloud AI, or Azure Cognitive Services.
    """
    await asyncio.sleep(1)  # Simulate processing time
    
    results = {}
    
    for analysis_type in analysis_types:
        if analysis_type == AnalysisType.READABILITY:
            # Simple readability metrics
            sentences = len([s for s in text.split('.') if s.strip()])
            words = len(text.split())
            avg_sentence_length = words / max(sentences, 1)
            
            results["readability"] = {
                "average_sentence_length": round(avg_sentence_length, 2),
                "word_count": words,
                "sentence_count": sentences,
                "reading_level": "intermediate" if avg_sentence_length < 20 else "advanced",
                "score": max(0, min(100, 100 - avg_sentence_length * 2))
            }
        
        elif analysis_type == AnalysisType.SENTIMENT:
            # Simple sentiment analysis (mock)
            positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic"]
            negative_words = ["bad", "terrible", "awful", "horrible", "worst", "hate"]
            
            text_lower = text.lower()
            pos_count = sum(1 for word in positive_words if word in text_lower)
            neg_count = sum(1 for word in negative_words if word in text_lower)
            
            if pos_count > neg_count:
                sentiment = "positive"
                score = 0.7
            elif neg_count > pos_count:
                sentiment = "negative"
                score = 0.3
            else:
                sentiment = "neutral"
                score = 0.5
            
            results["sentiment"] = {
                "sentiment": sentiment,
                "confidence": score,
                "positive_indicators": pos_count,
                "negative_indicators": neg_count
            }
        
        elif analysis_type == AnalysisType.STRUCTURE:
            paragraphs = len([p for p in text.split('\n\n') if p.strip()])
            results["structure"] = {
                "paragraph_count": paragraphs,
                "has_introduction": text[:100].lower().count("introduction") > 0,
                "has_conclusion": text[-100:].lower().count("conclusion") > 0,
                "structure_score": min(100, paragraphs * 10)
            }
        
        elif analysis_type == AnalysisType.GRAMMAR:
            # Simple grammar check (mock)
            results["grammar"] = {
                "grammar_score": 85,
                "issues_found": 2,
                "suggestions": [
                    {"type": "spelling", "message": "Check spelling of technical terms"},
                    {"type": "punctuation", "message": "Consider using more varied punctuation"}
                ]
            }
        
        elif analysis_type == AnalysisType.STYLE:
            words = text.split()
            unique_words = set(word.lower().strip('.,!?";:') for word in words)
            lexical_diversity = len(unique_words) / max(len(words), 1)
            
            results["style"] = {
                "lexical_diversity": round(lexical_diversity, 3),
                "style_consistency": 0.8,
                "formality_level": "medium",
                "tone": "professional"
            }
    
    if AnalysisType.COMPREHENSIVE in analysis_types:
        # Comprehensive analysis combines all metrics
        results["comprehensive"] = {
            "overall_score": 78,
            "strengths": ["Clear structure", "Good vocabulary"],
            "weaknesses": ["Long sentences", "Some grammar issues"],
            "recommendations": [
                "Break down long sentences for better readability",
                "Use more transitional phrases",
                "Consider your target audience"
            ]
        }
    
    return results


async def perform_text_rewrite(
    text: str,
    style: RewriteStyle,
    tone: Optional[str] = None,
    target_audience: Optional[str] = None,
    preserve_meaning: bool = True,
    target_length: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform text rewriting using AI service.
    
    This is a mock implementation. In production, you would integrate with
    actual AI services.
    """
    await asyncio.sleep(2)  # Simulate processing time
    
    # Mock rewrite based on style
    original_words = text.split()
    word_count = len(original_words)
    
    if style == RewriteStyle.FORMAL:
        rewritten = text.replace("don't", "do not").replace("won't", "will not").replace("can't", "cannot")
        changes = ["Expanded contractions", "Used more formal language"]
    elif style == RewriteStyle.CASUAL:
        rewritten = text.replace("therefore", "so").replace("however", "but")
        changes = ["Used simpler transitions", "More conversational tone"]
    elif style == RewriteStyle.ACADEMIC:
        rewritten = f"This analysis examines {text.lower()}"
        changes = ["Added academic framing", "Used scholarly language"]
    elif style == RewriteStyle.SIMPLIFIED:
        # Mock simplification
        sentences = text.split('.')
        simplified_sentences = []
        for sentence in sentences:
            if sentence.strip():
                words = sentence.split()
                if len(words) > 15:  # Split long sentences
                    mid = len(words) // 2
                    simplified_sentences.extend([
                        ' '.join(words[:mid]) + '.',
                        ' '.join(words[mid:]) + '.'
                    ])
                else:
                    simplified_sentences.append(sentence + '.')
        rewritten = ' '.join(simplified_sentences)
        changes = ["Shortened sentences", "Simplified vocabulary"]
    else:
        rewritten = text  # Default: no change
        changes = ["Minor style adjustments"]
    
    # Apply target length changes
    if target_length == "shorter":
        rewritten = rewritten[:len(rewritten)//2] + "..."
        changes.append("Reduced length by 50%")
    elif target_length == "longer":
        rewritten = rewritten + " " + rewritten
        changes.append("Extended content with additional details")
    
    new_word_count = len(rewritten.split())
    
    return {
        "rewritten_text": rewritten,
        "changes_summary": {
            "original_word_count": word_count,
            "new_word_count": new_word_count,
            "changes_made": changes,
            "style_applied": style,
            "tone_adjusted": tone or "default",
            "meaning_preserved": preserve_meaning
        },
        "metadata": {
            "processing_time": 2.0,
            "model_version": "mock-v1.0",
            "confidence": 0.9
        }
    }


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_text(
    request: TextAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Analyze text for various metrics like readability, sentiment, structure, etc.
    
    Args:
        request: Text analysis request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        AnalysisResult: Analysis results
    """
    try:
        # Get text content
        text_content, document = await get_text_from_request(
            request.text, request.document_id, db, current_user
        )
        
        # Perform analysis
        results = await perform_text_analysis(text_content, request.analysis_types)
        
        # Generate suggestions if requested
        suggestions = []
        if request.include_suggestions:
            suggestions = [
                {
                    "type": "readability",
                    "message": "Consider breaking down long sentences",
                    "priority": "medium"
                },
                {
                    "type": "structure",
                    "message": "Add more paragraph breaks for better flow",
                    "priority": "low"
                }
            ]
        
        analysis_result = {
            "analysis_id": str(uuid.uuid4()),
            "document_id": str(document.id) if document else None,
            "analysis_types": [t.value for t in request.analysis_types],
            "results": results,
            "suggestions": suggestions if request.include_suggestions else None,
            "metadata": {
                "text_length": len(text_content),
                "processing_time": 1.0,
                "model_version": "v1.0"
            },
            "processed_at": datetime.utcnow()
        }
        
        # Store analysis result in document if document_id provided
        if document:
            document.analysis_result = json.dumps(results)
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            await db.commit()
        
        logger.info("Text analysis completed", 
                   user_id=str(current_user.id),
                   document_id=str(document.id) if document else None)
        
        return AnalysisResult(**analysis_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Text analysis failed", 
                    user_id=str(current_user.id), 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text analysis failed"
        )


@router.post("/rewrite", response_model=RewriteResult)
async def rewrite_text(
    request: TextRewriteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Rewrite text according to specified style and parameters.
    
    Args:
        request: Text rewrite request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        RewriteResult: Rewrite results
    """
    try:
        # Get text content
        text_content, document = await get_text_from_request(
            request.text, request.document_id, db, current_user
        )
        
        # Perform rewriting
        rewrite_data = await perform_text_rewrite(
            text_content,
            request.style,
            request.tone,
            request.target_audience,
            request.preserve_meaning,
            request.target_length
        )
        
        rewrite_result = {
            "rewrite_id": str(uuid.uuid4()),
            "document_id": str(document.id) if document else None,
            "original_text": text_content,
            "rewritten_text": rewrite_data["rewritten_text"],
            "style": request.style.value,
            "changes_summary": rewrite_data["changes_summary"],
            "metadata": {
                **rewrite_data["metadata"],
                "style": request.style.value,
                "tone": request.tone,
                "target_audience": request.target_audience,
                "preserve_meaning": request.preserve_meaning,
                "target_length": request.target_length
            },
            "processed_at": datetime.utcnow()
        }
        
        # Store rewrite result in document if document_id provided
        if document:
            document.rewrite_result = json.dumps({
                "rewritten_text": rewrite_data["rewritten_text"],
                "metadata": rewrite_result["metadata"]
            })
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            await db.commit()
        
        logger.info("Text rewrite completed", 
                   user_id=str(current_user.id),
                   document_id=str(document.id) if document else None)
        
        return RewriteResult(**rewrite_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Text rewrite failed", 
                    user_id=str(current_user.id), 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text rewrite failed"
        )


@router.post("/jobs/{job_id}/cancel")
async def cancel_processing_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Cancel a processing job."""
    try:
        result = await db.execute(
            select(ProcessingJob).where(
                and_(
                    ProcessingJob.id == job_id,
                    ProcessingJob.user_id == current_user.id
                )
            )
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        if job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel completed or failed job"
            )
        
        job.status = ProcessingStatus.FAILED
        job.error_message = "Cancelled by user"
        job.completed_at = datetime.utcnow()
        
        await db.commit()
        
        return {"message": "Job cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Job cancellation failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job cancellation failed"
        )


@router.get("/jobs", response_model=List[ProcessingJobResponse])
async def list_processing_jobs(
    status: Optional[ProcessingStatus] = None,
    job_type: Optional[str] = None,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """List user's processing jobs."""
    try:
        query = select(ProcessingJob).where(ProcessingJob.user_id == current_user.id)
        
        if status:
            query = query.where(ProcessingJob.status == status)
        if job_type:
            query = query.where(ProcessingJob.job_type == job_type)
        
        query = query.order_by(ProcessingJob.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return [
            ProcessingJobResponse(
                job_id=str(job.id),
                document_id=str(job.document_id) if job.document_id else None,
                job_type=job.job_type,
                status=job.status,
                progress=job.progress,
                result=json.loads(job.result) if job.result else None,
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at
            )
            for job in jobs
        ]
        
    except Exception as e:
        logger.error("Job listing failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list jobs"
        )


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse)
async def get_processing_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Get processing job details."""
    try:
        result = await db.execute(
            select(ProcessingJob).where(
                and_(
                    ProcessingJob.id == job_id,
                    ProcessingJob.user_id == current_user.id
                )
            )
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        return ProcessingJobResponse(
            job_id=str(job.id),
            document_id=str(job.document_id) if job.document_id else None,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress,
            result=json.loads(job.result) if job.result else None,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Job retrieval failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job"
        )