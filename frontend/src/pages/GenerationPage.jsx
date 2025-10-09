import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CanvasMeme from '../components/CanvasMeme';

const API_BASE_URL = 'http://localhost:8000';

const GenerationPage = ({ selectedNews }) => {
  const navigate = useNavigate();
  const [currentImageUrl, setCurrentImageUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Redirect to home if no news is selected
    if (!selectedNews) {
      navigate('/');
      return;
    }

    // Set the initial image
    setCurrentImageUrl(`${API_BASE_URL}${selectedNews.initialImageUrl}`);
  }, [selectedNews, navigate]);

  const handleGenerateImage = (style) => {
    if (!selectedNews) return;

    setIsLoading(true);
    setError('');

    axios.post(`${API_BASE_URL}/api/generate-image`, {
      basePrompt: selectedNews.basePrompt,
      style: style,
    })
    .then(response => {
      setCurrentImageUrl(response.data.imageUrl);
    })
    .catch(err => {
      console.error("Image generation failed:", err);
      setError('Image generation failed. Please try again.');
    })
    .finally(() => {
      setIsLoading(false);
    });
  };

  if (!selectedNews) {
    return null;
  }

  return (
    <div className="generation-page">
      <button onClick={() => navigate('/')} className="back-btn">
        ← Back
      </button>

      <div className="generation-content">
        <div className="image-container">
          {error && <p className="error-message">{error}</p>}

          <CanvasMeme
            backgroundImageUrl={currentImageUrl}
            captionText={selectedNews.pregeneratedCaption}
            isLoading={isLoading}
          />
        </div>

        <div className="generation-controls">
          <button
            onClick={() => handleGenerateImage('Funnier')}
            disabled={isLoading}
            className="generation-btn funnier-btn"
          >
            {isLoading ? 'Generating...' : 'Funnier'}
          </button>
          <button
            onClick={() => handleGenerateImage('More Absurd')}
            disabled={isLoading}
            className="generation-btn absurd-btn"
          >
            {isLoading ? 'Generating...' : 'Absurd'}
          </button>
        </div>

        {isLoading && (
          <p className="loading-message">
            Generating new image... this may take a moment.
          </p>
        )}
      </div>
    </div>
  );
};

export default GenerationPage;
