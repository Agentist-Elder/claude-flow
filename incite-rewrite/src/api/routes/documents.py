from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog
from datetime import datetime
import uuid
import json

from ...database.connection import get_database
from ...models.user import User, Document
from ...api.routes.auth import get_current_user
from ...core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


# Pydantic models for request/response
class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Document title")
    content: str = Field(..., min_length=1, max_length=settings.MAX_TEXT_LENGTH, description="Document content")
    document_type: str = Field(default="text", description="Document type")
    is_public: bool = Field(default=False, description="Whether document is public")
    tags: Optional[str] = Field(None, max_length=500, description="Comma-separated tags")


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Document title")
    content: Optional[str] = Field(None, min_length=1, max_length=settings.MAX_TEXT_LENGTH, description="Document content")
    document_type: Optional[str] = Field(None, description="Document type")
    is_public: Optional[bool] = Field(None, description="Whether document is public")
    tags: Optional[str] = Field(None, max_length=500, description="Comma-separated tags")


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    original_content: Optional[str]
    document_type: str
    status: str
    word_count: int
    analysis_result: Optional[Dict[str, Any]]
    rewrite_result: Optional[Dict[str, Any]]
    processing_metadata: Optional[Dict[str, Any]]
    is_public: bool
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]
    user_id: str


class DocumentSummary(BaseModel):
    id: str
    title: str
    document_type: str
    status: str
    word_count: int
    is_public: bool
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class PaginatedDocuments(BaseModel):
    documents: List[DocumentSummary]
    total: int
    page: int
    size: int
    pages: int


def parse_tags(tags_str: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated tags string into list."""
    if not tags_str:
        return None
    return [tag.strip() for tag in tags_str.split(",") if tag.strip()]


def format_tags(tags_list: Optional[List[str]]) -> Optional[str]:
    """Format tags list into comma-separated string."""
    if not tags_list:
        return None
    return ",".join(tags_list)


def parse_json_field(field_value: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse JSON string field safely."""
    if not field_value:
        return None
    try:
        return json.loads(field_value)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse JSON field", field_value=field_value)
        return None


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Create a new document.
    
    Args:
        document_data: Document creation data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentResponse: Created document
    """
    try:
        # Count words
        word_count = count_words(document_data.content)
        
        # Create new document
        new_document = Document(
            id=uuid.uuid4(),
            user_id=current_user.id,
            title=document_data.title,
            content=document_data.content,
            original_content=document_data.content,  # Store original for comparison
            document_type=document_data.document_type,
            word_count=word_count,
            is_public=document_data.is_public,
            tags=document_data.tags,
            status="draft"
        )
        
        db.add(new_document)
        await db.commit()
        await db.refresh(new_document)
        
        logger.info("Document created successfully", 
                   document_id=str(new_document.id), 
                   user_id=str(current_user.id))
        
        return DocumentResponse(
            id=str(new_document.id),
            title=new_document.title,
            content=new_document.content,
            original_content=new_document.original_content,
            document_type=new_document.document_type,
            status=new_document.status,
            word_count=new_document.word_count,
            analysis_result=parse_json_field(new_document.analysis_result),
            rewrite_result=parse_json_field(new_document.rewrite_result),
            processing_metadata=parse_json_field(new_document.processing_metadata),
            is_public=new_document.is_public,
            tags=parse_tags(new_document.tags),
            created_at=new_document.created_at,
            updated_at=new_document.updated_at,
            processed_at=new_document.processed_at,
            user_id=str(new_document.user_id)
        )
        
    except Exception as e:
        logger.error("Document creation failed", user_id=str(current_user.id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document creation failed"
        )


@router.get("/", response_model=PaginatedDocuments)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    List user documents with pagination and filtering.
    
    Args:
        page: Page number
        size: Page size
        search: Search query
        document_type: Document type filter
        status: Status filter
        tags: Tags filter
        sort_by: Sort field
        sort_order: Sort order
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        PaginatedDocuments: Paginated document list
    """
    try:
        # Build query
        query = select(Document).where(Document.user_id == current_user.id)
        
        # Apply filters
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Document.title.ilike(search_pattern),
                    Document.content.ilike(search_pattern)
                )
            )
        
        if document_type:
            query = query.where(Document.document_type == document_type)
        
        if status:
            query = query.where(Document.status == status)
        
        if tags:
            tag_filters = [tag.strip() for tag in tags.split(",")]
            for tag in tag_filters:
                query = query.where(Document.tags.ilike(f"%{tag}%"))
        
        # Apply sorting
        sort_column = getattr(Document, sort_by, Document.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Get total count
        count_query = select(func.count(Document.id)).where(Document.user_id == current_user.id)
        if search:
            search_pattern = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Document.title.ilike(search_pattern),
                    Document.content.ilike(search_pattern)
                )
            )
        if document_type:
            count_query = count_query.where(Document.document_type == document_type)
        if status:
            count_query = count_query.where(Document.status == status)
        if tags:
            tag_filters = [tag.strip() for tag in tags.split(",")]
            for tag in tag_filters:
                count_query = count_query.where(Document.tags.ilike(f"%{tag}%"))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        # Execute query
        result = await db.execute(query)
        documents = result.scalars().all()
        
        # Calculate pages
        pages = (total + size - 1) // size
        
        # Convert to response format
        document_summaries = [
            DocumentSummary(
                id=str(doc.id),
                title=doc.title,
                document_type=doc.document_type,
                status=doc.status,
                word_count=doc.word_count,
                is_public=doc.is_public,
                tags=parse_tags(doc.tags),
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )
            for doc in documents
        ]
        
        return PaginatedDocuments(
            documents=document_summaries,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
        
    except Exception as e:
        logger.error("Document listing failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get a specific document by ID.
    
    Args:
        document_id: Document ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentResponse: Document details
    """
    try:
        # Find document
        result = await db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    or_(
                        Document.user_id == current_user.id,
                        Document.is_public == True
                    )
                )
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentResponse(
            id=str(document.id),
            title=document.title,
            content=document.content,
            original_content=document.original_content,
            document_type=document.document_type,
            status=document.status,
            word_count=document.word_count,
            analysis_result=parse_json_field(document.analysis_result),
            rewrite_result=parse_json_field(document.rewrite_result),
            processing_metadata=parse_json_field(document.processing_metadata),
            is_public=document.is_public,
            tags=parse_tags(document.tags),
            created_at=document.created_at,
            updated_at=document.updated_at,
            processed_at=document.processed_at,
            user_id=str(document.user_id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document retrieval failed", 
                    document_id=document_id, 
                    user_id=str(current_user.id), 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    document_data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Update a document.
    
    Args:
        document_id: Document ID
        document_data: Document update data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentResponse: Updated document
    """
    try:
        # Find document (only user's own documents can be updated)
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
                detail="Document not found or you don't have permission to update it"
            )
        
        # Update fields
        if document_data.title is not None:
            document.title = document_data.title
        if document_data.content is not None:
            document.content = document_data.content
            document.word_count = count_words(document_data.content)
            # Reset processing results if content changed
            document.analysis_result = None
            document.rewrite_result = None
            document.processed_at = None
            document.status = "draft"
        if document_data.document_type is not None:
            document.document_type = document_data.document_type
        if document_data.is_public is not None:
            document.is_public = document_data.is_public
        if document_data.tags is not None:
            document.tags = document_data.tags
        
        await db.commit()
        await db.refresh(document)
        
        logger.info("Document updated successfully", 
                   document_id=str(document.id), 
                   user_id=str(current_user.id))
        
        return DocumentResponse(
            id=str(document.id),
            title=document.title,
            content=document.content,
            original_content=document.original_content,
            document_type=document.document_type,
            status=document.status,
            word_count=document.word_count,
            analysis_result=parse_json_field(document.analysis_result),
            rewrite_result=parse_json_field(document.rewrite_result),
            processing_metadata=parse_json_field(document.processing_metadata),
            is_public=document.is_public,
            tags=parse_tags(document.tags),
            created_at=document.created_at,
            updated_at=document.updated_at,
            processed_at=document.processed_at,
            user_id=str(document.user_id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document update failed", 
                    document_id=document_id, 
                    user_id=str(current_user.id), 
                    error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document update failed"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Delete a document.
    
    Args:
        document_id: Document ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dict: Success message
    """
    try:
        # Find document (only user's own documents can be deleted)
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
                detail="Document not found or you don't have permission to delete it"
            )
        
        await db.delete(document)
        await db.commit()
        
        logger.info("Document deleted successfully", 
                   document_id=str(document.id), 
                   user_id=str(current_user.id))
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document deletion failed", 
                    document_id=document_id, 
                    user_id=str(current_user.id), 
                    error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document deletion failed"
        )


@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get document version history (original vs processed).
    
    Args:
        document_id: Document ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dict: Version history
    """
    try:
        # Find document
        result = await db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    or_(
                        Document.user_id == current_user.id,
                        Document.is_public == True
                    )
                )
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        versions = {
            "original": {
                "content": document.original_content,
                "word_count": count_words(document.original_content) if document.original_content else 0,
                "created_at": document.created_at
            },
            "current": {
                "content": document.content,
                "word_count": document.word_count,
                "updated_at": document.updated_at
            }
        }
        
        # Add processed version if available
        if document.rewrite_result:
            rewrite_data = parse_json_field(document.rewrite_result)
            if rewrite_data and "rewritten_text" in rewrite_data:
                versions["processed"] = {
                    "content": rewrite_data["rewritten_text"],
                    "word_count": count_words(rewrite_data["rewritten_text"]),
                    "processed_at": document.processed_at,
                    "metadata": rewrite_data.get("metadata", {})
                }
        
        return {
            "document_id": document_id,
            "title": document.title,
            "versions": versions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document versions retrieval failed", 
                    document_id=document_id, 
                    user_id=str(current_user.id), 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document versions"
        )