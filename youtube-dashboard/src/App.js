import logo from './logo.svg';
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

  return (
      <form onSubmit={handleSubmit}>
          <textarea name="channelURL" placeholder="Enter channel URL"></textarea>
          <button type="submit">Train Model</button>
      </form>
  );
}

export default App;
