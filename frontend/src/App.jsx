// frontend/src/App.jsx
import { useState, useEffect, useRef } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:5050'
const POLL_INTERVAL = 100 // ms

function PokerSync() {
  const [videoURL, setVideoURL] = useState(null)
  const [countdown, setCountdown] = useState(null)
  const [videoReady, setVideoReady] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)

  const audioRef = useRef(null)
  const videoRef = useRef(null)
  const lastPlayed = useRef(null)

  // Poll every POLL_INTERVAL ms for next audio
  useEffect(() => {
    let interval
    if (videoReady) {
      interval = setInterval(async () => {
        const video = videoRef.current
        if (video && !video.paused) {
          const t = video.currentTime
          try {
            const res = await fetch(`${API}/next-audio?time=${t}`)
            const { filename, offset } = await res.json()
            if (filename && filename !== lastPlayed.current) {
              lastPlayed.current = filename
              audioRef.current?.pause()
              const blob = await fetch(`${API}/audio/${filename}`).then(r => r.blob())
              const url = URL.createObjectURL(blob)
              const audio = new Audio(url)
              audio.onloadedmetadata = () => {
                audio.currentTime = offset
                audio.play().catch(console.warn)
              }
              audioRef.current = audio
            }
          } catch (e) {
            console.error('Polling error', e)
          }
        }
      }, POLL_INTERVAL)
    }
    return () => clearInterval(interval)
  }, [videoReady])

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      const url = URL.createObjectURL(file)
      setVideoURL(url)
      setVideoReady(false)
      setIsPlaying(false)
      setCountdown(null)
      lastPlayed.current = null
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
          videoRef.current.play().then(() => setIsPlaying(true))
          return null
        }
        return prev - 1
      })
    }, 1000)
  }

  return (
    <div style={styles.table}>
      <header style={styles.header}>
        <h1 style={styles.title}>♠︎ PokerSync ♥︎</h1>
        <p style={styles.tagline}>Your AI Poker Commentary Table</p>
      </header>

      <div style={styles.uploadSection}>
        <label style={styles.fileLabel}>
          <input
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            style={styles.fileInput}
          />
          Choose Your Hand
        </label>
      </div>

      {videoURL && (
        <div style={styles.videoWrapper}>
          <video
            ref={videoRef}
            src={videoURL}
            onLoadedMetadata={handleLoadedMetadata}
            controls={false}
            style={styles.video}
          />
        </div>
      )}

      <div style={styles.controls}>
        {videoReady && !isPlaying && countdown === null && (
          <button style={styles.actionButton} onClick={() => startCountdown(5)}>
            ♦︎ Deal in 5s ♦︎
          </button>
        )}
        {countdown !== null && (
          <span style={styles.countdown}>Starting in {countdown}...</span>
        )}
      </div>
    </div>
  )
}

const styles = {
  table: {
    backgroundColor: '#014421',
    width: '100%',          // full width
    minHeight: '100vh',
    padding: '2rem',
    color: '#f8f1e5',
    fontFamily: 'Georgia, serif',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'stretch'   // stretch children to full width
  },
  header: {
    textAlign: 'center',
    marginBottom: '2rem'
  },
  title: {
    fontSize: '3rem',
    margin: 0,
    letterSpacing: '0.1em'
  },
  tagline: {
    fontSize: '1.25rem',
    fontStyle: 'italic',
    color: '#d4af37'
  },
  uploadSection: {
    marginBottom: '1.5rem',
    display: 'flex',
    justifyContent: 'center'
  },
  fileLabel: {
    backgroundColor: '#d4af37',
    padding: '0.75rem 1.5rem',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 'bold',
    color: '#014421'
  },
  fileInput: {
    display: 'none'
  },
  videoWrapper: {
    position: 'relative',
    paddingBottom: '56.25%',
    height: 0,
    width: '100%',
    marginBottom: '1.5rem'
  },
  video: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    border: '4px solid #d4af37',
    borderRadius: '8px'
  },
  controls: {
    textAlign: 'center',
    marginTop: '1rem'
  },
  actionButton: {
    backgroundColor: '#bb0a21',
    color: '#fff',
    padding: '0.75rem 2rem',
    fontSize: '1rem',
    border: 'none',
    borderRadius: '25px',
    cursor: 'pointer',
    boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
    transition: 'transform 0.1s ease'
  },
  countdown: {
    fontSize: '1.5rem',
    marginTop: '0.5rem'
  }
}

export default PokerSync