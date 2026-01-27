import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import Header from './components/Header';
import LandingPage from './pages/LandingPage';
import GenerationPage from './pages/GenerationPage';

// Use environment variable for API URL, fallback to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [newsItems, setNewsItems] = useState([]);
  const [selectedNews, setSelectedNews] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    // Fetch the initial list of news headlines on component mount
    axios.get(`${API_BASE_URL}/api/news`)
      .then(response => {
        console.log('News items fetched:', response.data);
        console.log('Number of items:', response.data?.length || 0);
        setNewsItems(response.data || []);
        setError(''); // Clear any previous errors
        if (!response.data || response.data.length === 0) {
          setError('No headlines found. Backend may not have data for today.');
        }
      })
      .catch(err => {
        console.error("Failed to fetch news:", err);
        console.error("Error details:", err.response?.data || err.message);
        const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
        setError(`Could not connect to backend: ${errorMsg}. Make sure backend is running on ${API_BASE_URL}`);
        setNewsItems([]); // Ensure it's empty on error
      });
  }, []);

  return (
    <Router>
      <div className="app">
        <Header />

        {error && <p className="global-error">{error}</p>}

        <Routes>
          <Route
            path="/"
            element={
              <LandingPage
                newsItems={newsItems}
                selectedNews={selectedNews}
                setSelectedNews={setSelectedNews}
              />
            }
          />
          <Route
            path="/generate"
            element={<GenerationPage selectedNews={selectedNews} />}
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
