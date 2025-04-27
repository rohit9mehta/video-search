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
    <div className="App" style={{ fontFamily: 'Arial, sans-serif', maxWidth: '500px', margin: '0 auto', padding: '20px', marginTop: '100px' }}>
      <h1 style={{ textAlign: 'center', fontSize: '2.5em', marginBottom: '40px', color: '#333' }}>Admin Login</h1>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', backgroundColor: '#f9f9f9', padding: '30px', borderRadius: '10px', boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)' }}>
        <div className="section" style={{ width: '100%', maxWidth: '400px' }}>
          <h2 style={{ textAlign: 'center', fontSize: '1.8em', marginBottom: '20px', color: '#555' }}>Enter Credentials</h2>
          <textarea 
            name="channelURL" 
            placeholder="Enter channel URL"
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
            required
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '5px', border: '1px solid #ddd', marginBottom: '15px', minHeight: '50px', resize: 'vertical', fontFamily: 'Arial, sans-serif' }}
          ></textarea>
          <input
            type="password"
            name="password"
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ width: '100%', padding: '10px', fontSize: '1em', borderRadius: '5px', border: '1px solid #ddd', marginBottom: '15px', fontFamily: 'Arial, sans-serif' }}
          />
          <button 
            type="submit"
            style={{ padding: '12px 30px', fontSize: '1.1em', backgroundColor: '#008CBA', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', transition: 'background-color 0.3s', width: '100%' }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#007399'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#008CBA'}
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