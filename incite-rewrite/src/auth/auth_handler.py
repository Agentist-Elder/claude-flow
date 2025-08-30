from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.config import settings
from ..models.user import User, UserSession

logger = structlog.get_logger(__name__)

# Password context with bcrypt (12 rounds for production security)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS
)


class AuthHandler:
    """Handles JWT token creation, validation, and user authentication."""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt with 12 rounds.
        
        Args:
            password (str): Plain text password
            
        Returns:
            str: Hashed password
        """
        try:
            hashed = pwd_context.hash(password)
            logger.debug("Password hashed successfully")
            return hashed
        except Exception as e:
            logger.error("Failed to hash password", error=str(e))
            raise ValueError("Failed to hash password")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password (str): Plain text password
            hashed_password (str): Hashed password
            
        Returns:
            bool: True if password matches, False otherwise
        """
        try:
            is_valid = pwd_context.verify(plain_password, hashed_password)
            logger.debug("Password verification completed", is_valid=is_valid)
            return is_valid
        except Exception as e:
            logger.error("Failed to verify password", error=str(e))
            return False
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """
        Create a JWT access token.
        
        Args:
            data (Dict[str, Any]): Token payload data
            
        Returns:
            str: JWT access token
        """
        try:
            to_encode = data.copy()
            expire = datetime.utcnow() + self.access_token_expire
            to_encode.update({"exp": expire, "type": "access"})
            
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            logger.debug("Access token created", subject=data.get("sub"), expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create access token", error=str(e))
            raise ValueError("Failed to create access token")
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            data (Dict[str, Any]): Token payload data
            
        Returns:
            str: JWT refresh token
        """
        try:
            to_encode = data.copy()
            expire = datetime.utcnow() + self.refresh_token_expire
            to_encode.update({
                "exp": expire,
                "type": "refresh",
                "jti": secrets.token_urlsafe(32)  # Unique token ID
            })
            
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            logger.debug("Refresh token created", subject=data.get("sub"), expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create refresh token", error=str(e))
            raise ValueError("Failed to create refresh token")
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Args:
            token (str): JWT token to verify
            token_type (str): Expected token type ("access" or "refresh")
            
        Returns:
            Optional[Dict[str, Any]]: Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning("Token type mismatch", 
                             expected=token_type, 
                             actual=payload.get("type"))
                return None
            
            # Verify expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                logger.warning("Token expired", expires_at=exp)
                return None
            
            logger.debug("Token verified successfully", 
                        subject=payload.get("sub"), 
                        token_type=token_type)
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired during verification")
            return None
        except jwt.JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error during token verification", error=str(e))
            return None
    
    async def authenticate_user(
        self, 
        db: AsyncSession, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Args:
            db (AsyncSession): Database session
            email (str): User email
            password (str): Plain text password
            
        Returns:
            Optional[User]: User object if authenticated, None otherwise
        """
        try:
            # Find user by email
            result = await db.execute(
                select(User).where(User.email == email, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning("User not found or inactive", email=email)
                return None
            
            # Verify password
            if not self.verify_password(password, user.hashed_password):
                logger.warning("Invalid password", email=email)
                return None
            
            # Update last login
            user.last_login = datetime.utcnow()
            await db.commit()
            
            logger.info("User authenticated successfully", 
                       user_id=str(user.id), 
                       email=email)
            return user
        except Exception as e:
            logger.error("Authentication failed", email=email, error=str(e))
            await db.rollback()
            return None
    
    async def create_user_session(
        self,
        db: AsyncSession,
        user_id: str,
        refresh_token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSession:
        """
        Create a new user session.
        
        Args:
            db (AsyncSession): Database session
            user_id (str): User ID
            refresh_token (str): Refresh token
            device_info (Optional[str]): Device information
            ip_address (Optional[str]): Client IP address
            user_agent (Optional[str]): Client user agent
            
        Returns:
            UserSession: Created session object
        """
        try:
            session = UserSession(
                user_id=user_id,
                refresh_token=refresh_token,
                device_info=device_info,
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=datetime.utcnow() + self.refresh_token_expire
            )
            
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
            logger.info("User session created", 
                       session_id=str(session.id), 
                       user_id=user_id)
            return session
        except Exception as e:
            logger.error("Failed to create user session", 
                        user_id=user_id, 
                        error=str(e))
            await db.rollback()
            raise ValueError("Failed to create user session")
    
    async def validate_refresh_token(
        self, 
        db: AsyncSession, 
        refresh_token: str
    ) -> Optional[UserSession]:
        """
        Validate a refresh token and return the associated session.
        
        Args:
            db (AsyncSession): Database session
            refresh_token (str): Refresh token to validate
            
        Returns:
            Optional[UserSession]: Session object if valid, None otherwise
        """
        try:
            # Verify token structure
            payload = self.verify_token(refresh_token, "refresh")
            if not payload:
                return None
            
            # Find session in database
            result = await db.execute(
                select(UserSession).where(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.warning("Refresh token not found or expired")
                return None
            
            logger.debug("Refresh token validated", session_id=str(session.id))
            return session
        except Exception as e:
            logger.error("Failed to validate refresh token", error=str(e))
            return None
    
    async def revoke_session(self, db: AsyncSession, session_id: str) -> bool:
        """
        Revoke a user session.
        
        Args:
            db (AsyncSession): Database session
            session_id (str): Session ID to revoke
            
        Returns:
            bool: True if session was revoked, False otherwise
        """
        try:
            result = await db.execute(
                select(UserSession).where(UserSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                logger.warning("Session not found", session_id=session_id)
                return False
            
            session.is_active = False
            await db.commit()
            
            logger.info("Session revoked", session_id=session_id)
            return True
        except Exception as e:
            logger.error("Failed to revoke session", 
                        session_id=session_id, 
                        error=str(e))
            await db.rollback()
            return False
    
    async def revoke_all_user_sessions(self, db: AsyncSession, user_id: str) -> int:
        """
        Revoke all sessions for a user.
        
        Args:
            db (AsyncSession): Database session
            user_id (str): User ID
            
        Returns:
            int: Number of sessions revoked
        """
        try:
            result = await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )
            sessions = result.scalars().all()
            
            revoked_count = 0
            for session in sessions:
                session.is_active = False
                revoked_count += 1
            
            await db.commit()
            
            logger.info("All user sessions revoked", 
                       user_id=user_id, 
                       count=revoked_count)
            return revoked_count
        except Exception as e:
            logger.error("Failed to revoke all user sessions", 
                        user_id=user_id, 
                        error=str(e))
            await db.rollback()
            return 0


# Global auth handler instance
auth_handler = AuthHandler()