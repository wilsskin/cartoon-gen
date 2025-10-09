import { useRef, useEffect, useState } from 'react';

const CanvasMeme = ({ backgroundImageUrl, captionText, isLoading }) => {
  const canvasRef = useRef(null);
  const downloadLinkRef = useRef(null);
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

      // Update the download link with the new canvas content
      try {
        const dataUrl = canvas.toDataURL('image/png');
        downloadLinkRef.current.href = dataUrl;
      } catch (err) {
        console.error("Could not update canvas data URL:", err);
      }
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
          border: '2px solid #FCE9BE',
          borderRadius: '8px',
          width: '512px',
          height: '512px',
          display: isLoading ? 'none' : 'block'
        }}
      />
      {isLoading && (
        <div style={{
          width: '512px',
          height: '512px',
          border: '2px solid #FCE9BE',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#FCE9BE',
          color: '#1a1a1a',
          fontSize: '20px',
          fontWeight: '600',
          fontFamily: '"Crimson Text", Georgia, serif'
        }}>
          <p>Loading...</p>
        </div>
      )}
      <a
        ref={downloadLinkRef}
        href="#"
        download="satire-meme.png"
        className="download-btn"
        style={{
          display: imageError || isLoading ? 'none' : 'block',
          textDecoration: 'none',
          color: 'white',
          padding: '0.6em 1.2em'
        }}
        onClick={(e) => {
          if (!downloadLinkRef.current.href || downloadLinkRef.current.href === '#') {
            e.preventDefault();
          }
        }}
      >
        Download Meme
      </a>
    </div>
  );
};

export default CanvasMeme;
