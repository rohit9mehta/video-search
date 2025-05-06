import './App.css';
import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import CustomerView from './components/CustomerView';
import AdminView from './components/AdminView';
import Login from './components/Login';
import LandingPage from './components/LandingPage';
import { AuthProvider, useAuth } from './context/AuthContext';

function AppContent() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/" element={<CustomerView />} />
      <Route path="/login" element={<Login />} />
      <Route 
        path="/admin" 
        element={
          isAuthenticated ? <AdminView /> : <Navigate to="/login" replace />
        } 
      />
      <Route path="/landing" element={<LandingPage />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;
