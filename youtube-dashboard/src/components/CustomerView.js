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
    try {
      const ec2ApiUrlQuery = `https://aivideo.planeteria.com/api/query?query_phrase=${encodeURIComponent(queryPhrase)}&channel_url=${encodeURIComponent(channelUrl)}`;
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

  return (
    <div className="App" style={{ fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: '40px', color: '#333' }}>Clipt - AI in-video search</h1>
      <button onClick={() => navigate('/admin')} style={{ position: 'absolute', top: '20px', right: '20px', padding: '10px 20px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}>Go to Admin View</button>
      <div className="section" style={{ marginBottom: '40px' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#555' }}>Query Trained Model</h2>
        <form onSubmit={handleQuerySubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <textarea 
            name="queryPhrase" 
            placeholder="Enter query phrase" 
            style={{ width: '100%', padding: '15px', fontSize: '1.2em', borderRadius: '10px', border: '1px solid #ddd', marginBottom: '15px', minHeight: '100px', resize: 'vertical', fontFamily: 'Arial, sans-serif' }}
          ></textarea>
          <textarea 
            name="channelURL" 
            placeholder="Enter channel URL" 
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '5px', border: '1px solid #ddd', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif' }}
          ></textarea>
          <button 
            type="submit" 
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#008CBA', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', transition: 'background-color 0.3s' }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#007399'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#008CBA'}
          >
            Search
          </button>
        </form>
      </div>
      <div className="results" style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '10px', boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)' }}>
        <h3 style={{ fontSize: '1.5em', marginBottom: '15px', color: '#333' }}>Query Results:</h3>
        {queryResults.length > 0 ? (
          <ul style={{ listStyleType: 'none', padding: 0 }}>
            {queryResults
              .sort((a, b) => (b.metadata?.score || b.score || 0) - (a.metadata?.score || a.score || 0))
              .map((result, index) => (
                <li key={index} style={{ padding: '15px', borderBottom: index < queryResults.length - 1 ? '1px solid #eee' : 'none', backgroundColor: index % 2 === 0 ? '#fff' : '#f5f5f5', borderRadius: '5px' }}>
                  {result.error ? (
                    <span style={{ color: 'red', fontSize: '1em' }}>{result.error}</span>
                  ) : (
                    <>
                      <div style={{ marginBottom: '10px', fontSize: '1em' }}>
                        <b style={{ color: '#333' }}>Match:</b> <span style={{ color: '#555' }}>{result.metadata?.text || result.text || 'Not available'}</span>
                      </div>
                      <div style={{ fontSize: '0.95em' }}>
                        <b style={{ color: '#333' }}>Video URL:</b>{" "}
                        <a href={result.metadata?.url || 'Not available'} target="_blank" rel="noopener noreferrer" style={{ color: '#008CBA', textDecoration: 'none', transition: 'color 0.2s' }}
                          onMouseOver={(e) => e.target.style.color = '#005f73'}
                          onMouseOut={(e) => e.target.style.color = '#008CBA'}
                        >
                          {result.metadata?.url || 'Not available'}
                        </a>
                      </div>
                      {result.metadata?.score && <div style={{ fontSize: '0.9em', color: '#777', marginTop: '5px' }}><b>Score:</b> {result.metadata.score.toFixed(2)}</div>}
                    </>
                  )}
                </li>
              ))}
          </ul>
        ) : (
          <p style={{ color: '#777', fontStyle: 'italic', textAlign: 'center' }}>No results to display.</p>
        )}
      </div>
    </div>
  );
}

export default CustomerView; 