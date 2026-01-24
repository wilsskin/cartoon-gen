import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import filterIcon from '../assets/images/filter-icon.svg';
import arrowDownIcon from '../assets/images/arrow-down.svg';
import wsjLogo from '../assets/images/wsj-logo.png';

const LandingPage = ({ newsItems, selectedNews, setSelectedNews }) => {
  const [showAll, setShowAll] = useState(false);
  const navigate = useNavigate();
  const allowedCategories = new Set(['World', 'Politics', 'Business', 'Technology', 'Culture']);

  const visibleHeadlines = showAll ? newsItems : newsItems.slice(0, 5);

  // Debug: Log news items to console
  console.log('News items received:', newsItems.length, newsItems);

  const handleItemClick = (item) => {
    setSelectedNews(item);
    navigate('/generate');
  };

  return (
    <div className="landing-page">
      <div className="landing-container">
        {/* Content Wrapper - matches Frame 30 from Figma */}
        <div className="content-wrapper">
          {/* Hero Section */}
          <div className="hero-section">
            <h1 className="hero-title">CartoonGen</h1>
            <div className="hero-content">
              <div className="hero-subtitle-container">
                <div className="hero-subtitle">
                  Generate political cartoons from todays top headlines
                </div>
              </div>
              <div className="hero-image-placeholder">
                {/* Hero image placeholder */}
              </div>
            </div>
          </div>

          {/* Filter Section */}
          <div className="filter-section">
            <img src={filterIcon} alt="" className="filter-icon" width="16" height="16" />
            <span className="filter-text">Filter</span>
          </div>

          {/* News Items List */}
          <div className="news-list-section">
            {newsItems.length === 0 ? (
              <div className="news-loading">No headlines available. Make sure the backend is running.</div>
            ) : (
              visibleHeadlines.map((item, index) => (
                <div
                  key={item.id}
                  className={`news-item ${index === 0 ? 'news-item-first' : ''}`}
                >
                  <div className="news-item-content">
                    <h3
                      className="news-item-headline"
                      role="button"
                      tabIndex={0}
                      onClick={() => handleItemClick(item)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleItemClick(item);
                        }
                      }}
                    >
                      {item.headline}
                    </h3>
                    <div className="news-item-meta">
                      <img src={wsjLogo} alt="" className="news-item-logo" width="17.78" height="10" />
                      <span className="news-item-category">· {allowedCategories.has(item.category) ? item.category : 'Culture'}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* More Button */}
          {newsItems.length > 5 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="more-button"
            >
              More{' '}
              <img src={arrowDownIcon} alt="" className="more-arrow" width="16" height="16" />
            </button>
          )}

          {/* Recently Created Section */}
          <div className="recently-created-section">
            <div className="recently-created-title-wrapper">
              <h2 className="recently-created-title">Recently Created</h2>
            </div>
            <div className="recently-created-grid">
              {newsItems.slice(0, 4).map((item, index) => (
                <div
                  key={`recent-${item.id}`}
                  className="recent-card"
                >
                  <div className="recent-card-image"></div>
                  <p className="recent-card-text">{item.headline}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="landing-footer">
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
    </div>
  );
};

export default LandingPage;
