import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function AdminView() {
  const navigate = useNavigate();
  const { channelUrl, logout } = useAuth();
  const [message, setMessage] = React.useState('');
  const [videoTrainMessage, setVideoTrainMessage] = React.useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      const e2ApiUrlTrain = 'https://aivideo.planeteria.com/api/train';
      const response = await fetch(e2ApiUrlTrain, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ channel_url: channelUrl }),
      });
      const data = await response.json();
      setMessage(data.message || 'Training completed!');
    } catch (error) {
      setMessage('Error occurred during training. Please try again.');
    }
  };

  const handleVideoSubmit = async (event) => {
    event.preventDefault();
    const videoUrl = event.target.videoURL.value;
    try {
      const e2ApiUrlTrainVideo = 'https://aivideo.planeteria.com/api/train_video';
      const response = await fetch(e2ApiUrlTrainVideo, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ channel_url: channelUrl, video_url: videoUrl }),
      });
      const data = await response.json();
      setVideoTrainMessage(data.message || 'Video training started!');
    } catch (error) {
      setVideoTrainMessage('Error occurred during video training. Please try again.');
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="App" style={{ fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: '40px', color: '#333' }}>Admin View</h1>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '40px' }}>
        <button onClick={() => navigate('/')} style={{ padding: '10px 20px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', transition: 'background-color 0.3s' }}
          onMouseOver={(e) => e.target.style.backgroundColor = '#3e8e41'}
          onMouseOut={(e) => e.target.style.backgroundColor = '#4CAF50'}
        >
          Go to Customer View
        </button>
        <button onClick={handleLogout} style={{ padding: '10px 20px', backgroundColor: '#f44336', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', transition: 'background-color 0.3s' }}
          onMouseOver={(e) => e.target.style.backgroundColor = '#d32f2f'}
          onMouseOut={(e) => e.target.style.backgroundColor = '#f44336'}
        >
          Logout
        </button>
      </div>
      <div className="section" style={{ marginBottom: '40px', backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '10px', boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#555' }}>Train on Channel URL</h2>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <textarea 
            name="channelURL" 
            value={channelUrl} 
            readOnly
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '5px', border: '1px solid #ddd', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#eee' }}
          ></textarea>
          <button 
            type="submit"
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#008CBA', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', transition: 'background-color 0.3s' }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#007399'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#008CBA'}
          >
            Train Model
          </button>
        </form>
        {message && <div className="message" style={{ marginTop: '15px', textAlign: 'center', color: message.includes('Error') ? 'red' : '#333', fontSize: '1em' }}>{message}</div>}
      </div>
      <div className="section" style={{ marginBottom: '40px', backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '10px', boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#555' }}>Add Video to Trained Model</h2>
        <form onSubmit={handleVideoSubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <textarea 
            name="channelURL" 
            value={channelUrl} 
            readOnly
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '5px', border: '1px solid #ddd', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#eee' }}
          ></textarea>
          <textarea 
            name="videoURL" 
            placeholder="Enter video URL"
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '5px', border: '1px solid #ddd', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif' }}
          ></textarea>
          <button 
            type="submit"
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#008CBA', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', transition: 'background-color 0.3s' }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#007399'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#008CBA'}
          >
            Train on Video
          </button>
        </form>
        {videoTrainMessage && <div className="message" style={{ marginTop: '15px', textAlign: 'center', color: videoTrainMessage.includes('Error') ? 'red' : '#333', fontSize: '1em' }}>{videoTrainMessage}</div>}
      </div>
    </div>
  );
}

export default AdminView; 