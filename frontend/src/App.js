import React, { useState, useEffect } from 'react';
import './App.css';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import { getApiUrl } from './config';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    // Check if token exists and is valid
    const token = localStorage.getItem('token');
    if (token) {
      // Validate token by making a test API call
      fetch(getApiUrl('/camera/list'), {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(response => {
          if (response.ok) {
            setIsLoggedIn(true);
          } else {
            // Token is invalid, remove it
            localStorage.removeItem('token');
            setIsLoggedIn(false);
          }
        })
        .catch(() => {
          // API not available or token invalid
          localStorage.removeItem('token');
          setIsLoggedIn(false);
        });
    }
  }, []);

  const handleLogin = () => {
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
  };

  return (
    <div className="App">
      {isLoggedIn ? (
        <Dashboard onLogout={handleLogout} />
      ) : (
        <Login onLogin={handleLogin} />
      )}
    </div>
  );
}

export default App;
