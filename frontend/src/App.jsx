import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import Header from './components/Header';
import LandingPage from './pages/LandingPage';
import GenerationPage from './pages/GenerationPage';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [newsItems, setNewsItems] = useState([]);
  const [selectedNews, setSelectedNews] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    // Fetch the initial list of news headlines on component mount
    axios.get(`${API_BASE_URL}/api/news`)
      .then(response => {
        setNewsItems(response.data);
      })
      .catch(err => {
        console.error("Failed to fetch news:", err);
        setError('Could not connect to the backend. Is it running?');
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
