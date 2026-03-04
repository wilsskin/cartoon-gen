import { Link, useNavigate } from 'react-router-dom';

const HowItWorksPage = () => {
  const navigate = useNavigate();

  return (
    <div className="how-it-works-page">
      <div className="how-it-works-container">
        <div className="content-wrapper">
          <div className="hero-section hero-section--reduced-bottom">
            <h1 className="hero-title">How it works</h1>
            <div className="hero-content">
              <div className="hero-subtitle-container">
                <div
                  className="generation-back"
                  onClick={() => navigate('/')}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate('/'); } }}
                  aria-label="Back to headlines"
                >
                  <span className="back-text">Back to headlines</span>
                </div>
              </div>
            </div>
          </div>

          <div className="how-it-works-content">
            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">Overview</h2>
              <p className="how-it-works-p">
                CartoonGen pulls the top three headlines from five news outlets once each morning and lets users generate a satirical cartoon from the headlines.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">RSS Feeds</h2>
              <p className="how-it-works-p">
                Headlines and summaries are pulled from public RSS feeds by a Python script that runs once per day at 8am PST via Vercel Cron. The script fetches the RSS feeds from five news outlets and stores each headline, summary, URL, and publish date in a Neon database. The site only displays today's headlines.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">Image Generation</h2>
              <p className="how-it-works-p">
                Images are generated using Google's Gemini 2.5 Flash Image (Nano Banana). When the user clicks a headline, the app inserts the headline and its summary into a predefined prompt that contains instructions for the political cartoon style. The backend then sends this prompt to the Gemini API and returns the generated image for the user to download or copy. Sensitive or disturbing images are not generated or shown to users.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">Tech Stack</h2>
              <p className="how-it-works-p">
                The frontend is built with React and Vite. The backend is a Python API built with FastAPI. It pulls RSS feeds, communicates with the Gemini API for image generation, and serves data to the frontend. Headlines and related metadata are stored in a Neon database. The app is deployed on Vercel, which also runs the daily RSS ingestion job.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">Origin Story</h2>
              <p className="how-it-works-p">
              CartoonGen was born at a three hour SF hackathon in fall 2025. My partner <a href="https://github.com/aryandaga7" target="_blank" rel="noopener noreferrer" className="footer-link how-it-works-github-link">Aryan Dagnas</a> and I initially set out to build an app that used Sora to transform news headlines into short videos, but the API costs were too high, so we pivoted to image generation. After the hackathon ended, I continued building the project on my own. I integrated live RSS feeds, set up a daily cron job, and connected the Gemini API to generate satirical images from real headlines. You can explore the full codebase on <a href="https://github.com/wilsskin/cartoon-gen" target="_blank" rel="noopener noreferrer" className="footer-link how-it-works-github-link">GitHub</a>.
              </p>
            </section>
          </div>

          <div className="how-it-works-footer">
            <div className="footer-left">
              <span className="footer-text">Built by <a href="https://wilsonskinner.com/" target="_blank" rel="noopener noreferrer" className="footer-link">Wilson Skinner</a></span>
            </div>
            <div className="footer-right">
              <Link to="/" className="footer-text">Back to headlines</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HowItWorksPage;
