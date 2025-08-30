import json
import asyncio
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import structlog
from datetime import datetime
import uuid

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time features."""
    
    def __init__(self):
        # Active connections grouped by user
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        # Room-based connections for document collaboration
        self.rooms: Dict[str, Set[str]] = {}
        # Connection to user mapping
        self.connection_to_user: Dict[str, str] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: str, connection_id: Optional[str] = None) -> str:
        """
        Accept a WebSocket connection and register it.
        
        Args:
            websocket: WebSocket connection
            user_id: User ID
            connection_id: Optional connection ID
            
        Returns:
            str: Connection ID
        """
        if connection_id is None:
            connection_id = str(uuid.uuid4())
        
        await websocket.accept()
        
        async with self._lock:
            # Add to user connections
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
            
            # Store connection metadata
            self.connection_metadata[connection_id] = {
                "user_id": user_id,
                "websocket": websocket,
                "connected_at": datetime.utcnow(),
                "last_activity": datetime.utcnow()
            }
            
            # Map connection to user
            self.connection_to_user[connection_id] = user_id
        
        logger.info("WebSocket connected", 
                   user_id=user_id, 
                   connection_id=connection_id,
                   total_connections=len(self.connection_metadata))
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        Remove a WebSocket connection.
        
        Args:
            connection_id: Connection ID to remove
        """
        async with self._lock:
            if connection_id not in self.connection_metadata:
                return
            
            metadata = self.connection_metadata[connection_id]
            user_id = metadata["user_id"]
            websocket = metadata["websocket"]
            
            # Remove from user connections
            if user_id in self.active_connections:
                try:
                    self.active_connections[user_id].remove(websocket)
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]
                except ValueError:
                    pass
            
            # Remove from rooms
            for room_id in list(self.rooms.keys()):
                self.rooms[room_id].discard(connection_id)
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
            
            # Clean up metadata
            del self.connection_metadata[connection_id]
            del self.connection_to_user[connection_id]
        
        logger.info("WebSocket disconnected", 
                   user_id=user_id, 
                   connection_id=connection_id,
                   total_connections=len(self.connection_metadata))
    
    async def send_personal_message(self, message: dict, user_id: str):
        """
        Send a message to all connections of a specific user.
        
        Args:
            message: Message to send
            user_id: Target user ID
        """
        if user_id not in self.active_connections:
            logger.warning("No active connections for user", user_id=user_id)
            return
        
        # Copy list to avoid modification during iteration
        connections = self.active_connections[user_id].copy()
        disconnected_connections = []
        
        for websocket in connections:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps(message))
                    logger.debug("Message sent to user", user_id=user_id)
                else:
                    disconnected_connections.append(websocket)
            except Exception as e:
                logger.error("Failed to send message to user", 
                           user_id=user_id, 
                           error=str(e))
                disconnected_connections.append(websocket)
        
        # Clean up disconnected connections
        if disconnected_connections:
            async with self._lock:
                for websocket in disconnected_connections:
                    try:
                        self.active_connections[user_id].remove(websocket)
                    except ValueError:
                        pass
    
    async def send_to_room(self, message: dict, room_id: str):
        """
        Send a message to all connections in a room.
        
        Args:
            message: Message to send
            room_id: Target room ID
        """
        if room_id not in self.rooms:
            logger.warning("Room not found", room_id=room_id)
            return
        
        # Copy set to avoid modification during iteration
        connection_ids = self.rooms[room_id].copy()
        disconnected_connections = []
        
        for connection_id in connection_ids:
            if connection_id not in self.connection_metadata:
                disconnected_connections.append(connection_id)
                continue
            
            try:
                websocket = self.connection_metadata[connection_id]["websocket"]
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps(message))
                    # Update last activity
                    self.connection_metadata[connection_id]["last_activity"] = datetime.utcnow()
                else:
                    disconnected_connections.append(connection_id)
            except Exception as e:
                logger.error("Failed to send message to room", 
                           room_id=room_id, 
                           connection_id=connection_id,
                           error=str(e))
                disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        if disconnected_connections:
            async with self._lock:
                for connection_id in disconnected_connections:
                    self.rooms[room_id].discard(connection_id)
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]
        
        logger.debug("Message sent to room", 
                    room_id=room_id, 
                    connections=len(connection_ids))
    
    async def broadcast(self, message: dict, exclude_user: Optional[str] = None):
        """
        Broadcast a message to all connected users.
        
        Args:
            message: Message to broadcast
            exclude_user: User ID to exclude from broadcast
        """
        user_ids = list(self.active_connections.keys())
        if exclude_user:
            user_ids = [uid for uid in user_ids if uid != exclude_user]
        
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)
        
        logger.info("Message broadcasted", 
                   total_users=len(user_ids),
                   excluded_user=exclude_user)
    
    async def join_room(self, connection_id: str, room_id: str) -> bool:
        """
        Add a connection to a room.
        
        Args:
            connection_id: Connection ID
            room_id: Room ID to join
            
        Returns:
            bool: True if joined successfully
        """
        if connection_id not in self.connection_metadata:
            logger.warning("Connection not found", connection_id=connection_id)
            return False
        
        async with self._lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = set()
            self.rooms[room_id].add(connection_id)
        
        user_id = self.connection_metadata[connection_id]["user_id"]
        logger.info("Connection joined room", 
                   connection_id=connection_id,
                   user_id=user_id,
                   room_id=room_id)
        
        # Notify room members
        await self.send_to_room({
            "type": "user_joined",
            "room_id": room_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }, room_id)
        
        return True
    
    async def leave_room(self, connection_id: str, room_id: str) -> bool:
        """
        Remove a connection from a room.
        
        Args:
            connection_id: Connection ID
            room_id: Room ID to leave
            
        Returns:
            bool: True if left successfully
        """
        if (connection_id not in self.connection_metadata or 
            room_id not in self.rooms or 
            connection_id not in self.rooms[room_id]):
            return False
        
        async with self._lock:
            self.rooms[room_id].discard(connection_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        
        user_id = self.connection_metadata[connection_id]["user_id"]
        logger.info("Connection left room", 
                   connection_id=connection_id,
                   user_id=user_id,
                   room_id=room_id)
        
        # Notify remaining room members
        if room_id in self.rooms:
            await self.send_to_room({
                "type": "user_left",
                "room_id": room_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }, room_id)
        
        return True
    
    async def get_room_users(self, room_id: str) -> List[str]:
        """
        Get list of user IDs in a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            List[str]: List of user IDs
        """
        if room_id not in self.rooms:
            return []
        
        user_ids = []
        for connection_id in self.rooms[room_id]:
            if connection_id in self.connection_metadata:
                user_ids.append(self.connection_metadata[connection_id]["user_id"])
        
        return list(set(user_ids))  # Remove duplicates
    
    def get_connection_count(self) -> dict:
        """
        Get connection statistics.
        
        Returns:
            dict: Connection statistics
        """
        return {
            "total_connections": len(self.connection_metadata),
            "total_users": len(self.active_connections),
            "total_rooms": len(self.rooms),
            "connections_per_user": {
                user_id: len(connections) 
                for user_id, connections in self.active_connections.items()
            }
        }
    
    async def cleanup_inactive_connections(self, timeout_minutes: int = 30):
        """
        Clean up connections that have been inactive for too long.
        
        Args:
            timeout_minutes: Inactivity timeout in minutes
        """
        cutoff_time = datetime.utcnow().timestamp() - (timeout_minutes * 60)
        inactive_connections = []
        
        for connection_id, metadata in self.connection_metadata.items():
            last_activity = metadata["last_activity"].timestamp()
            if last_activity < cutoff_time:
                inactive_connections.append(connection_id)
        
        for connection_id in inactive_connections:
            logger.info("Cleaning up inactive connection", connection_id=connection_id)
            await self.disconnect(connection_id)
        
        if inactive_connections:
            logger.info("Cleaned up inactive connections", 
                       count=len(inactive_connections))


# Global connection manager instance
manager = ConnectionManager()