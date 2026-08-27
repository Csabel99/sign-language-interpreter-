import {useEffect, useRef, useState} from 'react'

function Camera() {
    const videoRef = useRef<HTMLVideoElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const streamRef = useRef<MediaStream | null>(null)
    const socketRef = useRef<WebSocket | null>(null)
    const captureTimerRef = useRef<number | null>(null)

    const [isCameraOn, setIsCameraOn] = useState(false)
    const [error, setError] = useState('')
    const [translation, setTranslation] = useState('')

    function stopConnection() {
        if (captureTimerRef.current !== null) {
            window.clearInterval(captureTimerRef.current)
            captureTimerRef.current = null
        }
        socketRef.current?.close()
        socketRef.current = null
    }

    // turning on the camera, checking if allowed
    async function startCamera() {
        try{
            setError('')

            // request only camera, no microphone
            const stream = await navigator.mediaDevices.getUserMedia({video: true, audio: false,})
            streamRef.current = stream
            if(videoRef.current){
                videoRef.current.srcObject = stream
            }

            const socket = new WebSocket(
                `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/translate`,
            )
            socket.onmessage = (event) => {
                const message = JSON.parse(event.data) as {text?: string; error?: string}
                if (message.text) setTranslation(message.text)
                if (message.error) setError(message.error)
            }
            socket.onerror = () => setError('Unable to connect to the translation server.')
            socketRef.current = socket

            socket.onopen = () => {
                captureTimerRef.current = window.setInterval(() => {
                    const video = videoRef.current
                    const canvas = canvasRef.current
                    if (!video || !canvas || video.readyState < 2) return

                    canvas.width = video.videoWidth
                    canvas.height = video.videoHeight
                    canvas.getContext('2d')?.drawImage(video, 0, 0)
                    const data = canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
                    if (socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({type: 'frame', data}))
                    }
                }, 1000)
            }
            setIsCameraOn(true)
        
        }catch(error){
            setIsCameraOn(false)

            // error message
            if(error instanceof DOMException && error.name == "NotAllowedError"){
                setError('Camera permission was denied.')
            }else{
                setError('Unable to access your camera.')
            }
        }
    }

    // stop camera 
    function cameraStop(){
        stopConnection()
        streamRef.current?.getTracks().forEach((track)=> track.stop())
        streamRef.current = null

        if(videoRef.current){
            videoRef.current.srcObject = null
        }

        setIsCameraOn(false)
    }

    useEffect(() => () => cameraStop(), [])
    return (
        <div className="mx-auto w-full max-w-3xl rounded-lg bg-white p-6 shadow-lg">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="aspect-video w-full rounded-md bg-slate-100 object-cover"
            />
            <canvas ref={canvasRef} className="hidden" />
            <button
                type="button"
                onClick={isCameraOn ? cameraStop : startCamera}
                className="mt-4 rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
            >
                {isCameraOn ? 'Stop camera' : 'start camera'}
            </button>

            {error && <p>{error}</p>}

            <label htmlFor="translation" className="mt-4 block text-left font-bold">
                Translation
            </label>
            <textarea
                id="translation"
                value={translation}
                readOnly
                placeholder="Your translation will appear here"
                rows={3}
                className="mt-2 w-full resize-none rounded border p-3"
            />


        </div>
    )
}

export default Camera