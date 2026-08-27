import asyncio
import os
import time

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect
)

from google import genai
from google.genai import types


# ============================================================
# Setup
# ============================================================

load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found"
    )


client = genai.Client(
    api_key=API_KEY
)

MODEL = (
    "gemini-3.1-flash-live-preview"
)


app = FastAPI()


# ============================================================
# ASL instruction
# ============================================================

ASL_PROMPT = """
You are an American Sign Language (ASL)
interpretation system.

Analyze the recent video frames sent to you.

Your ONLY job is to recognize valid American
Sign Language and translate it into natural English.

Pay attention to:

- hand shape
- finger positions
- palm orientation
- hand location
- hand movement
- movement direction
- whether one or two hands are being used
- the sequence of movements across recent frames
- facial expressions only when needed for ASL meaning

Rules:

- Only interpret American Sign Language.
- Ignore random or ordinary hand gestures.
- Ignore the background.
- Do not describe the scene.
- Do not describe the person's hands.
- Do not explain your reasoning.
- Do not guess.
- Consider multiple recent frames together.
- Do not repeat the previous translation unless
  a new sign has actually been performed.

If you confidently recognize a sign or phrase,
return ONLY its natural English translation.

Examples:

Hello

Thank you

I love you

How are you?

If there is no recognizable ASL sign,
do not produce a translation.
"""


# ============================================================
# Receive camera frames from React
# ============================================================

async def receive_frames(
    websocket: WebSocket,
    session
):

    last_gemini_frame = 0.0

    while True:

        # JPEG sent from React
        frame_bytes = (
            await websocket.receive_bytes()
        )

        current_time = time.monotonic()


        # React sends ~5 FPS.
        #
        # Only forward approximately
        # one frame/sec to Gemini.
        if (
            current_time -
            last_gemini_frame
            < 1.0
        ):
            continue


        await session.send_realtime_input(
            video=types.Blob(
                data=frame_bytes,
                mime_type="image/jpeg"
            )
        )


        last_gemini_frame = current_time

        print(
            "Frame sent to Gemini"
        )


# ============================================================
# Periodically ask Gemini for interpretation
# ============================================================

async def analyze_signs(session):

    while True:

        # Allow several frames to accumulate
        await asyncio.sleep(4)

        print(
            "Asking Gemini to interpret ASL..."
        )

        await session.send_realtime_input(
            text=ASL_PROMPT
        )


# ============================================================
# Receive Gemini's translation
# ============================================================

async def receive_gemini(
    session,
    websocket: WebSocket
):

    previous_translation = None


    while True:

        async for response in session.receive():

            if not response.server_content:
                continue


            transcription = (
                response
                .server_content
                .output_transcription
            )


            if not transcription:
                continue


            text = transcription.text

            if not text:
                continue


            text = text.strip()

            if not text:
                continue


            # Avoid sending same response repeatedly
            if text == previous_translation:
                continue


            previous_translation = text


            print(
                "ASL Translation:",
                text
            )


            # Send translation back to React
            await websocket.send_text(
                text
            )


# ============================================================
# React WebSocket
# ============================================================

@app.websocket("/ws/video")
async def video_websocket(
    websocket: WebSocket
):

    await websocket.accept()

    print(
        "React camera connected"
    )


    config = {
        "response_modalities": [
            "AUDIO"
        ],
        "output_audio_transcription": {},
    }


    frame_task = None
    analysis_task = None
    response_task = None


    try:

        async with client.aio.live.connect(
            model=MODEL,
            config=config
        ) as session:

            print(
                "Gemini Live connected"
            )


            frame_task = asyncio.create_task(
                receive_frames(
                    websocket,
                    session
                )
            )


            analysis_task = asyncio.create_task(
                analyze_signs(
                    session
                )
            )


            response_task = asyncio.create_task(
                receive_gemini(
                    session,
                    websocket
                )
            )


            tasks = {
                frame_task,
                analysis_task,
                response_task
            }


            # If React disconnects or any major
            # task exits, stop the others too.
            done, pending = (
                await asyncio.wait(
                    tasks,
                    return_when=
                    asyncio.FIRST_COMPLETED
                )
            )


            for task in pending:
                task.cancel()


            await asyncio.gather(
                *pending,
                return_exceptions=True
            )


            # Surface unexpected exceptions
            for task in done:

                if task.cancelled():
                    continue

                exception = task.exception()

                if exception:
                    raise exception


    except WebSocketDisconnect:

        print(
            "React camera disconnected"
        )


    except Exception as error:

        print(
            "Backend error:"
        )

        print(
            type(error).__name__,
            error
        )


    finally:

        for task in (
            frame_task,
            analysis_task,
            response_task
        ):

            if task and not task.done():
                task.cancel()


        print(
            "Gemini session closed"
        )