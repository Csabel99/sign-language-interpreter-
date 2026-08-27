import asyncio
import cv2
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.1-flash-live-preview"

async def send_camera(session):
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError("Could not open camera")

    try:
        while True:
            success, frame = camera.read()

            if not success:
                continue

            # Show camera locally
            cv2.imshow("Camera", frame)

            # Convert OpenCV frame -> JPEG
            success, encoded_frame = cv2.imencode(".jpg", frame)

            if success:
                jpeg_bytes = encoded_frame.tobytes()

                # Send current camera frame to Gemini
                await session.send_realtime_input(
                    video=types.Blob(
                        data=jpeg_bytes,
                        mime_type="image/jpeg"
                    )
                )

            # Gemini Live video limit is 1 FPS
            await asyncio.sleep(1)

    finally:
        camera.release()
        cv2.destroyAllWindows()


async def ask_gemini(session):
    while True:
        await asyncio.sleep(5)

        await session.send_realtime_input(
            text="""
            Look at the latest camera frames.
            Briefly tell me what you currently see and
            mention anything important that changed.
            """
        )


async def receive_responses(session):
    async for response in session.receive():

        if (
            response.server_content
            and response.server_content.output_transcription
        ):
            print(
                "Gemini:",
                response.server_content.output_transcription.text
            )


async def main():

    config = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
    }

    async with client.aio.live.connect(
        model=MODEL,
        config=config
    ) as session:

        print("Gemini connected to camera.")

        await asyncio.gather(
            send_camera(session),
            ask_gemini(session),
            receive_responses(session),
        )


if __name__ == "__main__":
    asyncio.run(main())