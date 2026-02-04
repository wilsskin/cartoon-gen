import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import filterIcon from '../assets/images/filter-icon.svg';
import arrowDownIcon from '../assets/images/arrow-down.svg';
import cnnLogo from '../assets/images/cnn.svg';
import foxLogo from '../assets/images/fox-us.svg';
import nbcLogo from '../assets/images/nbc.svg';
import nytLogo from '../assets/images/nyt.svg';
import nprLogo from '../assets/images/npr.svg';
import wsjLogo from '../assets/images/wsj-logo.png';

const FEED_LOGOS = {
  cnn_top: cnnLogo,
  fox_us: foxLogo,
  nbc_top: nbcLogo,
  nyt_home: nytLogo,
  npr_news: nprLogo,
  wsj_world: wsjLogo,
};

// Filter dropdown options (alphabetical)
const FEED_OPTIONS = [
  { id: 'cnn_top', label: 'CNN' },
  { id: 'fox_us', label: 'Fox News' },
  { id: 'nbc_top', label: 'NBC News' },
  { id: 'nyt_home', label: 'New York Times' },
  { id: 'npr_news', label: 'NPR' },
];

const ITEMS_PER_PAGE = 5;

const LandingPage = ({ newsItems, selectedNews, setSelectedNews, isLoading }) => {
  const [visibleCount, setVisibleCount] = useState(ITEMS_PER_PAGE);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [selectedFeed, setSelectedFeed] = useState(null);
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);
  const navigate = useNavigate();

  // Close dropdown when clicking outside (anywhere except the dropdown itself)
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!isFilterOpen) return;
      
      // If clicking the button, let the button's onClick handle it
      if (buttonRef.current && buttonRef.current.contains(event.target)) {
        return;
      }
      
      // If clicking outside the dropdown, close it
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsFilterOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isFilterOpen]);

  // Sort headlines: selected feed first, then others grouped by feed
  const sortedHeadlines = selectedFeed
    ? [
        // First: all items from selected feed
        ...newsItems.filter(item => item.feedId === selectedFeed),
        // Then: items from other feeds, grouped by feedId
        ...FEED_OPTIONS
          .filter(opt => opt.id !== selectedFeed)
          .flatMap(opt => newsItems.filter(item => item.feedId === opt.id))
      ]
    : newsItems;

  const visibleHeadlines = sortedHeadlines.slice(0, visibleCount);
  const canShowMore = visibleCount < sortedHeadlines.length;
  const canShowLess = visibleCount > ITEMS_PER_PAGE;

  const handleShowMore = () => {
    setVisibleCount(prev => Math.min(prev + ITEMS_PER_PAGE, sortedHeadlines.length));
  };

  const handleShowLess = () => {
    setVisibleCount(prev => Math.max(prev - ITEMS_PER_PAGE, ITEMS_PER_PAGE));
  };

  const handleFilterSelect = (feedId) => {
    setSelectedFeed(feedId);
    setIsFilterOpen(false);
  };

  const handleItemClick = (item) => {
    setSelectedNews(item);
    setSelectedFeed(null); // Reset filter when navigating to generate
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
          <div className="filter-wrapper">
            <button
              ref={buttonRef}
              className="filter-section"
              onClick={() => setIsFilterOpen(!isFilterOpen)}
              aria-expanded={isFilterOpen}
              aria-haspopup="listbox"
            >
              <img src={filterIcon} alt="" className="filter-icon" width="16" height="16" />
              <span className="filter-text">Filter</span>
            </button>

            {/* Filter Dropdown */}
            {isFilterOpen && (
              <div className="filter-dropdown" role="listbox" ref={dropdownRef}>
                {FEED_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    className="filter-option"
                    onClick={() => handleFilterSelect(option.id)}
                    role="option"
                    aria-selected={selectedFeed === option.id}
                  >
                    <img
                      src={FEED_LOGOS[option.id]}
                      alt=""
                      className="filter-option-logo"
                    />
                    <span className="filter-option-label">{option.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* News Items List */}
          <div className="news-list-section" key={selectedFeed || 'all'}>
            {isLoading ? (
              <div className="news-loading">Headlines loading...</div>
            ) : newsItems.length === 0 ? (
              <div className="news-loading">No headlines available</div>
            ) : (
              visibleHeadlines.map((item, index) => (
                <div
                  key={`${selectedFeed}-${item.id}`}
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
                    <a
                      href={item.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="news-item-meta"
                    >
                      <img src={FEED_LOGOS[item.feedId] || wsjLogo} alt="" className="news-item-logo" />
                      <span className="news-item-category">{item.category}</span>
                    </a>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* More/Less Buttons */}
          {(canShowMore || canShowLess) && (
            <div className="more-less-buttons">
              {canShowMore && (
                <button onClick={handleShowMore} className="more-button">
                  More
                  <img src={arrowDownIcon} alt="" className="more-arrow" width="10" height="11" />
                </button>
              )}
              {canShowLess && (
                <button onClick={handleShowLess} className="less-button">
                  Less
                  <img src={arrowDownIcon} alt="" className="more-arrow" width="10" height="11" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="landing-footer">
          <div className="footer-left">
            <span className="footer-text">©2026 CartoonGen</span>
            <span className="footer-text">Built by Wilson Skinner & Aryn Dagnas</span>
          </div>
          <div className="footer-right">
            <a href="#" className="footer-text">How it works</a>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="footer-text">Github repo</a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
