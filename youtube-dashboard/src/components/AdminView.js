import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function AdminView() {
  const navigate = useNavigate();
  const { channelUrl, logout } = useAuth();
  const [message, setMessage] = React.useState('');
  const [videoTrainMessage, setVideoTrainMessage] = React.useState('');
  const [customerKey, setCustomerKey] = React.useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      const e2ApiUrlTrain = 'https://aivideo.planeteria.com/api/train';
      const response = await fetch(e2ApiUrlTrain, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ channel_url: channelUrl, customer_key: customerKey }),
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
        body: JSON.stringify({ channel_url: channelUrl, video_url: videoUrl, customer_key: customerKey }),
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
    <div className="App" style={{ fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: '0 auto', padding: '20px', background: '#f9fbfd', color: '#232946' }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: '40px', color: '#1976d2', fontWeight: 700, letterSpacing: '-0.5px', background: '#f6faff', borderRadius: 12, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}>Admin View</h1>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '40px' }}>
        <button onClick={() => navigate('/')} style={{ padding: '10px 20px', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}
        >
          Go to Customer View
        </button>
        <button onClick={handleLogout} style={{ padding: '10px 20px', backgroundColor: '#f44336', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(244, 67, 54, 0.07)' }}
        >
          Logout
        </button>
      </div>
      <div className="section clipt-card" style={{ marginBottom: '40px' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#232946' }}>Train on Channel URL</h2>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <textarea 
            name="channelURL" 
            value={channelUrl} 
            readOnly
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#f6faff', color: '#232946' }}
          ></textarea>
          <textarea
            name="customerKey"
            value={customerKey}
            onChange={e => setCustomerKey(e.target.value)}
            placeholder="Enter customer key"
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '30px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#f9fbfd', color: '#232946' }}
          />
          <button 
            type="submit"
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}
          >
            Train Model
          </button>
        </form>
        {message && <div className="message" style={{ marginTop: '15px', textAlign: 'center', color: message.includes('Error') ? 'red' : '#232946', fontSize: '1em' }}>{message}</div>}
      </div>
      <div className="section clipt-card" style={{ marginBottom: '40px' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#232946' }}>Add Video to Trained Model</h2>
        <form onSubmit={handleVideoSubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <textarea 
            name="channelURL" 
            value={channelUrl} 
            readOnly
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#f6faff', color: '#232946' }}
          ></textarea>
          <textarea
            name="customerKey"
            value={customerKey}
            onChange={e => setCustomerKey(e.target.value)}
            placeholder="Enter customer key"
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '30px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#f9fbfd', color: '#232946' }}
          />
          <textarea 
            name="videoURL" 
            placeholder="Enter video URL"
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', backgroundColor: '#f9fbfd', color: '#232946' }}
          ></textarea>
          <button 
            type="submit"
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}
          >
            Train on Video
          </button>
        </form>
        {videoTrainMessage && <div className="message" style={{ marginTop: '15px', textAlign: 'center', color: videoTrainMessage.includes('Error') ? 'red' : '#232946', fontSize: '1em' }}>{videoTrainMessage}</div>}
      </div>
    </div>
  );
}

export default AdminView; 