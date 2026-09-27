import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..pipeline.streaming_pipeline import StreamingPipeline
from ..storage.session_store import session_store
from ..models.session import SessionCreate, SessionSettings

router = APIRouter(tags=["live"])

@router.websocket("/ws/live/{session_id}")
async def live_audio_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = session_store.get_session(session_id)
    if not session:
        # Create session if needed
        sess_create = SessionCreate(
            title=f"Live Session {session_id[:6]}",
            audio_source="microphone",
            mode="live"
        )
        session = session_store.create_session(sess_create)

    pipeline = StreamingPipeline()
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def frame_stream():
        while True:
            chunk = await audio_queue.get()
            if chunk == b"":
                break
            yield chunk

    async def sender_task():
        try:
            async for event in pipeline.process_live_stream(frame_stream()):
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))

    sender = asyncio.create_task(sender_task())

    try:
        while True:
            # Receive either binary audio data or text commands
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                await audio_queue.put(message["bytes"])
            elif "text" in message and message["text"]:
                cmd = json.loads(message["text"])
                if cmd.get("action") == "stop":
                    await audio_queue.put(b"")
                    break
    except WebSocketDisconnect:
        await audio_queue.put(b"")
    finally:
        sender.cancel()
