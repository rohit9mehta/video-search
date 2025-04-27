import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [channelUrl, setChannelUrl] = useState('');

  useEffect(() => {
    // Check if there's a saved channel URL in localStorage on mount
    const savedChannelUrl = localStorage.getItem('adminChannelUrl');
    if (savedChannelUrl) {
      setIsAuthenticated(true);
      setChannelUrl(savedChannelUrl);
    }
  }, []);

  const login = (url, password) => {
    // Hardcoded password check for now
    if (password === 'password') {
      localStorage.setItem('adminChannelUrl', url);
      setChannelUrl(url);
      setIsAuthenticated(true);
      return true;
    }
    return false;
  };

  const logout = () => {
    localStorage.removeItem('adminChannelUrl');
    setChannelUrl('');
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, channelUrl, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}; 