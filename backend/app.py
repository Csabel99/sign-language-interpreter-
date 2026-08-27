import asyncio
import cv2
import os
import mediapipe as mp
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# MediaPipe setup
# ============================================================

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


# ============================================================
# Gemini setup
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY not found")

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.1-flash-live-preview"


# ============================================================
# Camera + MediaPipe
# ============================================================

async def send_camera(session):

    # More stable webcam backend for Windows
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        raise RuntimeError("Could not open camera")

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    last_send_time = 0

    # Create MediaPipe hand tracker
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:

        try:

            while True:

                success, frame = camera.read()

                if not success:
                    print("Failed to read camera frame")
                    await asyncio.sleep(0.05)
                    continue


                # ====================================================
                # Mirror camera
                # ====================================================

                frame = cv2.flip(frame, 1)


                # ====================================================
                # Convert BGR -> RGB for MediaPipe
                # ====================================================

                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                # Helps performance slightly
                rgb_frame.flags.writeable = False

                results = hands.process(rgb_frame)

                rgb_frame.flags.writeable = True


                # ====================================================
                # Did MediaPipe find any hands?
                # ====================================================

                hand_detected = (
                    results.multi_hand_landmarks is not None
                )


                # ====================================================
                # Draw MediaPipe landmarks
                # ====================================================

                display_frame = frame.copy()

                if hand_detected:

                    for hand_landmarks in results.multi_hand_landmarks:

                        mp_drawing.draw_landmarks(
                            display_frame,
                            hand_landmarks,
                            mp_hands.HAND_CONNECTIONS,

                            mp_drawing_styles
                            .get_default_hand_landmarks_style(),

                            mp_drawing_styles
                            .get_default_hand_connections_style()
                        )


                    # Display status
                    cv2.putText(
                        display_frame,
                        f"Hands detected: {len(results.multi_hand_landmarks)}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                else:

                    cv2.putText(
                        display_frame,
                        "No hands detected",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2
                    )


                # ====================================================
                # Show camera + hand tracking
                # ====================================================

                cv2.imshow(
                    "ASL Hand Tracking",
                    display_frame
                )

                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    print("Stopping camera...")
                    break


                # ====================================================
                # Send frame to Gemini
                # ====================================================

                current_time = time.monotonic()

                # Only send when:
                #
                # 1. MediaPipe sees a hand
                # 2. At least one second passed
                #
                if (
                    hand_detected
                    and current_time - last_send_time >= 1
                ):

                    # Send ORIGINAL image to Gemini rather than
                    # landmark overlay so Gemini can see the hand
                    # naturally.

                    success, encoded_frame = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 70]
                    )

                    if success:

                        jpeg_bytes = encoded_frame.tobytes()

                        try:

                            await session.send_realtime_input(
                                video=types.Blob(
                                    data=jpeg_bytes,
                                    mime_type="image/jpeg"
                                )
                            )

                            print(
                                "Hand detected -> frame sent to Gemini"
                            )

                        except Exception as e:

                            print(
                                "Gemini frame error:",
                                e
                            )

                            break

                    last_send_time = current_time


                # Allow other asyncio tasks to execute
                await asyncio.sleep(0.01)


        except asyncio.CancelledError:

            print("Camera task cancelled")
            raise


        except Exception as e:

            print("Camera error:")
            print(type(e).__name__, e)


        finally:

            camera.release()

            cv2.destroyAllWindows()

            print("Camera released")


# ============================================================
# Gemini ASL prompt
# ============================================================

async def ask_gemini(session):

    asl_prompt = """
You are an American Sign Language (ASL) interpretation system.

The camera frames provided to you contain a person whose hands
have already been detected by a hand-tracking system.

Your only task is to recognize valid American Sign Language
and translate it into natural English.

Pay attention to:

- Hand shape
- Finger positions
- Palm orientation
- Hand location
- Hand movement
- Movement direction
- Whether one or two hands are being used
- The sequence of signs across recent video frames
- Facial expression only when necessary for ASL meaning

Rules:

- Only interpret American Sign Language.
- Ignore ordinary hand movements that are not ASL.
- Ignore the background.
- Ignore clothing and unrelated objects.
- Do not describe the person's hands.
- Do not describe what is happening in the scene.
- Do not explain your reasoning.
- Do not guess.
- Do not interpret random gestures as ASL.
- Consider recent frames together because ASL signs may involve movement.
- If multiple signs form a phrase, translate the complete phrase.
- Do not repeat a translation unless a new sign has been performed.

If you confidently recognize an ASL sign:

Return ONLY its natural English translation.

Example:

Hello

or:

Thank you

or:

How are you?

If the sign cannot be confidently recognized,
do not provide a translation.
"""

    try:

        while True:

            # Give Gemini several frames to look at
            await asyncio.sleep(4)

            await session.send_realtime_input(
                text=asl_prompt
            )

            print("Gemini analyzing ASL...")


    except asyncio.CancelledError:

        raise


    except Exception as e:

        print("Gemini prompt error:")
        print(type(e).__name__, e)


# ============================================================
# Receive Gemini output
# ============================================================

async def receive_responses(session):

    try:

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

                if text:

                    print(
                        "\nASL Translation:",
                        text
                    )


    except asyncio.CancelledError:

        raise


    except Exception as e:

        print("Gemini receive error:")
        print(type(e).__name__, e)


# ============================================================
# Main
# ============================================================

async def main():

    config = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
    }

    try:

        async with client.aio.live.connect(
            model=MODEL,
            config=config
        ) as session:

            print("Gemini connected.")
            print("Starting MediaPipe hand tracking...")
            print("Press Q to quit.\n")


            camera_task = asyncio.create_task(
                send_camera(session)
            )

            ask_task = asyncio.create_task(
                ask_gemini(session)
            )

            receive_task = asyncio.create_task(
                receive_responses(session)
            )


            try:

                await camera_task


            finally:

                ask_task.cancel()
                receive_task.cancel()

                await asyncio.gather(
                    ask_task,
                    receive_task,
                    return_exceptions=True
                )


    except Exception as e:

        print("Gemini connection error:")
        print(type(e).__name__, e)


# ============================================================
# Start program
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
    