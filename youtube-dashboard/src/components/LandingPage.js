import React, { useRef, useState, useEffect } from 'react';
import ReactPlayer from 'react-player';
import { useParams } from 'react-router-dom';

function LandingPage() {
  const { videoId } = useParams();
  const VIDEO_ID = videoId;
  const S3_TRANSCRIPT_URL = `https://video-search-training-bucket.s3.us-east-2.amazonaws.com/transcripts/${VIDEO_ID}.json`;
  const YT_URL = `https://www.youtube.com/watch?v=${VIDEO_ID}`;
  const S3_SUMMARY_URL = `https://video-search-training-bucket.s3.us-east-2.amazonaws.com/summaries/${VIDEO_ID}.json`;
  const [transcript, setTranscript] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeTab, setActiveTab] = useState('transcript');
  const playerRef = useRef(null);
  const transcriptRefs = useRef([]);

  // Add summary state
  const [summary, setSummary] = useState(null);
  const [videoTitle, setVideoTitle] = useState('');

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

  // Fetch summary directly from S3
  useEffect(() => {
    fetch(S3_SUMMARY_URL)
      .then(res => res.json())
      .then(data => {
        setSummary(data.summary || data);
      })
      .catch(() => setSummary(null));
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
            {summary === null
              ? <span style={{ color: '#888' }}>Summary not available or still processing.</span>
              : summary}
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
              Video Chat
            </button>
          </div>
          {/* Tab Content */}
          <div style={{ flex: 1, padding: 24, overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            {activeTab === 'transcript' && (
              <div style={{ flex: 1, overflowY: 'auto', background: '#f9f9f9', borderRadius: 8, padding: 12, minHeight: 0 }}>
                <h3 style={{ marginTop: 0, color: '#555' }}>Transcript</h3>
                {loading ? (
                  <div>Loading transcript...</div>
                ) : transcript.length === 0 ? (
                  <div style={{ color: '#888' }}>Transcript not available or still processing.</div>
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
                {/* Sleek Quick Answers Header */}
                <div style={{ marginBottom: 8, marginTop: 4 }}>
                  <div style={{ fontSize: '1.1em', fontWeight: 700, color: '#2196f3', marginBottom: 2 }}>
                    Need some quick answers <span style={{ color: '#1976d2' }}>related to this meeting?</span>
                  </div>
                  <div style={{ color: '#555', fontSize: '0.97em', marginBottom: 8 }}>
                    Here is a selection of some of the most popular prompts for you to choose from.
                  </div>
                </div>
                {/* Prompt grid fills all available space above input box if no chat history */}
                {chatHistory.length === 0 && (
                  <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                    {[
                      {
                        q: 'Provide a general overview of the topics discussed.',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="12" height="12" rx="3"/><line x1="6" y1="6" x2="12" y2="6"/><line x1="6" y1="9" x2="12" y2="9"/><line x1="6" y1="12" x2="9" y2="12"/></svg>
                        )
                      },
                      {
                        q: 'Who were the meeting attendees?',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="7" cy="6" r="3"/><circle cx="13" cy="8" r="2.2"/><path d="M2 15c0-2.7 3.8-4.2 5.3-4.2s5.3 1.5 5.3 4.2"/><path d="M11 15c0-1.1 1.6-1.8 2.4-1.8s2.4 0.7 2.4 1.8"/></svg>
                        )
                      },
                      {
                        q: 'Provide details on any bids discussed.',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="2.5" y="5" width="13" height="9" rx="1.5"/><path d="M12.5 2.5v2.5"/><path d="M5.5 2.5v2.5"/><line x1="2.5" y1="8.5" x2="15.5" y2="8.5"/></svg>
                        )
                      },
                      {
                        q: 'Were there any specific projects discussed?',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="12" height="12" rx="3"/><path d="M6 9h6M6 12h3"/></svg>
                        )
                      },
                      {
                        q: 'Are there any funding opportunities or grants discussed?',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="9" r="7.2"/><path d="M9 5.5v3.5l2.2 2.2"/></svg>
                        )
                      },
                      {
                        q: 'Summarize any discussions on awarded contracts.',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="12" height="12" rx="3"/><path d="M6 6h6M6 9h6M6 12h3"/></svg>
                        )
                      },
                      {
                        q: 'Any future plans or projects discussed?',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="9" r="7.2"/><path d="M9 4.5v4l3 1.5"/></svg>
                        )
                      },
                      {
                        q: 'List any vendors mentioned in the discussion.',
                        icon: (
                          <svg width="18" height="18" fill="none" stroke="#1976d2" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="2.5" y="5" width="13" height="9" rx="1.5"/><path d="M12.5 2.5v2.5"/><path d="M5.5 2.5v2.5"/></svg>
                        )
                      },
                    ].map(({ q, icon }) => (
                      <button
                        key={q}
                        type="button"
                        onClick={async () => {
                          setChatHistory(prev => [...prev, { sender: 'user', text: q }, { sender: 'bot', text: 'Thinking...' }]);
                          setChatInput('');
                          try {
                            const res = await fetch('/api/llm_chat', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ question: q, video_id: VIDEO_ID })
                            });
                            const data = await res.json();
                            setChatHistory(prev => [
                              ...prev.slice(0, -1),
                              {
                                sender: 'bot',
                                text: data.answer || data.error || "Sorry, I couldn't find an answer.",
                                timestamp: data.timestamp
                              }
                            ]);
                          } catch (err) {
                            setChatHistory(prev => [
                              ...prev.slice(0, -1),
                              { sender: 'bot', text: "Error contacting server." }
                            ]);
                          }
                        }}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          background: '#fff', color: '#1976d2', border: '1px solid #e3eaf3',
                          borderRadius: 10, padding: '8px 8px', fontSize: '0.97em', fontWeight: 500,
                          cursor: 'pointer', boxShadow: '0 1px 4px rgba(33,150,243,0.04)',
                          transition: 'background 0.18s, box-shadow 0.18s, border 0.18s',
                          minHeight: 36,
                          textAlign: 'left',
                          outline: 'none',
                        }}
                        onMouseOver={e => {
                          e.currentTarget.style.background = '#f5faff';
                          e.currentTarget.style.border = '1.5px solid #b3d6f7';
                          e.currentTarget.style.boxShadow = '0 2px 8px rgba(33,150,243,0.10)';
                        }}
                        onMouseOut={e => {
                          e.currentTarget.style.background = '#fff';
                          e.currentTarget.style.border = '1px solid #e3eaf3';
                          e.currentTarget.style.boxShadow = '0 1px 4px rgba(33,150,243,0.04)';
                        }}
                      >
                        <span style={{ display: 'flex', alignItems: 'center' }}>{icon}</span>
                        <span style={{ flex: 1 }}>{q}</span>
                      </button>
                    ))}
                  </div>
                )}
                {/* Only show chat history if there are messages */}
                {chatHistory.length > 0 && (
                  <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                    <div style={{ flex: 1, overflowY: 'auto', marginBottom: 10, background: '#f5f5f5', borderRadius: 8, padding: 10, minHeight: 0 }}>
                      {chatHistory.map((msg, idx) => (
                        <div key={idx} style={{ marginBottom: 8, textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
                          <span style={{
                            display: 'inline-block',
                            background: msg.sender === 'user' ? '#008CBA' : '#eee',
                            color: msg.sender === 'user' ? '#fff' : '#333',
                            borderRadius: 14,
                            padding: '7px 14px',
                            maxWidth: '80%',
                            wordBreak: 'break-word',
                            fontSize: '0.97em',
                          }}>
                            {msg.text}
                            {msg.timestamp !== undefined && msg.timestamp !== null && (
                              <button 
                                style={{ marginLeft: 8, padding: '3px 8px', borderRadius: 7, border: 'none', background: '#007399', color: '#fff', cursor: 'pointer', fontSize: '0.93em' }}
                                onClick={() => handleSeek(msg.timestamp)}
                              >
                                Jump to this part
                              </button>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Input box always at the bottom */}
                <form onSubmit={handleChatSubmit} style={{ display: 'flex', gap: 7, flex: '0 0 auto', background: '#fff', borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.03)', padding: '7px 7px 7px 12px', alignItems: 'center', marginTop: chatHistory.length > 0 ? 0 : 'auto' }}>
                  <input
                    id="chat-input-box"
                    type="text"
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    placeholder="Ask anything else about the video..."
                    style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #ccc', fontSize: '1em', background: '#fafcff' }}
                  />
                  <button type="submit" style={{ padding: '8px 18px', background: '#008CBA', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 500, fontSize: '1em' }}>Send</button>
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