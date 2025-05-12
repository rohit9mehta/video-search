import React, { useRef, useState, useEffect } from 'react';
import ReactPlayer from 'react-player';

const VIDEO_ID = 'Gp-_S5z86NY';
const S3_TRANSCRIPT_URL = `https://video-search-training-bucket.s3.us-east-2.amazonaws.com/transcripts/${VIDEO_ID}.json`;
const YT_URL = `https://www.youtube.com/watch?v=${VIDEO_ID}`;

function LandingPage() {
  const [transcript, setTranscript] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { sender: 'bot', text: 'Hi! Ask me anything about this video.' }
  ]);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeTab, setActiveTab] = useState('transcript');
  const playerRef = useRef(null);
  const transcriptRefs = useRef([]);

  // Add summary state
  const [summary, setSummary] = useState(null);
  const [videoTitle, setVideoTitle] = useState('');

  // Fetch summary from backend
  useEffect(() => {
    fetch(`/api/summary?video_id=${VIDEO_ID}`)
      .then(res => res.json())
      .then(data => {
        if (data.summary) setSummary(data.summary);
      });
  }, []);

  // Fetch video title from YouTube oEmbed
  useEffect(() => {
    fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(YT_URL)}&format=json`)
      .then(res => res.json())
      .then(data => {
        if (data.title) setVideoTitle(data.title);
      })
      .catch(() => setVideoTitle('YouTube Video'));
  }, []);

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
        {
          sender: 'bot',
          text: data.answer || data.error || "Sorry, I couldn't find an answer.",
          timestamp: data.timestamp // may be undefined or null
        }
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
    <div style={{ fontFamily: 'Arial, sans-serif', width: '100vw', height: '100vh', minHeight: 0, minWidth: 0, padding: 0, margin: 0, boxSizing: 'border-box', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Video Title Heading */}
      <h1
        style={{
          textAlign: 'left',
          margin: '24px 0 8px 32px',
          fontSize: '2em',
          color: '#008CBA',
          fontWeight: 700,
          letterSpacing: '-0.5px',
          borderBottom: '1px solid #eee',
          paddingBottom: 8,
          background: '#f9f9f9',
          borderRadius: 0,
          boxShadow: 'none',
          width: 'calc(100% - 32px)',
          maxWidth: 1200,
          flex: '0 0 auto',
        }}
      >
        {videoTitle}
      </h1>
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          gap: 0,
          justifyContent: 'stretch',
          alignItems: 'stretch',
          width: '100%',
          flex: '1 1 0',
          minHeight: 0,
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        {/* Video Player */}
        <div style={{ flex: '2 1 0%', minWidth: 0, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', background: '#000' }}>
          <ReactPlayer
            ref={playerRef}
            url={`https://www.youtube.com/watch?v=${VIDEO_ID}`}
            width="100%"
            height="100%"
            controls
            style={{ borderRadius: 0, boxShadow: 'none', background: '#000' }}
            onProgress={({ playedSeconds }) => setCurrentTime(playedSeconds)}
          />
          <div style={{ background: '#f9f9f9', color: '#222', padding: '18px 24px', borderBottom: '1px solid #eee', fontSize: '1.1em' }}>
            <h3 style={{ margin: '0 0 8px 0', color: '#008CBA' }}>Video Summary</h3>
            {summary ? summary : <span style={{ color: '#888' }}>Loading summary...</span>}
          </div>
        </div>
        {/* Tabbed Panel: Transcript / Chatbot */}
        <div style={{ flex: '1 1 0%', minWidth: 0, height: '100%', background: '#fff', borderRadius: 0, boxShadow: 'none', padding: 0, marginLeft: 0, display: 'flex', flexDirection: 'column', minWidth: 340, maxWidth: 600 }}>
          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid #eee', borderRadius: '0', overflow: 'hidden' }}>
            <button
              onClick={() => setActiveTab('transcript')}
              style={{
                flex: 1,
                padding: '16px 0',
                background: activeTab === 'transcript' ? '#f9f9f9' : '#fff',
                border: 'none',
                borderBottom: activeTab === 'transcript' ? '2px solid #008CBA' : '2px solid transparent',
                color: activeTab === 'transcript' ? '#008CBA' : '#333',
                fontWeight: activeTab === 'transcript' ? 'bold' : 'normal',
                fontSize: '1.1em',
                cursor: 'pointer',
                outline: 'none',
                transition: 'background 0.2s, color 0.2s',
              }}
            >
              Transcript
            </button>
            <button
              onClick={() => setActiveTab('chatbot')}
              style={{
                flex: 1,
                padding: '16px 0',
                background: activeTab === 'chatbot' ? '#f9f9f9' : '#fff',
                border: 'none',
                borderBottom: activeTab === 'chatbot' ? '2px solid #008CBA' : '2px solid transparent',
                color: activeTab === 'chatbot' ? '#008CBA' : '#333',
                fontWeight: activeTab === 'chatbot' ? 'bold' : 'normal',
                fontSize: '1.1em',
                cursor: 'pointer',
                outline: 'none',
                transition: 'background 0.2s, color 0.2s',
              }}
            >
              Chatbot
            </button>
          </div>
          {/* Tab Content */}
          <div style={{ flex: 1, padding: 24, overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            {activeTab === 'transcript' && (
              <div style={{ flex: 1, overflowY: 'auto', background: '#f9f9f9', borderRadius: 8, padding: 12, minHeight: 0 }}>
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
            )}
            {activeTab === 'chatbot' && (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
                <h3 style={{ color: '#333', marginTop: 0 }}>Video Assistant</h3>
                <div style={{ flex: 1, overflowY: 'auto', marginBottom: 16, background: '#f5f5f5', borderRadius: 8, padding: 12, minHeight: 0 }}>
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
                      }}>
                        {msg.text}
                        {msg.timestamp !== undefined && msg.timestamp !== null && (
                          <button 
                            style={{ marginLeft: 8, padding: '4px 10px', borderRadius: 8, border: 'none', background: '#007399', color: '#fff', cursor: 'pointer' }}
                            onClick={() => handleSeek(msg.timestamp)}
                          >
                            Jump to this part
                          </button>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
                <form onSubmit={handleChatSubmit} style={{ display: 'flex', gap: 8, flex: '0 0 auto' }}>
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
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default LandingPage; 