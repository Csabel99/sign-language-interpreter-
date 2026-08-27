import { useRef, useState } from 'react'

function Camera() {
    const videoRef = useRef<HTMLVideoElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)

    const streamRef = useRef<MediaStream | null>(null)
    const socketRef = useRef<WebSocket | null>(null)
    const intervalRef = useRef<number | null>(null)

    const [isCameraOn, setIsCameraOn] = useState(false)
    const [error, setError] = useState('')
    const [translation, setTranslation] = useState('')


    // -----------------------------------------
    // Connect to Python WebSocket
    // -----------------------------------------

    function connectToBackend() {
        const socket = new WebSocket(
            'ws://localhost:8000/ws/video'
        )

        socket.binaryType = 'arraybuffer'

        socket.onopen = () => {
            console.log('Connected to app.py')
        }

        socket.onmessage = (event) => {
            console.log(
                'Translation from Python:',
                event.data
            )

            setTranslation(event.data)
        }

        socket.onerror = () => {
            console.error('WebSocket error')
            setError('Could not connect to backend.')
        }

        socket.onclose = () => {
            console.log('Disconnected from app.py')
        }

        socketRef.current = socket
    }


    // -----------------------------------------
    // Start camera
    // -----------------------------------------

    async function startCamera() {
        try {
            setError('')
            setTranslation('')

            const stream =
                await navigator.mediaDevices.getUserMedia({
                    video: true,
                    audio: false,
                })

            streamRef.current = stream

            if (videoRef.current) {
                videoRef.current.srcObject = stream
            }

            connectToBackend()

            setIsCameraOn(true)

            // Send ~5 frames per second to Python.
            // Python will decide how often to forward to Gemini.
            intervalRef.current = window.setInterval(
                sendFrame,
                200
            )

        } catch (error) {

            setIsCameraOn(false)

            if (
                error instanceof DOMException &&
                error.name === 'NotAllowedError'
            ) {
                setError(
                    'Camera permission was denied.'
                )
            } else {
                setError(
                    'Unable to access your camera.'
                )
            }
        }
    }


    // -----------------------------------------
    // Capture one video frame
    // -----------------------------------------

    function sendFrame() {
        const video = videoRef.current
        const canvas = canvasRef.current
        const socket = socketRef.current

        if (!video || !canvas || !socket) {
            return
        }

        if (
            socket.readyState !== WebSocket.OPEN
        ) {
            return
        }

        // Camera hasn't finished starting yet
        if (
            video.videoWidth === 0 ||
            video.videoHeight === 0
        ) {
            return
        }

        const context =
            canvas.getContext('2d')

        if (!context) {
            return
        }


        // Reduce frame size before sending
        canvas.width = 640
        canvas.height = 480


        // Copy current camera frame to canvas
        context.drawImage(
            video,
            0,
            0,
            canvas.width,
            canvas.height
        )


        // Convert canvas into JPEG bytes
        canvas.toBlob(
            (blob) => {

                if (!blob) {
                    return
                }

                if (
                    socket.readyState ===
                    WebSocket.OPEN
                ) {
                    socket.send(blob)
                }

            },

            'image/jpeg',

            0.7
        )
    }


    // -----------------------------------------
    // Stop camera
    // -----------------------------------------

    function cameraStop() {

        // Stop sending frames
        if (intervalRef.current !== null) {
            clearInterval(
                intervalRef.current
            )

            intervalRef.current = null
        }


        // Stop browser camera
        streamRef.current
            ?.getTracks()
            .forEach((track) =>
                track.stop()
            )

        streamRef.current = null


        if (videoRef.current) {
            videoRef.current.srcObject = null
        }


        // Close Python WebSocket
        socketRef.current?.close()
        socketRef.current = null


        setIsCameraOn(false)
    }


    // -----------------------------------------
    // UI
    // -----------------------------------------

    return (
        <div className="mx-auto w-full max-w-3xl rounded-lg bg-white p-6 shadow-lg">

            <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="aspect-video w-full rounded-md bg-slate-100 object-cover"
            />

            {/* Used only for grabbing frames */}
            <canvas
                ref={canvasRef}
                className="hidden"
            />


            <button
                type="button"
                onClick={
                    isCameraOn
                        ? cameraStop
                        : startCamera
                }
                className="mt-4 rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
            >
                {
                    isCameraOn
                        ? 'Stop camera'
                        : 'Start camera'
                }
            </button>


            {error && (
                <p className="mt-3 text-red-500">
                    {error}
                </p>
            )}


            <div className="mt-6 rounded-md bg-slate-100 p-4">

                <p className="text-sm font-semibold text-slate-500">
                    ASL Translation
                </p>

                <p className="mt-2 text-2xl font-bold">
                    {
                        translation ||
                        'Waiting for a sign...'
                    }
                </p>

            </div>

        </div>
    )
}

export default Camera