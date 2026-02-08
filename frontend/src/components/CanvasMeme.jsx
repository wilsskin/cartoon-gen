import { useRef, useEffect, useState } from 'react';

const CanvasMeme = ({ backgroundImageUrl, captionText, isLoading }) => {
  const canvasRef = useRef(null);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    if (!backgroundImageUrl || isLoading) return;

    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');
    const img = new Image();

    // This is important for fetching images from the backend API
    img.crossOrigin = 'Anonymous';

    img.onload = () => {
      setImageError(false);

      // Set canvas dimensions to match the image
      canvas.width = img.width;
      canvas.height = img.height;

      // Draw the background image
      context.drawImage(img, 0, 0);
    };

    img.onerror = () => {
      setImageError(true);
      // Create a placeholder on the canvas
      canvas.width = 512;
      canvas.height = 512;
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = '#FEF4DF';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = '#1a1a1a';
      context.font = '16px "Crimson Text", Georgia, serif';
      context.textAlign = 'center';
      context.fillText('Image not yet available', canvas.width / 2, canvas.height / 2 - 10);
      context.fillText('Add images to backend/static/images/', canvas.width / 2, canvas.height / 2 + 15);
    };

    img.src = backgroundImageUrl;

  }, [backgroundImageUrl, captionText, isLoading]);

  return (
    <div>
      <canvas
        ref={canvasRef}
        style={{
          border: 'none',
          borderRadius: '8px',
          width: '512px',
          height: '512px',
          maxWidth: '100%',
          maxHeight: '100%',
          objectFit: 'contain',
          display: isLoading ? 'none' : 'block'
        }}
      />
      {isLoading && (
        <div
          className="generation-loading-container"
          style={{
            width: '512px',
            height: '512px',
            maxWidth: '100%',
            maxHeight: '100%',
            border: 'none',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#f5f5f5',
          }}
          aria-hidden="true"
        >
          <div className="generation-loading-square-wrap">
            <svg
              className="generation-loading-square-svg"
              viewBox="0 0 48 48"
              width="48"
              height="48"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              {/* Square path: bottom (L→R), right (↑), top (R→L), left (↓). Total length 192. */}
              <path
                className="generation-loading-square-path"
                d="M 0 48 L 48 48 L 48 0 L 0 0 L 0 48"
                stroke="#000000"
                strokeWidth="3"
                strokeLinecap="square"
              />
            </svg>
          </div>
        </div>
      )}
    </div>
  );
};

export default CanvasMeme;
