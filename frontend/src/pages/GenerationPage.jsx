import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CanvasMeme from '../components/CanvasMeme';
import arrowBack from '../assets/images/arrow-back.svg';
import actionIcons from '../assets/images/action-icons.svg';

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
      const backendDetail = err?.response?.data?.detail;
      if (typeof backendDetail === 'string' && backendDetail.trim().length > 0) {
        setError(backendDetail);
      } else {
        setError('Image generation failed. Please try again.');
      }
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
      {/* Main Content */}
      <div className="generation-main">
        {/* Back Button */}
        <div className="generation-back" onClick={() => navigate('/')}>
          <img src={arrowBack} alt="" className="back-arrow" width="16" height="16" />
          <span className="back-text">Back</span>
        </div>

        {/* Card Container */}
        <div className="generation-card-container">
          {/* Image Card */}
          <div className="generation-card">
            {error && <p className="error-message">{error}</p>}
            <CanvasMeme
              backgroundImageUrl={currentImageUrl}
              captionText={selectedNews.pregeneratedCaption}
              isLoading={isLoading}
            />
          </div>

          {/* Text Content */}
          <div className="generation-text-content">
            <h2 className="generation-headline">{selectedNews.headline}</h2>
            <p className="generation-subtext">This is subtext and more about the headline the person selected</p>
          </div>

          {/* Action Icons */}
          <div className="generation-actions">
            <img src={actionIcons} alt="Actions" className="action-icons" />
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="generation-footer">
        <div className="footer-text">
          <p className="footer-subtitle">
            Built by{' '}
            <span>
              <a href="#" style={{ textDecoration: 'underline', textUnderlineOffset: '2px', textDecorationThickness: '0.8px', color: 'inherit' }}>Wilson Skinner</a>
            </span>
            {' '}and{' '}
            <span>
              <a href="#" style={{ textDecoration: 'underline', textUnderlineOffset: '2px', textDecorationThickness: '0.8px', color: 'inherit' }}>Aryan Daga</a>
            </span>
          </p>
        </div>
        <div className="footer-links">
          <a href="#" className="footer-link">How it works</a>
        </div>
      </div>
    </div>
  );
};

export default GenerationPage;
