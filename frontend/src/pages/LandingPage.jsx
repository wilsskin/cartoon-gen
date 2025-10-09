import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LandingPage = ({ newsItems, selectedNews, setSelectedNews }) => {
  const [showAll, setShowAll] = useState(false);
  const navigate = useNavigate();

  const visibleHeadlines = showAll ? newsItems : newsItems.slice(0, 5);

  const scrollToHeadlines = () => {
    const headlinesSection = document.getElementById('headlines-section');
    if (headlinesSection) {
      headlinesSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleGenerateClick = () => {
    if (selectedNews) {
      navigate('/generate');
    }
  };

  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero-section">
        <h1 className="hero-title">Generate Political Cartoons From Recent Headlines</h1>
        <button onClick={scrollToHeadlines} className="hero-btn">
          Generate Now
        </button>
      </section>

      {/* Headlines Selection Section */}
      <section id="headlines-section" className="headlines-section">
        <h2 className="section-title">Select a Recent Headline</h2>
        <p className="section-subtitle">Choose from today's top news stories to create your meme</p>

        <div className="headlines-container">
          <div className="headlines-list">
            {visibleHeadlines.map((item) => (
              <div
                key={item.id}
                className={`headline-item ${selectedNews?.id === item.id ? 'selected' : ''}`}
                onClick={() => setSelectedNews(item)}
              >
                <div className="headline-content">
                  <p className="headline-text">{item.headline}</p>
                  <a
                    href={item.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="source-link"
                    onClick={(e) => e.stopPropagation()}
                    title="View Source"
                  >
                    →
                  </a>
                </div>
              </div>
            ))}

            {newsItems.length > 5 && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="show-more-btn"
              >
                {showAll ? 'Show Less' : 'Show More'}
              </button>
            )}
          </div>

          <div className="generate-image-container">
            <button
              onClick={handleGenerateClick}
              disabled={!selectedNews}
              className={`generate-image-btn ${selectedNews ? 'active' : ''}`}
            >
              Generate Image
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
