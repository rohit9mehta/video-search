import './App.css';

function App() {
  const handleSubmit = async (event) => {
      event.preventDefault();
      const channelUrl = event.target.channelURL.value;
      // Call backend API to trigger training
      await fetch('/api/train', {
          method: 'POST',
          body: JSON.stringify({ channelUrl }),
      });
  };

  const handleQuerySubmit = async (event) => {
    event.preventDefault();
    const queryPhrase = event.target.queryPhrase.value;
    const channelUrl = event.target.channelURL.value;
    // Call backend API to trigger query
    await fetch('/api/query', {
        method: 'GET',
        body: JSON.stringify({ queryPhrase, channelUrl }),
    });
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
