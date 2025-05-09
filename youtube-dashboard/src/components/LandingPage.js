import React, { useRef, useState, useEffect } from 'react';
import ReactPlayer from 'react-player';

const VIDEO_ID = 'Gp-_S5z86NY';
const S3_TRANSCRIPT_URL = `https://video-search-training-bucket.s3.us-east-2.amazonaws.com/transcripts/${VIDEO_ID}.json`;

function LandingPage() {
  const [transcript, setTranscript] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { sender: 'bot', text: 'Hi! Ask me anything about this video.' }
  ]);
  const [currentTime, setCurrentTime] = useState(0);
  const playerRef = useRef(null);
  const transcriptRefs = useRef([]);

  // Fetch transcript from S3
  useEffect(() => {
    fetch(S3_TRANSCRIPT_URL)
      .then(res => res.json())
      .then(data => {
        setTranscript(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Find the current transcript line index
  const currentLineIdx = transcript.reduce((acc, line, idx) => {
    if (currentTime >= line.start) return idx;
    return acc;
  }, 0);

  // Auto-scroll transcript to keep current line in view
  useEffect(() => {
    const node = transcriptRefs.current[currentLineIdx];
    if (node) {
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [currentLineIdx, loading]);

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const userMsg = { sender: 'user', text: chatInput };
    setChatHistory(prev => [...prev, userMsg, { sender: 'bot', text: 'Thinking...' }]);
    setChatInput('');

    try {
      const res = await fetch('/api/llm_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: chatInput, video_id: VIDEO_ID })
      });
      const data = await res.json();
      setChatHistory(prev => [
        ...prev.slice(0, -1), // remove 'Thinking...'
        { sender: 'bot', text: data.answer || data.error || "Sorry, I couldn't find an answer." }
      ]);
    } catch (err) {
      setChatHistory(prev => [
        ...prev.slice(0, -1),
        { sender: 'bot', text: "Error contacting server." }
      ]);
    }
  };

  const handleSeek = (time) => {
    if (playerRef.current) {
      playerRef.current.seekTo(time, 'seconds');
    }
  };

  return (
    <div style={{ fontFamily: 'Arial, sans-serif', maxWidth: 900, margin: '0 auto', padding: 24 }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: 32, color: '#333' }}>Welcome to Clipt</h1>
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', justifyContent: 'center' }}>
        {/* Video Player */}
        <div style={{ flex: '1 1 350px', minWidth: 320 }}>
          <ReactPlayer
            ref={playerRef}
            url={`https://www.youtube.com/watch?v=${VIDEO_ID}`}
            width="100%"
            height="220px"
            controls
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
            onProgress={({ playedSeconds }) => setCurrentTime(playedSeconds)}
          />
        </div>
        {/* Live-Scrolling Transcript */}
        <div style={{ flex: '1 1 300px', minWidth: 260, maxHeight: 320, overflowY: 'auto', background: '#f9f9f9', borderRadius: 10, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <h3 style={{ marginTop: 0, color: '#555' }}>Transcript</h3>
          {loading ? (
            <div>Loading transcript...</div>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {transcript.map((line, idx) => (
                <li
                  key={idx}
                  ref={el => transcriptRefs.current[idx] = el}
                  onClick={() => handleSeek(line.start)}
                  style={{
                    marginBottom: 12,
                    cursor: 'pointer',
                    background: idx === currentLineIdx ? '#d0f0ff' : 'transparent',
                    color: idx === currentLineIdx ? '#007399' : '#222',
                    borderRadius: 6,
                    padding: '4px 8px',
                    transition: 'background 0.2s, color 0.2s',
                    fontWeight: idx === currentLineIdx ? 'bold' : 'normal',
                  }}
                >
                  <span style={{ color: '#888', fontSize: '0.95em', marginRight: 8 }}>
                    {new Date(line.start * 1000).toISOString().substr(14, 5)}
                  </span>
                  <span>{line.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {/* Chatbot Search */}
      <div style={{ marginTop: 40, background: '#fff', borderRadius: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.07)', padding: 24, maxWidth: 600, marginLeft: 'auto', marginRight: 'auto' }}>
        <h3 style={{ color: '#333', marginTop: 0 }}>Chatbot Search</h3>
        <div style={{ maxHeight: 180, overflowY: 'auto', marginBottom: 16, background: '#f5f5f5', borderRadius: 8, padding: 12 }}>
          {chatHistory.map((msg, idx) => (
            <div key={idx} style={{ marginBottom: 10, textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
              <span style={{
                display: 'inline-block',
                background: msg.sender === 'user' ? '#008CBA' : '#eee',
                color: msg.sender === 'user' ? '#fff' : '#333',
                borderRadius: 16,
                padding: '8px 16px',
                maxWidth: '80%',
                wordBreak: 'break-word',
              }}>{msg.text}</span>
            </div>
          ))}
        </div>
        <form onSubmit={handleChatSubmit} style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            placeholder="Ask about the video..."
            style={{ flex: 1, padding: 10, borderRadius: 6, border: '1px solid #ccc', fontSize: '1em' }}
          />
          <button type="submit" style={{ padding: '10px 20px', background: '#008CBA', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>Send</button>
        </form>
      </div>
    </div>
  );
}

export default LandingPage; 