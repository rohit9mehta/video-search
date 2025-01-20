import './App.css';

function App() {
  const handleSubmit = async (event) => {
      event.preventDefault();
      const channelUrl = event.target.channelURL.value;
      // Call backend API to trigger training
      const e2ApiUrlTrain = 'http://3.20.204.32:5000/train';
      await fetch(e2ApiUrlTrain, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ channel_url: channelUrl }),
      });
  };

  const handleQuerySubmit = async (event) => {
    event.preventDefault();
    const queryPhrase = event.target.queryPhrase.value;
    const channelUrl = event.target.channelURL.value;
    // Call backend API to trigger query
    const ec2ApiUrlQuery = `http://3.20.204.32:5000/query?query_phrase=${encodeURIComponent(queryPhrase)}&channel_url=${encodeURIComponent(channelUrl)}`;
    const response = await fetch(ec2ApiUrlQuery)
    const results = await response.json()
    console.log('Query Results: ', results);
  };
  return (
    <>
        <form onSubmit={handleSubmit}>
          <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
          <button type="submit">Train Model</button>
        </form>
        <form onSubmit={handleQuerySubmit}>
          <textarea name="queryPhrase" placeholder="Enter query phrase"></textarea>
          <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
          <button type="submit">Query Model</button>
        </form>  
    </>
  );
}

export default App;
