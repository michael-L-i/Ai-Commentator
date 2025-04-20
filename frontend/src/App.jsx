/*
// ✅ frontend/src/App.jsx
import { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [videoURL, setVideoURL] = useState(null)
  const [countdown, setCountdown] = useState(null)
  const [videoReady, setVideoReady] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioOffset, setAudioOffset] = useState(0)
  const audioRef = useRef(null)
  const videoRef = useRef(null)
  const socketRef = useRef(null)
  const pendingAudio = useRef(null)

  useEffect(() => {
    socketRef.current = new WebSocket('ws://localhost:3000')
    socketRef.current.binaryType = 'blob'

    socketRef.current.onopen = () => console.log('🎲 Connected to backend WebSocket')

    socketRef.current.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const metadata = JSON.parse(event.data)
        if (metadata.type === 'audio') {
          setAudioOffset(metadata.offset || 0)
        }
      } else if (event.data instanceof Blob) {
        const audioURL = URL.createObjectURL(event.data)
        const audio = new Audio(audioURL)
        audio.onloadedmetadata = () => {
          audio.currentTime = audioOffset
          audio.play().catch(err => console.warn('Playback error:', err))
        }
        audioRef.current = audio
      }
    }

    return () => socketRef.current?.close()
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      const video = videoRef.current
      if (video && socketRef.current?.readyState === WebSocket.OPEN && !video.paused) {
        socketRef.current.send(
          JSON.stringify({ type: 'sync', currentTime: video.currentTime })
        )
      }
    }, 500)
    return () => clearInterval(interval)
  }, [])

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      const url = URL.createObjectURL(file)
      setVideoURL(url)
      setVideoReady(false)
      setIsPlaying(false)
      setCountdown(null)
    }
  }

  const handleLoadedMetadata = () => {
    const video = videoRef.current
    if (video) {
      video.pause()
      setVideoReady(true)
    }
  }

  const startCountdown = (seconds) => {
    setCountdown(seconds)
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev === 1) {
          clearInterval(interval)
          const video = videoRef.current
          if (video) {
            video.play().then(() => {
              setIsPlaying(true)
              setCountdown(null)
            })
          }
          return null
        }
        return prev - 1
      })
    }, 1000)
  }

  return (
    <div>
      <h1>Poker Sync</h1>
      <input type="file" accept="video/*" onChange={handleFileChange} />

      {videoURL && (
        <video
          ref={videoRef}
          src={videoURL}
          onLoadedMetadata={handleLoadedMetadata}
          controls={false}
          style={{ width: '100%', pointerEvents: 'none', marginTop: '1rem' }}
        />
      )}

      {videoReady && !isPlaying && countdown === null && (
        <button onClick={() => startCountdown(5)}>▶️ Start Video</button>
      )}

      {countdown !== null && <h2>Starting in {countdown}...</h2>}
    </div>
  )
}

export default App
*/


import { useState, useEffect, useRef } from 'react'
import './App.css'

// Hardcoded WebSocket URL to match Flask (or use VITE_WS_URL if you prefer)
const WS_URL = 'ws://localhost:5050'

function App() {
  const [videoURL, setVideoURL] = useState(null)
  const [countdown, setCountdown] = useState(null)
  const [videoReady, setVideoReady] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioOffset, setAudioOffset] = useState(0)

  const audioRef = useRef(null)
  const videoRef = useRef(null)
  const socketRef = useRef(null)

  useEffect(() => {
    console.log('🔌 Connecting to WebSocket: ws://localhost:5050');
    const socket = new WebSocket('ws://localhost:5050');
    socket.binaryType = 'blob';
  
    socket.onopen = () => console.log('✅ Connected to Flask backend');
    socket.onerror = (e) => console.error('❌ WebSocket error:', e);
    socket.onclose = () => console.warn('⚠️ WebSocket closed');
  
    socket.onmessage = (event) => {
      console.log('📦 Received from backend:', event);
      // ... your existing logic here ...
    };
  
    socketRef.current = socket;
    return () => socket.close();
  }, []);
  

  useEffect(() => {
    const interval = setInterval(() => {
      const video = videoRef.current
      if (
        video &&
        socketRef.current?.readyState === WebSocket.OPEN &&
        !video.paused
      ) {
        const msg = JSON.stringify({
          type: 'sync',
          currentTime: video.currentTime,
        })
        socketRef.current.send(msg)
        console.log('⏱ Sent sync:', msg)
      }
    }, 500)

    return () => clearInterval(interval)
  }, [])

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      const url = URL.createObjectURL(file)
      setVideoURL(url)
      setVideoReady(false)
      setIsPlaying(false)
      setCountdown(null)
    }
  }

  const handleLoadedMetadata = () => {
    const video = videoRef.current
    if (video) {
      video.pause()
      setVideoReady(true)
    }
  }

  const startCountdown = (seconds) => {
    setCountdown(seconds)
    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev === 1) {
          clearInterval(interval)
          const video = videoRef.current
          if (video) {
            video.play().then(() => {
              setIsPlaying(true)
              setCountdown(null)
            })
          }
          return null
        }
        return prev - 1
      })
    }, 1000)
  }

  return (
    <div>
      <h1>Poker Sync</h1>
      <input type="file" accept="video/*" onChange={handleFileChange} />

      {videoURL && (
        <video
          ref={videoRef}
          src={videoURL}
          onLoadedMetadata={handleLoadedMetadata}
          controls={false}
          style={{
            width: '100%',
            pointerEvents: 'none',
            marginTop: '1rem',
          }}
        />
      )}

      {videoReady && !isPlaying && countdown === null && (
        <button onClick={() => startCountdown(5)}>▶️ Start Video</button>
      )}

      {countdown !== null && <h2>Starting in {countdown}...</h2>}
    </div>
  )
}

export default App

