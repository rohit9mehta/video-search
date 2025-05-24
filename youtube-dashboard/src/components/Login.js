import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [channelUrl, setChannelUrl] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    if (login(channelUrl, password)) {
      navigate('/admin');
    } else {
      setError('Invalid password. Please try again.');
    }
  };

  return (
    <div className="App" style={{ fontFamily: 'Arial, sans-serif', maxWidth: '500px', margin: '0 auto', padding: '20px', marginTop: '100px', background: '#f9fbfd', color: '#232946' }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: '40px', color: '#1976d2', fontWeight: 700, letterSpacing: '-0.5px', background: '#f6faff', borderRadius: 12, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)' }}>Admin Login</h1>
      <form onSubmit={handleSubmit} className="clipt-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', backgroundColor: '#f6faff', padding: '30px', borderRadius: '12px', boxShadow: '0 8px 32px 0 rgba(25, 118, 210, 0.10)' }}>
        <div className="section" style={{ width: '100%', maxWidth: '400px' }}>
          <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#232946' }}>Enter Credentials</h2>
          <textarea 
            name="channelURL" 
            placeholder="Enter channel URL"
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
            required
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif', background: '#f9fbfd', color: '#232946' }}
          ></textarea>
          <input
            type="password"
            name="password"
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '8px', border: '1px solid #e3eaf3', marginBottom: '15px', fontFamily: 'Arial, sans-serif', background: '#f9fbfd', color: '#232946' }}
          />
          <button 
            type="submit"
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, boxShadow: '0 2px 8px rgba(25, 118, 210, 0.07)', width: '100%' }}
          >
            Login
          </button>
        </div>
        {error && <div className="message" style={{ marginTop: '15px', textAlign: 'center', color: 'red', fontSize: '1em' }}>{error}</div>}
      </form>
    </div>
  );
}

export default Login; 