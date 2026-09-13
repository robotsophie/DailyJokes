import React, { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const ROTATION_SECONDS = 30
const ROTATION_MS = ROTATION_SECONDS * 1_000
const CACHE_REFRESH_MS = 10 * 60 * 1000

function App() {
  const [jokes, setJokes] = React.useState([])
  const [index, setIndex] = React.useState(0)
  const [secondsLeft, setSecondsLeft] = React.useState(ROTATION_SECONDS)
  const [status, setStatus] = React.useState('Loading a little joy…')
  const [voted, setVoted] = React.useState(false)

  const loadJokes = React.useCallback(() => {
    return fetch('/api/jokes')
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((items) => {
        if (!items.length) throw new Error('No jokes available')
        setJokes(items)
        setIndex(Math.floor(Math.random() * items.length))
        setStatus('')
      })
      .catch(() => setStatus('The joke drawer is taking a moment. Please refresh.'))
  }, [])

  React.useEffect(() => {
    loadJokes()
    const refresh = window.setInterval(loadJokes, CACHE_REFRESH_MS)
    return () => window.clearInterval(refresh)
  }, [loadJokes])

  React.useEffect(() => {
    if (!jokes.length) return undefined
    setVoted(false)
    setSecondsLeft(ROTATION_SECONDS)
    setStatus('')
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => (current <= 1 ? ROTATION_SECONDS : current - 1))
    }, 1000)
    const rotation = window.setTimeout(() => {
      setIndex((current) => (current + 1) % jokes.length)
    }, ROTATION_MS)
    return () => {
      window.clearInterval(timer)
      window.clearTimeout(rotation)
    }
  }, [index, jokes.length])

  const joke = jokes[index]

  async function castVote(vote) {
    if (!joke || voted) return
    setVoted(true)
    setStatus('')
    setIndex((current) => (current + 1) % jokes.length)
    try {
      const response = await fetch('/api/votes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ joke_id: joke.id, joke_text: joke.text, vote }),
      })
      if (!response.ok) throw new Error('Vote failed')
    } catch {
      setVoted(false)
      setStatus('Your vote could not be saved. Please try again.')
    }
  }

  return (
    <main className="page-shell">
      <section className="joke-card" aria-live="polite">
        <header>
          <p className="eyebrow">A tiny happiness break</p>
          <h1>Laugh Loop</h1>
        </header>

        <div className="joke-copy">
          {joke ? <p>{joke.text}</p> : <p>{status}</p>}
        </div>

        {joke && (
          <footer className="card-footer">
            <div className="vote-panel">
              <div className="vote-group" aria-label="Rate this joke">
                <button className="vote-button" disabled={voted} onClick={() => castVote('up')} aria-label="Funny">
                  <span aria-hidden="true">👍</span> Funny
                </button>
                <button className="vote-button" disabled={voted} onClick={() => castVote('down')} aria-label="Not funny">
                  <span aria-hidden="true">👎</span> Not for me
                </button>
              </div>
              <p className="vote-prompt">Tell us if it’s funny or not to see the next joke.</p>
            </div>
            <p className="rotation-note">Next laugh in {secondsLeft}s</p>
          </footer>
        )}
        {status && joke && <p className="status-message">{status}</p>}
      </section>

      <img className="laughing-cat" src="/api/cat-image?v=2" alt="A laughing cat" />
    </main>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode><App /></StrictMode>,
)
