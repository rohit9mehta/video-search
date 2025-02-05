import './App.css';
import React from 'react';

function App() {

  const [message, setMessage] = React.useState(""); // State to store the API response
  const [queryResults, setQueryResults] = React.useState([]); // State for query results
  const handleSubmit = async (event) => {
    event.preventDefault();
    const channelUrl = event.target.channelURL.value;
    try {
        // Call backend API to trigger training
        const e2ApiUrlTrain = 'http://3.20.204.32:5000/train';
        const response = await fetch(e2ApiUrlTrain, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
        const ec2ApiUrlQuery = `http://3.20.204.32:5000/query?query_phrase=${encodeURIComponent(queryPhrase)}&channel_url=${encodeURIComponent(channelUrl)}`;
        const response = await fetch(ec2ApiUrlQuery)
        const results = await response.json()
        // Save the results to state
        setQueryResults(results || []);
    } catch (error) {
        setQueryResults([{ error: "Error occurred during query. Please try again." }]);
    }
  };
  return (
    <div className="App">
      {/* Training Form */}
      <form onSubmit={handleSubmit}>
        <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
        <button type="submit">Train Model</button>
      </form>
      {message && <div className="message">{message}</div>}

      {/* Query Form */}
      <form onSubmit={handleQuerySubmit}>
        <textarea name="queryPhrase" placeholder="Enter query phrase"></textarea>
        <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
        <button type="submit">Query Model</button>
      </form>

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
