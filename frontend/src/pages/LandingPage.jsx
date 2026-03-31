import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import filterIcon from '../assets/images/filter-icon.svg';
import arrowDownIcon from '../assets/images/arrow-down.svg';
import foxLogo from '../assets/images/fox-us.svg';
import nbcLogo from '../assets/images/nbc.svg';
import nytLogo from '../assets/images/nyt.svg';
import nprLogo from '../assets/images/npr.svg';
import wsjLogo from '../assets/images/wsj.svg';
import heroCartoon1 from '../assets/images/hero-cartoon-1.webp';
import heroCartoon2 from '../assets/images/hero-cartoon-2.webp';
import heroCartoon3 from '../assets/images/hero-cartoon-3.webp';
import iconX from '../assets/images/icon-x.svg';
import iconArrowLeft from '../assets/images/icon-arrow-left.svg';
import iconArrowRight from '../assets/images/icon-arrow-right.svg';

const HERO_IMAGES = [heroCartoon1, heroCartoon2, heroCartoon3];

const FEED_LOGOS = {
  fox_us: foxLogo,
  nbc_top: nbcLogo,
  nyt_home: nytLogo,
  npr_news: nprLogo,
  wsj_us: wsjLogo,
};

// Feed ID -> short display label (matches backend FEED_DISPLAY_TAGS)
const FEED_LABELS = {
  fox_us: 'FOX',
  nbc_top: 'NBC',
  nyt_home: 'NYT',
  npr_news: 'NPR',
  wsj_us: 'WSJ',
};

// Filter dropdown options (alphabetical)
const FEED_OPTIONS = [
  { id: 'fox_us', label: 'Fox News' },
  { id: 'nbc_top', label: 'NBC News' },
  { id: 'nyt_home', label: 'New York Times' },
  { id: 'npr_news', label: 'NPR' },
  { id: 'wsj_us', label: 'Wall Street Journal' },
];

const ITEMS_PER_PAGE = 5;

const LandingPage = ({ newsItems, isLoading }) => {
  const [visibleCount, setVisibleCount] = useState(ITEMS_PER_PAGE);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [selectedFeed, setSelectedFeed] = useState(null);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [galleryIndex, setGalleryIndex] = useState(0);
  const [articleTooltipId, setArticleTooltipId] = useState(null);
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);
  const articleTooltipTimeoutRef = useRef(null);
  const navigate = useNavigate();

  const TOOLTIP_DELAY_MS = 300;

  const showArticleTooltip = (itemId) => {
    if (articleTooltipTimeoutRef.current) clearTimeout(articleTooltipTimeoutRef.current);
    articleTooltipTimeoutRef.current = setTimeout(() => setArticleTooltipId(itemId), TOOLTIP_DELAY_MS);
  };

  const hideArticleTooltip = () => {
    if (articleTooltipTimeoutRef.current) {
      clearTimeout(articleTooltipTimeoutRef.current);
      articleTooltipTimeoutRef.current = null;
    }
    setArticleTooltipId(null);
  };

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
    setSelectedFeed(null); // Reset filter when navigating to generate
    navigate(`/generate/${item.id}`);
  };

  const openGallery = useCallback((index) => {
    setGalleryIndex(index);
    setGalleryOpen(true);
  }, []);

  const closeGallery = useCallback(() => setGalleryOpen(false), []);

  const galleryPrev = useCallback(() => {
    setGalleryIndex((i) => (i - 1 + HERO_IMAGES.length) % HERO_IMAGES.length);
  }, []);

  const galleryNext = useCallback(() => {
    setGalleryIndex((i) => (i + 1) % HERO_IMAGES.length);
  }, []);

  useEffect(() => {
    if (!galleryOpen) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') closeGallery();
      if (e.key === 'ArrowLeft') galleryPrev();
      if (e.key === 'ArrowRight') galleryNext();
    };
    document.addEventListener('keydown', handleKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = '';
    };
  }, [galleryOpen, closeGallery, galleryPrev, galleryNext]);

  useEffect(() => () => {
    if (articleTooltipTimeoutRef.current) clearTimeout(articleTooltipTimeoutRef.current);
  }, []);

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
                  Generate political cartoons from today's top headlines
                </div>
              </div>
              <div className="hero-images-container">
                <div className="hero-images-overlay" aria-hidden="true">
                  <div
                    className="hero-image-card hero-image-card-1"
                    role="button"
                    tabIndex={0}
                    onClick={() => openGallery(0)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openGallery(0); } }}
                    aria-label="View example cartoon 1"
                  >
                    <img src={heroCartoon1} alt="" />
                  </div>
                  <div
                    className="hero-image-card hero-image-card-2"
                    role="button"
                    tabIndex={0}
                    onClick={() => openGallery(1)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openGallery(1); } }}
                    aria-label="View example cartoon 2"
                  >
                    <img src={heroCartoon2} alt="" />
                  </div>
                  <div
                    className="hero-image-card hero-image-card-3"
                    role="button"
                    tabIndex={0}
                    onClick={() => openGallery(2)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openGallery(2); } }}
                    aria-label="View example cartoon 3"
                  >
                    <img src={heroCartoon3} alt="" />
                  </div>
                </div>
              </div>

              {galleryOpen && (
                <div
                  className="hero-gallery-backdrop"
                  role="dialog"
                  aria-modal="true"
                  aria-label="Example cartoon gallery"
                  onClick={(e) => e.target === e.currentTarget && closeGallery()}
                >
                  <div className="hero-gallery-content" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="hero-gallery-close"
                      onClick={closeGallery}
                      aria-label="Close gallery"
                    >
                      <img src={iconX} alt="" width="24" height="24" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="hero-gallery-prev"
                      onClick={galleryPrev}
                      aria-label="Previous image"
                    >
                      <img src={iconArrowLeft} alt="" width="16" height="16" aria-hidden="true" />
                    </button>
                    <img src={HERO_IMAGES[galleryIndex]} alt="" />
                    <button
                      type="button"
                      className="hero-gallery-next"
                      onClick={galleryNext}
                      aria-label="Next image"
                    >
                      <img src={iconArrowRight} alt="" width="16" height="16" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              )}
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
              <img src={filterIcon} alt="" className="filter-icon" width="18" height="18" />
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
                    <span className={`logo-frame logo-frame--filter logo-feed--${option.id}`}>
                      <img
                        src={FEED_LOGOS[option.id]}
                        alt=""
                        className="filter-option-logo"
                      />
                    </span>
                    <span className="filter-option-label">{option.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* News Items List */}
          <div className="news-list-section" key={selectedFeed || 'all'}>
            {isLoading ? (
              <div className="news-loading news-loading--dots">Loading headlines<span className="loading-dot loading-dot-1">.</span><span className="loading-dot loading-dot-2">.</span><span className="loading-dot loading-dot-3">.</span></div>
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
                      aria-label="View article"
                      onMouseEnter={() => showArticleTooltip(item.id)}
                      onMouseLeave={hideArticleTooltip}
                    >
                      <span className={`logo-frame logo-frame--news logo-feed--${item.feedId}`}>
                        <img src={FEED_LOGOS[item.feedId]} alt="" className="news-item-logo" />
                      </span>
                      <span className="news-item-category">{FEED_LABELS[item.feedId] || item.category}</span>
                      <span className="generation-action-tooltip" data-visible={articleTooltipId === item.id}>View article</span>
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
                  <img src={arrowDownIcon} alt="" className="more-arrow" width="11" height="13" />
                </button>
              )}
              {canShowLess && (
                <button onClick={handleShowLess} className="less-button">
                  Less
                  <img src={arrowDownIcon} alt="" className="more-arrow" width="11" height="13" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="landing-footer">
          <div className="footer-left">
            <span className="footer-text">Built by <a href="https://wilsonskinner.com/" target="_blank" rel="noopener noreferrer" className="footer-link">Wilson Skinner</a></span>
          </div>
          <div className="footer-right">
            <Link to="/how-it-works" className="footer-text">How it works</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
