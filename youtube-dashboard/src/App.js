import './App.css';
import React from 'react';

function App() {

  const [message, setMessage] = React.useState(""); // State to store the API response
  const [queryResults, setQueryResults] = React.useState([]); // State for query results
  const [videoTrainMessage, setVideoTrainMessage] = React.useState(""); // State to store the single video training response
  const backendUrl = 'https://aivideo.planeteria.com';
  const handleSubmit = async (event) => {
    event.preventDefault();
    const channelUrl = event.target.channelURL.value;
    try {
        const e2ApiUrlTrain = 'https://aivideo.planeteria.com/api/train';
        // Call backend API to trigger training
        const response = await fetch(e2ApiUrlTrain, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ channel_url: channelUrl }),
        });
        const data = await response.json();
        setMessage(data.message || "Training completed!");
    } catch (error) {
        setMessage("Error occurred during training. Please try again.");
    }
  };

  const handleQuerySubmit = async (event) => {
    event.preventDefault();
    const queryPhrase = event.target.queryPhrase.value;
    const channelUrl = event.target.channelURL.value;
    try {
        // Call backend API to trigger query
        const ec2ApiUrlQuery = `https://aivideo.planeteria.com/api/query?query_phrase=${encodeURIComponent(queryPhrase)}&channel_url=${encodeURIComponent(channelUrl)}`;
        const response = await fetch(ec2ApiUrlQuery, {
          credentials: 'include'
        });

        if (response.status === 401) {
          alert("You are not authenticated. Redirecting to login...");
          window.location.href = `${backendUrl}/login`;  // Redirect to login page
          return;
        }
        const results = await response.json()
        // Save the results to state
        setQueryResults(results || []);
    } catch (error) {
        setQueryResults([{ error: "Error occurred during query. Please try again." }]);
    }
  };

  const handleVideoSubmit = async (event) => {
    event.preventDefault();
    const channelUrl = event.target.channelURL.value;
    const videoUrl = event.target.videoURL.value;
    try {
        const e2ApiUrlTrainVideo = 'https://aivideo.planeteria.com/api/train_video';
        // Call backend API to trigger training on a single video
        const response = await fetch(e2ApiUrlTrainVideo, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ channel_url: channelUrl, video_url: videoUrl }),
        });
        const data = await response.json();
        setVideoTrainMessage(data.message || "Video training started!");
    } catch (error) {
        setVideoTrainMessage("Error occurred during video training. Please try again.");
    }
  };

  return (
    <div className="App">
      {/* Section 1: Train on Channel URL */}
      <div className="section">
        <h2>Train on Channel URL</h2>
        <form onSubmit={handleSubmit}>
          <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
          <button type="submit">Train Model</button>
        </form>
        {message && <div className="message">{message}</div>}
      </div>

      {/* Section 2: Add Video to Trained Model */}
      <div className="section">
        <h2>Add Video to Trained Model</h2>
        <form onSubmit={handleVideoSubmit}>
          <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
          <textarea name="videoURL" placeholder="Enter video URL"></textarea>
          <button type="submit">Train on Video</button>
        </form>
        {videoTrainMessage && <div className="message">{videoTrainMessage}</div>}
      </div>

      {/* Section 3: Query */}
      <div className="section">
        <h2>Query Trained Model</h2>
        <form onSubmit={handleQuerySubmit}>
          <textarea name="queryPhrase" placeholder="Enter query phrase"></textarea>
          <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
          <button type="submit">Query Model</button>
        </form>
      </div>

      {/* Display Query Results */}
      <div className="results">
        <h3>Query Results:</h3>
        {queryResults.length > 0 ? (
          <ul>
            {queryResults.map((result, index) => (
              <li key={index}>
                {result.error ? (
                  <span>{result.error}</span>
                ) : (
                  <>
                    <b>Match:</b> {result.text} <br />
                    <b>Video URL:</b>{" "}
                    <a href={result.metadata.url} target="_blank" rel="noopener noreferrer">
                      {result.metadata.url}
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>No results to display.</p>
        )}
      </div>
    </div>
  );
}


export default App;
