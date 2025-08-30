from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
import structlog
from datetime import datetime
import uuid

from ...database.connection import get_database
from ...models.user import User
from ...auth.auth_handler import auth_handler
from ...core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()


# Pydantic models for request/response
class UserRegistration(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=30, description="Username")
    password: str = Field(..., min_length=8, max_length=100, description="Password")
    first_name: Optional[str] = Field(None, max_length=50, description="First name")
    last_name: Optional[str] = Field(None, max_length=50, description="Last name")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class UserProfile(BaseModel):
    id: str
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_verified: bool
    profile_picture: Optional[str]
    bio: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")


class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_database)
) -> User:
    """
    Dependency to get current authenticated user from JWT token.
    
    Args:
        credentials: JWT token from Authorization header
        db: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        # Verify token
        payload = auth_handler.verify_token(credentials.credentials, "access")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Fetch user from database
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to authenticate user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_client_info(request: Request) -> Dict[str, Optional[str]]:
    """Extract client information from request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "device_info": request.headers.get("x-device-info")
    }


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistration,
    db: AsyncSession = Depends(get_database)
):
    """
    Register a new user account.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        UserProfile: Created user profile
        
    Raises:
        HTTPException: If registration fails
    """
    try:
        # Check if user already exists
        result = await db.execute(
            select(User).where(
                (User.email == user_data.email) | (User.username == user_data.username)
            )
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken"
                )
        
        # Hash password
        hashed_password = auth_handler.hash_password(user_data.password)
        
        # Create new user
        new_user = User(
            id=uuid.uuid4(),
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info("User registered successfully", 
                   user_id=str(new_user.id), 
                   email=user_data.email)
        
        # Convert to response model
        return UserProfile(
            id=str(new_user.id),
            email=new_user.email,
            username=new_user.username,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            is_verified=new_user.is_verified,
            profile_picture=new_user.profile_picture,
            bio=new_user.bio,
            created_at=new_user.created_at,
            last_login=new_user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User registration failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    user_credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_database)
):
    """
    Authenticate user and return JWT tokens.
    
    Args:
        user_credentials: User login credentials
        request: HTTP request for client info
        db: Database session
        
    Returns:
        TokenResponse: JWT tokens and expiration info
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Authenticate user
        user = await auth_handler.authenticate_user(
            db, user_credentials.email, user_credentials.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create JWT tokens
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = auth_handler.create_access_token(token_data)
        refresh_token = auth_handler.create_refresh_token(token_data)
        
        # Create user session
        client_info = get_client_info(request)
        await auth_handler.create_user_session(
            db, str(user.id), refresh_token, **client_info
        )
        
        logger.info("User logged in successfully", 
                   user_id=str(user.id), 
                   email=user.email)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    refresh_request: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_database)
):
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_request: Refresh token request
        request: HTTP request for client info
        db: Database session
        
    Returns:
        TokenResponse: New JWT tokens
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        # Validate refresh token
        session = await auth_handler.validate_refresh_token(
            db, refresh_request.refresh_token
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == session.user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create new JWT tokens
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = auth_handler.create_access_token(token_data)
        new_refresh_token = auth_handler.create_refresh_token(token_data)
        
        # Revoke old session and create new one
        await auth_handler.revoke_session(db, str(session.id))
        client_info = get_client_info(request)
        await auth_handler.create_user_session(
            db, str(user.id), new_refresh_token, **client_info
        )
        
        logger.info("Token refreshed successfully", user_id=str(user.id))
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def logout_user(
    refresh_request: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Logout user by revoking refresh token.
    
    Args:
        refresh_request: Refresh token to revoke
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dict: Success message
    """
    try:
        # Find and revoke the specific session
        session = await auth_handler.validate_refresh_token(
            db, refresh_request.refresh_token
        )
        
        if session and session.user_id == current_user.id:
            await auth_handler.revoke_session(db, str(session.id))
            logger.info("User logged out successfully", user_id=str(current_user.id))
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error("Logout failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/logout-all")
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Logout user from all devices by revoking all refresh tokens.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dict: Success message with session count
    """
    try:
        revoked_count = await auth_handler.revoke_all_user_sessions(
            db, str(current_user.id)
        )
        
        logger.info("All user sessions logged out", 
                   user_id=str(current_user.id), 
                   count=revoked_count)
        
        return {
            "message": "Logged out from all devices successfully",
            "sessions_revoked": revoked_count
        }
        
    except Exception as e:
        logger.error("Logout all failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout from all devices failed"
        )


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user profile.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserProfile: User profile information
    """
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_verified=current_user.is_verified,
        profile_picture=current_user.profile_picture,
        bio=current_user.bio,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    profile_data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Update user profile information.
    
    Args:
        profile_data: Profile update data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        UserProfile: Updated user profile
    """
    try:
        # Update user profile
        if profile_data.first_name is not None:
            current_user.first_name = profile_data.first_name
        if profile_data.last_name is not None:
            current_user.last_name = profile_data.last_name
        if profile_data.bio is not None:
            current_user.bio = profile_data.bio
        
        await db.commit()
        await db.refresh(current_user)
        
        logger.info("User profile updated", user_id=str(current_user.id))
        
        return UserProfile(
            id=str(current_user.id),
            email=current_user.email,
            username=current_user.username,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            is_verified=current_user.is_verified,
            profile_picture=current_user.profile_picture,
            bio=current_user.bio,
            created_at=current_user.created_at,
            last_login=current_user.last_login
        )
        
    except Exception as e:
        logger.error("Profile update failed", user_id=str(current_user.id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Change user password.
    
    Args:
        password_data: Password change request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dict: Success message
    """
    try:
        # Verify current password
        if not auth_handler.verify_password(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        new_hashed_password = auth_handler.hash_password(password_data.new_password)
        current_user.hashed_password = new_hashed_password
        
        await db.commit()
        
        # Revoke all sessions to force re-login
        await auth_handler.revoke_all_user_sessions(db, str(current_user.id))
        
        logger.info("Password changed successfully", user_id=str(current_user.id))
        
        return {"message": "Password changed successfully. Please log in again."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password change failed", user_id=str(current_user.id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )