import {useRef, useState} from 'react'

function Camera() {
    const videoRef = useRef<HTMLVideoElement>(null)
    const streamRef = useRef<MediaStream | null>(null)

    const [isCameraOn, setIsCameraOn] = useState(false)
    const [error, setError] = useState('')

    // turning on the camera, checking if allowed
    async function startCamera() {
        try{
            setError('')

            // request only camera, no microphone
            const stream = await navigator.mediaDevices.getUserMedia({video: true, audio: false,})
            streamRef.current = stream
            if(videoRef.current){
                videoRef.current.srcObject = stream
            }setIsCameraOn(true)
        
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
        streamRef.current?.getTracks().forEach((track)=> track.stop())
        streamRef.current = null

        if(videoRef.current){
            videoRef.current.srcObject = null
        }

        setIsCameraOn(false)
    }
    return (
        <div className="mx-auto w-full max-w-3xl rounded-lg bg-white p-6 shadow-lg">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="aspect-video w-full rounded-md bg-slate-100 object-cover"
            />
            <button
                type="button"
                onClick={isCameraOn ? cameraStop : startCamera}
                className="mt-4 rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
            >
                {isCameraOn ? 'Stop camera' : 'start camera'}
            </button>

            {error && <p>{error}</p>}


        </div>
    )
}

export default Camera