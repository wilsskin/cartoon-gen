import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CanvasMeme from '../components/CanvasMeme';
import arrowBack from '../assets/images/arrow-back.svg';
import actionIcons from '../assets/images/action-icons.svg';

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

const GenerationPage = ({ selectedNews }) => {
  const navigate = useNavigate();
  const [currentImageUrl, setCurrentImageUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorDetails, setErrorDetails] = useState(null); // { code, message, status, model, requestId, details }
  const [showErrorDetails, setShowErrorDetails] = useState(false);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const lastHeadlineIdRef = useRef(null);

  useEffect(() => {
    // Redirect to home if no news is selected
    if (!selectedNews) {
      navigate('/');
      return;
    }

    // Set the initial image (empty for RSS items)
    setCurrentImageUrl(selectedNews.initialImageUrl ? `${API_BASE_URL}${selectedNews.initialImageUrl}` : '');

    // Auto-generate cartoon when user lands after clicking a headline
    if (lastHeadlineIdRef.current !== selectedNews.id) {
      lastHeadlineIdRef.current = selectedNews.id;
      handleGenerateImage('Default');
    }
  }, [selectedNews, navigate]);

  const handleGenerateImage = (style) => {
    if (!selectedNews) return;

    setIsLoading(true);
    setError('');
    setErrorDetails(null);
    setShowErrorDetails(false);
    setIsRateLimited(false);

    axios.post(`${API_BASE_URL}/api/generate-image`, {
      headlineId: selectedNews.id,
      style: style,
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
      setIsLoading(false);
    });
  };

  if (!selectedNews) {
    return null;
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
                isLoading={isLoading}
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

          {/* Action Icons - leftmost is download */}
          <div className="generation-actions">
            <img src={actionIcons} alt="Actions" className="action-icons" />
            {currentImageUrl && !isLoading && !error ? (
              <a
                href={currentImageUrl}
                download={downloadFilename}
                className="generation-action-download"
                title="Download cartoon"
                aria-label="Download cartoon as PNG"
              />
            ) : (
              <span className="generation-action-download generation-action-download-disabled" aria-hidden="true" />
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="generation-footer">
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
  );
};

export default GenerationPage;
