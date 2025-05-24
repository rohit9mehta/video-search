import React from 'react';
import { useNavigate } from 'react-router-dom';

function CustomerView() {
  const navigate = useNavigate();
  const [queryResults, setQueryResults] = React.useState([]);
  const backendUrl = 'https://aivideo.planeteria.com';

  const handleQuerySubmit = async (event) => {
    event.preventDefault();
    const queryPhrase = event.target.queryPhrase.value;
    const channelUrl = event.target.channelURL.value;
    const customerKey = event.target.customerKey.value;
    try {
      const ec2ApiUrlQuery = `https://aivideo.planeteria.com/api/query?query_phrase=${encodeURIComponent(queryPhrase)}&channel_url=${encodeURIComponent(channelUrl)}&customer_key=${encodeURIComponent(customerKey)}`;
      const response = await fetch(ec2ApiUrlQuery, {
        credentials: 'include'
      });

      if (response.status === 401) {
        alert("You are not authenticated. Redirecting to login...");
        window.location.href = `${backendUrl}/login`;
        return;
      }
      const results = await response.json();
      setQueryResults(results || []);
    } catch (error) {
      setQueryResults([{ error: "Error occurred during query. Please try again." }]);
    }
  };

  // Helper to group results by video_id
  function groupByVideo(results) {
    const groups = {};
    results.forEach(result => {
      let videoId = result.metadata?.video_id;
      // Fallback: try to extract from URL if not present
      if (!videoId && result.metadata?.url) {
        const match = result.metadata.url.match(/[?&]v=([^&]+)/);
        if (match) videoId = match[1];
      }
      if (!videoId) videoId = 'unknown';
      if (!groups[videoId]) groups[videoId] = [];
      groups[videoId].push(result);
    });
    return groups;
  }

  return (
    <div className="App" style={{ fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: '0 auto', padding: '20px', background: '#f9fbfd', color: '#232946' }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: '40px', color: '#1976d2', fontWeight: 700, letterSpacing: '-0.5px', background: '#f6faff', borderRadius: 12, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}>Clipt - AI in-video search</h1>
      <button onClick={() => navigate('/admin')} style={{ position: 'absolute', top: '20px', right: '20px', padding: '10px 20px', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}>Go to Admin View</button>
      <div className="section clipt-card" style={{ marginBottom: '40px' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#232946' }}>Query Trained Model</h2>
        <form onSubmit={handleQuerySubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <textarea 
            name="queryPhrase" 
            placeholder="Enter query phrase" 
            style={{ width: '100%', padding: '15px', fontSize: '1.2em', borderRadius: '10px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '100px', resize: 'vertical', fontFamily: 'Arial, sans-serif', background: '#f9fbfd', color: '#232946' }}
          ></textarea>
          <textarea 
            name="channelURL" 
            placeholder="Enter channel URL" 
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', background: '#f9fbfd', color: '#232946' }}
          ></textarea>
          <textarea 
            name="customerKey" 
            placeholder="Enter customer key" 
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '30px', resize: 'vertical', fontFamily: 'Arial, sans-serif', background: '#f9fbfd', color: '#232946' }}
          ></textarea>
          <button 
            type="submit" 
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}
          >
            Search
          </button>
        </form>
      </div>
      <div className="results clipt-card" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '1.5em', marginBottom: '15px', color: '#232946' }}>Query Results:</h3>
        {queryResults.length > 0 ? (
          Object.entries(groupByVideo(queryResults)).map(([videoId, results]) => (
            <div key={videoId} style={{ marginBottom: '32px', border: '1px solid #e3eaf3', borderRadius: 12, padding: 16, background: '#fff' }}>
              <h4 style={{ color: '#1976d2', marginBottom: '12px' }}>Video: {videoId}</h4>
              <ul style={{ listStyleType: 'none', padding: 0 }}>
                {results
                  .sort((a, b) => (b.metadata?.score || b.score || 0) - (a.metadata?.score || a.score || 0))
                  .map((result, index) => (
                    <li key={index} style={{ padding: '15px', borderBottom: index < results.length - 1 ? '1px solid #e3eaf3' : 'none', backgroundColor: index % 2 === 0 ? '#f9fbfd' : '#f6faff', borderRadius: '8px' }}>
                      {result.error ? (
                        <span style={{ color: 'red', fontSize: '1em' }}>{result.error}</span>
                      ) : (
                        <>
                          <div style={{ marginBottom: '10px', fontSize: '1em' }}>
                            <b style={{ color: '#232946' }}>Match:</b> <span style={{ color: '#555' }}>{result.metadata?.text || result.text || 'Not available'}</span>
                          </div>
                          <div style={{ fontSize: '0.95em' }}>
                            <b style={{ color: '#232946' }}>Video URL:</b>{' '}
                            {(() => {
                              const ytUrl = result.metadata?.url || '';
                              let landingUrl = 'Not available';
                              if (ytUrl && ytUrl.includes('youtube.com/watch')) {
                                const match = ytUrl.match(/[?&]v=([^&]+).*?[&]t=(\d+)/);
                                if (match) {
                                  const videoId = match[1];
                                  const t = match[2];
                                  landingUrl = `https://aivideo.planeteria.com/${videoId}?t=${t}`;
                                } else {
                                  // fallback: try to extract videoId only
                                  const idMatch = ytUrl.match(/[?&]v=([^&]+)/);
                                  if (idMatch) {
                                    const videoId = idMatch[1];
                                    landingUrl = `https://aivideo.planeteria.com/${videoId}`;
                                  }
                                }
                              }
                              return (
                                <a href={landingUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'none', transition: 'color 0.2s' }}
                                  onMouseOver={e => e.target.style.color = '#005f73'}
                                  onMouseOut={e => e.target.style.color = '#1976d2'}
                                >
                                  {landingUrl}
                                </a>
                              );
                            })()}
                          </div>
                          {result.metadata?.score && <div style={{ fontSize: '0.9em', color: '#777', marginTop: '5px' }}><b>Score:</b> {result.metadata.score.toFixed(2)}</div>}
                        </>
                      )}
                    </li>
                  ))}
              </ul>
            </div>
          ))
        ) : (
          <p style={{ color: '#777', fontStyle: 'italic', textAlign: 'center' }}>No results to display.</p>
        )}
      </div>
    </div>
  );
}

export default CustomerView; 