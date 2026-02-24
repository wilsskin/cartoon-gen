import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import CanvasMeme from '../components/CanvasMeme';
import arrowBack from '../assets/images/arrow-back.svg';

// News source logos
import foxLogo from '../assets/images/fox-us.svg';
import nbcLogo from '../assets/images/nbc.svg';
import nytLogo from '../assets/images/nyt.svg';
import nprLogo from '../assets/images/npr.svg';
import wsjLogo from '../assets/images/wsj.png';

const FEED_LOGOS = {
  fox_us: foxLogo,
  nbc_top: nbcLogo,
  nyt_home: nytLogo,
  npr_news: nprLogo,
  wsj_us: wsjLogo,
};

// API base URL: relative in production, localhost in dev
// In production (Vercel), frontend calls relative /api/* routes on the same domain
// In local dev, frontend uses http://localhost:8000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000');

const TOOLTIP_DELAY_MS = 300;

const GenerationPage = ({ newsItems, isLoading }) => {
  const navigate = useNavigate();
  const { headlineId } = useParams();
  const items = Array.isArray(newsItems) ? newsItems : [];
  const selectedNews = useMemo(
    () => (headlineId ? items.find((item) => item.id === headlineId) ?? null : null),
    [items, headlineId]
  );
  const [currentImageUrl, setCurrentImageUrl] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');
  const [errorDetails, setErrorDetails] = useState(null); // { code, message, status, model, requestId, details }
  const [showErrorDetails, setShowErrorDetails] = useState(false);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [tooltip, setTooltip] = useState(null); // 'download' | 'copy' | 'regenerate'
  const [copyConfirmed, setCopyConfirmed] = useState(false);
  const tooltipTimeoutRef = useRef(null);
  const lastHeadlineIdRef = useRef(null);

  const clearTooltipTimeout = () => {
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current);
      tooltipTimeoutRef.current = null;
    }
  };

  const showTooltipAfterDelay = (action) => {
    clearTooltipTimeout();
    tooltipTimeoutRef.current = setTimeout(() => setTooltip(action), TOOLTIP_DELAY_MS);
  };

  const hideTooltip = () => {
    clearTooltipTimeout();
    setTooltip(null);
  };

  const handleCopyImage = () => {
    if (!currentImageUrl || isGenerating || error) return;
    if (copyConfirmed) {
      setTooltip(null);
      setCopyConfirmed(false);
    }
    fetch(currentImageUrl)
      .then((res) => res.blob())
      .then((blob) => navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]))
      .then(() => {
        setCopyConfirmed(true);
        setTooltip('copy');
      })
      .catch(() => {});
  };

  const hideTooltipAndCopyState = () => {
    hideTooltip();
    setCopyConfirmed(false);
  };

  useEffect(() => {
    // No headline id in URL → go home
    if (!headlineId) {
      navigate('/');
      return;
    }
    // Still loading headlines → wait (don't redirect)
    if (isLoading) return;
    // Headline not in today's list (e.g. stale or shared link) → render shows "Headline no longer available"
    if (!selectedNews) return;

    // Always show top of page when entering generation view (fixes scroll-from-landing)
    window.scrollTo(0, 0);

    // Set the initial image (empty for RSS items)
    setCurrentImageUrl(selectedNews.initialImageUrl ? `${API_BASE_URL}${selectedNews.initialImageUrl}` : '');

    // Auto-generate cartoon when user lands or headline id in URL changes
    if (lastHeadlineIdRef.current !== selectedNews.id) {
      lastHeadlineIdRef.current = selectedNews.id;
      handleGenerateImage();
    }
  }, [headlineId, isLoading, selectedNews, navigate]);

  useEffect(() => () => clearTooltipTimeout(), []);

  const handleGenerateImage = () => {
    if (!selectedNews) return;

    setCurrentImageUrl(''); // Clear old image so only loading shows until new image arrives
    setIsGenerating(true);
    setError('');
    setErrorDetails(null);
    setShowErrorDetails(false);
    setIsRateLimited(false);

    axios.post(`${API_BASE_URL}/api/generate-image`, {
      headlineId: selectedNews.id,
    })
    .then(response => {
      const data = response?.data;
      if (data?.ok && data?.imageBase64) {
        const mime = data.mimeType || 'image/png';
        setCurrentImageUrl(`data:${mime};base64,${data.imageBase64}`);
        return;
      }
      if (data?.ok === false && data?.error) {
        const err = data.error;
        setError(err.message || 'Image generation failed.');
        setErrorDetails({
          code: err.code,
          message: err.message,
          status: err.status,
          model: err.model,
          requestId: err.requestId,
          details: err.details,
        });
        return;
      }
      setError('Image generation failed. Please try again.');
    })
    .catch(err => {
      console.error("Image generation failed:", err);
      const status = err?.response?.status;
      const data = err?.response?.data;

      if (status === 429) {
        setIsRateLimited(true);
        setError(data?.error?.message || data?.detail || "You've generated too many cartoons. Please wait a few minutes and try again.");
        if (data?.error) setErrorDetails({ ...data.error, requestId: data.error.requestId });
        return;
      }
      if (data?.ok === false && data?.error) {
        const e = data.error;
        setError(e.message || 'Image generation failed.');
        setErrorDetails({
          code: e.code,
          message: e.message,
          status: e.status,
          model: e.model,
          requestId: e.requestId,
          details: e.details,
        });
        return;
      }
      setError(data?.detail || data?.error?.message || 'Image generation failed. Please try again.');
      if (data?.error) {
        setErrorDetails({
          code: data.error.code,
          message: data.error.message,
          status: data.error.status,
          model: data.error.model,
          requestId: data.error.requestId,
          details: data.error.details,
        });
      }
    })
    .finally(() => {
      setIsGenerating(false);
    });
  };

  // No id in URL
  if (!headlineId) return null;
  // Still loading headlines
  if (isLoading) {
    return (
      <div className="generation-page">
        <div className="generation-main">
          <div className="generation-back" onClick={() => navigate('/')}>
            <img src={arrowBack} alt="" className="back-arrow" width="16" height="16" />
            <span className="back-text">Back</span>
          </div>
          <div className="generation-card-container">
            <p className="news-loading">Loading headlines...</p>
          </div>
        </div>
      </div>
    );
  }
  // Headline not in today's list
  if (!selectedNews) {
    return (
      <div className="generation-page">
        <div className="generation-main">
          <div className="generation-back" onClick={() => navigate('/')}>
            <img src={arrowBack} alt="" className="back-arrow" width="16" height="16" />
            <span className="back-text">Back</span>
          </div>
          <div className="generation-card-container">
            <p className="generation-unavailable">
              Headline no longer available. <button type="button" className="generation-unavailable-link" onClick={() => navigate('/')}>Back to headlines</button>
            </p>
          </div>
        </div>
      </div>
    );
  }

  const d = new Date();
  const downloadFilename = `cartoongen_${d.toLocaleString('en-US', { month: 'short' }).toLowerCase()}${d.getDate()}.png`;

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
            {error ? (
              <div className={`generation-error ${isRateLimited ? 'generation-error-rate-limit' : ''}`}>
                {isRateLimited ? (
                  <>
                    <span className="generation-error-title">Slow down!</span>
                    <span className="generation-error-text">{error}</span>
                  </>
                ) : (
                  <>
                    <span className="generation-error-text">{error}</span>
                    {errorDetails && (
                      <div className="generation-error-details">
                        <button
                          type="button"
                          className="generation-error-details-toggle"
                          onClick={() => setShowErrorDetails((v) => !v)}
                          aria-expanded={showErrorDetails}
                        >
                          {showErrorDetails ? 'Hide' : 'Show'} details
                        </button>
                        {showErrorDetails && (
                          <pre className="generation-error-details-content">
                            {[
                              errorDetails.status != null && `Status: ${errorDetails.status}`,
                              errorDetails.code != null && errorDetails.code !== undefined && `Code: ${String(errorDetails.code)}`,
                              errorDetails.model != null && errorDetails.model !== undefined && `Model: ${String(errorDetails.model)}`,
                              errorDetails.requestId != null && errorDetails.requestId !== undefined && `Request ID: ${String(errorDetails.requestId)}`,
                              errorDetails.details != null && `Details: ${JSON.stringify(errorDetails.details, null, 2)}`,
                            ].filter(Boolean).join('\n')}
                          </pre>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <CanvasMeme
                backgroundImageUrl={currentImageUrl}
                captionText={selectedNews.pregeneratedCaption}
                isLoading={isGenerating}
              />
            )}
          </div>

          {/* Source Logo - links to article */}
          <div className="generation-source">
            <a
              href={selectedNews.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="generation-source-link"
            >
              <img
                src={FEED_LOGOS[selectedNews.feedId]}
                alt={selectedNews.category || 'News source'}
                className="generation-source-logo"
              />
            </a>
          </div>

          {/* Text Content */}
          <div className="generation-text-content">
            <h2 className="generation-headline">{selectedNews.headline}</h2>
            {selectedNews.summary && (
              <p className="generation-subtext">{selectedNews.summary}</p>
            )}
          </div>

          {/* Action Icons: one SVG inside each button so hitbox and icon always align (40×40, 16px gap) */}
          <div className={`generation-actions ${isGenerating ? 'generation-actions-loading' : ''}`}>
            {currentImageUrl && !isGenerating && !error ? (
              <>
                <a
                  href={currentImageUrl}
                  download={downloadFilename}
                  className="generation-action generation-action-download"
                  aria-label="Download cartoon as PNG"
                  onMouseEnter={() => showTooltipAfterDelay('download')}
                  onMouseLeave={hideTooltip}
                >
                  <svg className="action-icon-svg" viewBox="0 0 32 32" width="40" height="40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect className="action-icon-border" x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#595959" strokeOpacity="0.15"/>
                    <g clipPath="url(#clip-dl)">
                      <path d="M16 17.125V9.25" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M22.1875 17.125V21.625H9.8125V17.125" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M18.8125 14.3125L16 17.125L13.1875 14.3125" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </g>
                    <defs><clipPath id="clip-dl"><rect x="7" y="7" width="18" height="18" rx="2.5" fill="white"/></clipPath></defs>
                  </svg>
                  <span className="generation-action-tooltip" data-visible={tooltip === 'download'}>Download</span>
                </a>
                <button
                  type="button"
                  className="generation-action generation-action-copy"
                  aria-label={copyConfirmed ? 'Image COPIED' : 'Copy image to clipboard'}
                  onClick={handleCopyImage}
                  onMouseEnter={() => showTooltipAfterDelay('copy')}
                  onMouseLeave={hideTooltipAndCopyState}
                >
                  <svg className="action-icon-svg" viewBox="0 0 32 32" width="40" height="40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect className="action-icon-border" x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#595959" strokeOpacity="0.15"/>
                    <g clipPath="url(#clip-cp)" transform="translate(-40, 0)">
                      <path d="M58.8125 18.8125H62.1875V9.8125H53.1875V13.1875" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M58.8125 13.1875H49.8125V22.1875H58.8125V13.1875Z" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </g>
                    <defs><clipPath id="clip-cp"><rect width="18" height="18" fill="white" transform="translate(47 7)"/></clipPath></defs>
                  </svg>
                  <span className="generation-action-tooltip" data-visible={tooltip === 'copy'}>
                    {copyConfirmed ? (
                      <span className="generation-action-tooltip-copy-success">
                        <svg className="generation-action-tooltip-check" width="10" height="10" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                          <path d="M1.5 5L4 7.5L8.5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                        Image Copied
                      </span>
                    ) : (
                      'Copy'
                    )}
                  </span>
                </button>
                <button
                  type="button"
                  className="generation-action generation-action-regenerate"
                  aria-label="Regenerate cartoon"
                  onClick={() => {
                    hideTooltip();
                    handleGenerateImage();
                  }}
                  onMouseEnter={() => showTooltipAfterDelay('regenerate')}
                  onMouseLeave={hideTooltip}
                >
                  <svg className="action-icon-svg" viewBox="0 0 32 32" width="40" height="40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect className="action-icon-border" x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#595959" strokeOpacity="0.15"/>
                    <g clipPath="url(#clip-reg)" transform="translate(-80, 0)">
                      <path d="M98.8125 13.75H102.188V10.375" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M102.188 13.7499L100.199 11.7614C99.0475 10.6099 97.4884 9.9588 95.8599 9.94932C94.2314 9.93985 92.6649 10.5728 91.5 11.7108" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M93.1875 18.25H89.8125V21.625" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M89.8125 18.25L91.8009 20.2384C92.9525 21.3899 94.5116 22.041 96.1401 22.0505C97.7686 22.06 99.3351 21.4271 100.5 20.2891" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </g>
                    <defs><clipPath id="clip-reg"><rect width="18" height="18" fill="white" transform="translate(87 7)"/></clipPath></defs>
                  </svg>
                  <span className="generation-action-tooltip" data-visible={tooltip === 'regenerate'}>Regenerate</span>
                </button>
              </>
            ) : (
              <>
                <span className="generation-action generation-action-download generation-action-disabled" aria-hidden="true">
                  <svg className="action-icon-svg" viewBox="0 0 32 32" width="40" height="40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect className="action-icon-border" x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#595959" strokeOpacity="0.15"/>
                    <g clipPath="url(#clip-dl-disabled)">
                      <path d="M16 17.125V9.25" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M22.1875 17.125V21.625H9.8125V17.125" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M18.8125 14.3125L16 17.125L13.1875 14.3125" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </g>
                    <defs><clipPath id="clip-dl-disabled"><rect x="7" y="7" width="18" height="18" rx="2.5" fill="white"/></clipPath></defs>
                  </svg>
                </span>
                <span className="generation-action generation-action-copy generation-action-disabled" aria-hidden="true">
                  <svg className="action-icon-svg" viewBox="0 0 32 32" width="40" height="40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect className="action-icon-border" x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#595959" strokeOpacity="0.15"/>
                    <g clipPath="url(#clip-cp-disabled)" transform="translate(-40, 0)">
                      <path d="M58.8125 18.8125H62.1875V9.8125H53.1875V13.1875" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M58.8125 13.1875H49.8125V22.1875H58.8125V13.1875Z" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </g>
                    <defs><clipPath id="clip-cp-disabled"><rect width="18" height="18" fill="white" transform="translate(47 7)"/></clipPath></defs>
                  </svg>
                </span>
                <span className="generation-action generation-action-regenerate generation-action-disabled" aria-hidden="true">
                  <svg className="action-icon-svg" viewBox="0 0 32 32" width="40" height="40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect className="action-icon-border" x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="#595959" strokeOpacity="0.15"/>
                    <g clipPath="url(#clip-reg-disabled)" transform="translate(-80, 0)">
                      <path d="M98.8125 13.75H102.188V10.375" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M102.188 13.7499L100.199 11.7614C99.0475 10.6099 97.4884 9.9588 95.8599 9.94932C94.2314 9.93985 92.6649 10.5728 91.5 11.7108" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M93.1875 18.25H89.8125V21.625" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M89.8125 18.25L91.8009 20.2384C92.9525 21.3899 94.5116 22.041 96.1401 22.0505C97.7686 22.06 99.3351 21.4271 100.5 20.2891" stroke="black" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </g>
                    <defs><clipPath id="clip-reg-disabled"><rect width="18" height="18" fill="white" transform="translate(87 7)"/></clipPath></defs>
                  </svg>
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="generation-footer">
        <div className="footer-left">
          <span className="footer-text">©2026 CartoonGen</span>
          <span className="footer-text">Built by <a href="https://wilsonskinner.com/" className="footer-link">Wilson Skinner</a> & <a href="#" className="footer-link">Aryn Dagnas</a></span>
        </div>
        <div className="footer-right">
          <a href="#" className="footer-text">How it works</a>
          <a href="https://github.com/wilsskin/cartoon-gen" target="_blank" rel="noopener noreferrer" className="footer-text">Github repo</a>
        </div>
      </div>
    </div>
  );
};

export default GenerationPage;
