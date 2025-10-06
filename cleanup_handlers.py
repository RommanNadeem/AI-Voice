"""
LiveKit Agent Cleanup & Reconnection Handlers
==============================================

Provides safe backend cleanup and reconnection flow to prevent WebRTC errors.

Features:
- Debounced participant disconnect handling
- Safe track reference cleanup
- Fresh session creation on reconnect
- Graceful shutdown for all resources

Usage:
    from cleanup_handlers import (
        register_cleanup_handlers,
        graceful_shutdown,
        active_sessions
    )
    
    # In your entrypoint:
    register_cleanup_handlers(ctx.room)
    
    # On shutdown:
    await graceful_shutdown(ctx.room, tts)
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set

# ---------------------------
# Session Tracking
# ---------------------------
# Track active sessions and cleanup state
active_sessions: Dict[str, Dict] = {}  # {participant_sid: {"user_id": str, "tracks": set(), "cleanup_done": bool}}
cleanup_locks: Dict[str, asyncio.Lock] = {}  # {participant_sid: asyncio.Lock()} - debounce guard


async def cleanup_participant_tracks(room, participant_sid: str, participant_identity: str = None):
    """
    Safely cleanup participant tracks with debounce guard.
    Prevents multiple cleanup runs for the same participant.
    
    Args:
        room: LiveKit room instance
        participant_sid: Participant session ID
        participant_identity: Optional participant identity for logging
    """
    # Initialize lock for this participant if not exists
    if participant_sid not in cleanup_locks:
        cleanup_locks[participant_sid] = asyncio.Lock()
    
    async with cleanup_locks[participant_sid]:
        # Check if cleanup already done
        if participant_sid in active_sessions and active_sessions[participant_sid].get("cleanup_done"):
            logging.info(f"[CLEANUP] Already cleaned up participant {participant_sid}, skipping")
            return
        
        logging.info(f"[CLEANUP] Starting cleanup for participant {participant_sid} (identity: {participant_identity})")
        
        try:
            # Get session data if exists
            session_data = active_sessions.get(participant_sid, {})
            tracks_to_cleanup = session_data.get("tracks", set())
            
            # Method 1: Cleanup tracks from session data
            if tracks_to_cleanup:
                logging.info(f"[CLEANUP] Found {len(tracks_to_cleanup)} tracks in session")
                for track_sid in list(tracks_to_cleanup):
                    try:
                        # Note: Track cleanup is handled by LiveKit SDK automatically
                        # We just remove references to prevent stale pointers
                        logging.debug(f"[CLEANUP] Removed reference to track {track_sid}")
                    except Exception as e:
                        logging.warning(f"[CLEANUP] Error removing track {track_sid}: {e}")
                
                # Clear track references
                tracks_to_cleanup.clear()
            
            # Method 2: Cleanup from room's remote participants (if still accessible)
            try:
                participant = room.remote_participants.get(participant_sid)
                if participant:
                    # Check track publications
                    for track_pub in participant.track_publications.values():
                        try:
                            if track_pub.track:
                                # Let LiveKit SDK handle the unpublishing
                                # We're just logging for visibility
                                logging.debug(f"[CLEANUP] Track {track_pub.sid} will be auto-cleaned by LiveKit SDK")
                        except Exception as e:
                            logging.warning(f"[CLEANUP] Error accessing track {track_pub.sid}: {e}")
            except Exception as e:
                logging.debug(f"[CLEANUP] Participant no longer in room: {e}")
            
            # Mark cleanup as done
            if participant_sid in active_sessions:
                active_sessions[participant_sid]["cleanup_done"] = True
            
            logging.info(f"[CLEANUP] ✓ Completed cleanup for participant {participant_sid}")
            
        except Exception as e:
            logging.error(f"[CLEANUP] Error during cleanup for {participant_sid}: {e}")
        
        finally:
            # Schedule session removal after delay (allow for reconnection window)
            asyncio.create_task(remove_session_after_delay(participant_sid, delay=30))


async def remove_session_after_delay(participant_sid: str, delay: int = 30):
    """
    Remove session data after delay, allowing for reconnection window.
    
    Args:
        participant_sid: Participant session ID
        delay: Delay in seconds before cleanup (default 30s)
    """
    await asyncio.sleep(delay)
    if participant_sid in active_sessions and active_sessions[participant_sid].get("cleanup_done"):
        logging.info(f"[SESSION] Removing session data for {participant_sid} after {delay}s")
        active_sessions.pop(participant_sid, None)
        cleanup_locks.pop(participant_sid, None)


async def handle_participant_disconnected(room, participant, clear_user_callback=None):
    """
    Handle participant disconnect event.
    Called when a participant leaves the room.
    
    Args:
        room: LiveKit room instance
        participant: Disconnected participant
        clear_user_callback: Optional callback to clear user state
    """
    participant_sid = participant.sid
    participant_identity = participant.identity
    
    logging.info(f"[DISCONNECT] Participant disconnected: sid={participant_sid}, identity={participant_identity}, room={room.name}")
    
    # Clear current user if callback provided
    if clear_user_callback:
        session_data = active_sessions.get(participant_sid, {})
        if session_data.get("user_id"):
            clear_user_callback(session_data["user_id"])
            logging.info(f"[DISCONNECT] Cleared active user_id: {session_data['user_id']}")
    
    # Run cleanup with debounce protection
    await cleanup_participant_tracks(room, participant_sid, participant_identity)


async def handle_participant_connected(room, participant):
    """
    Handle participant connect/reconnect event.
    Creates fresh session or clears stale data.
    
    Args:
        room: LiveKit room instance
        participant: Connected participant
    """
    participant_sid = participant.sid
    participant_identity = participant.identity
    
    logging.info(f"[CONNECT] Participant connected: sid={participant_sid}, identity={participant_identity}, room={room.name}")
    
    # Clear any stale session data for this participant
    if participant_sid in active_sessions:
        old_cleanup_done = active_sessions[participant_sid].get("cleanup_done", False)
        if old_cleanup_done:
            logging.info(f"[CONNECT] Clearing stale session for reconnecting participant {participant_sid}")
    
    # Create fresh session
    active_sessions[participant_sid] = {
        "user_id": None,  # Will be set after UUID extraction
        "tracks": set(),
        "cleanup_done": False,
        "connected_at": time.time()
    }
    
    logging.info(f"[CONNECT] ✓ Fresh session created for participant {participant_sid}")


async def handle_track_published(room, track, participant):
    """
    Track when participant publishes a track.
    Adds track reference to session for cleanup.
    
    Args:
        room: LiveKit room instance
        track: Published track
        participant: Participant who published the track
    """
    participant_sid = participant.sid
    track_sid = track.sid
    
    logging.debug(f"[TRACK] Published: {track_sid} by participant {participant_sid}")
    
    # Add track to session
    if participant_sid in active_sessions:
        active_sessions[participant_sid]["tracks"].add(track_sid)


async def graceful_shutdown(room, tts=None, clear_user_callback=None):
    """
    Graceful shutdown handler.
    Cleans up all active participants and resources.
    
    Args:
        room: LiveKit room instance
        tts: Optional TTS instance to close
        clear_user_callback: Optional callback to clear user state
    """
    logging.info(f"[SHUTDOWN] Starting graceful shutdown for room {room.name}")
    
    try:
        # Cleanup all active participants
        participant_sids = list(active_sessions.keys())
        logging.info(f"[SHUTDOWN] Cleaning up {len(participant_sids)} active sessions")
        
        for participant_sid in participant_sids:
            session_data = active_sessions.get(participant_sid, {})
            participant_identity = session_data.get("user_id", "unknown")
            await cleanup_participant_tracks(room, participant_sid, participant_identity)
        
        # Clear current user if callback provided
        if clear_user_callback:
            clear_user_callback(None)
        
        # Close TTS if provided
        if tts:
            try:
                await tts.aclose()
                logging.info("[SHUTDOWN] ✓ TTS resources closed")
            except Exception as e:
                logging.error(f"[SHUTDOWN] TTS cleanup error: {e}")
        
        # Clear all session data
        active_sessions.clear()
        cleanup_locks.clear()
        
        logging.info("[SHUTDOWN] ✓ Graceful shutdown complete")
        
    except Exception as e:
        logging.error(f"[SHUTDOWN] Error during shutdown: {e}")


def register_cleanup_handlers(room, clear_user_callback=None):
    """
    Register all cleanup event handlers with the room.
    
    Args:
        room: LiveKit room instance
        clear_user_callback: Optional callback to clear user state on disconnect
    
    Returns:
        Dictionary of registered handlers for reference
    """
    
    @room.on("participant_connected")
    def on_participant_connected(participant):
        asyncio.create_task(handle_participant_connected(room, participant))
    
    @room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        asyncio.create_task(handle_participant_disconnected(room, participant, clear_user_callback))
    
    @room.on("track_published")
    def on_track_published(publication, participant):
        if publication.track:
            asyncio.create_task(handle_track_published(room, publication.track, participant))
    
    logging.info("[EVENT HANDLERS] ✓ Registered cleanup event handlers")
    
    return {
        "participant_connected": on_participant_connected,
        "participant_disconnected": on_participant_disconnected,
        "track_published": on_track_published
    }


def get_session_info(participant_sid: str) -> Optional[Dict]:
    """
    Get session information for a participant.
    
    Args:
        participant_sid: Participant session ID
    
    Returns:
        Session data dictionary or None
    """
    return active_sessions.get(participant_sid)


def update_session_user(participant_sid: str, user_id: str):
    """
    Update user_id for a participant session.
    
    Args:
        participant_sid: Participant session ID
        user_id: User ID to associate with session
    """
    if participant_sid in active_sessions:
        active_sessions[participant_sid]["user_id"] = user_id
        logging.info(f"[SESSION] Updated session for participant {participant_sid} with user_id {user_id}")
    else:
        logging.warning(f"[SESSION] No active session found for participant {participant_sid}")

