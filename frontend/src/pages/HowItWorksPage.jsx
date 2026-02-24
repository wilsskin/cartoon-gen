import { Link, useNavigate } from 'react-router-dom';
import arrowBack from '../assets/images/arrow-back.svg';

const HowItWorksPage = () => {
  const navigate = useNavigate();

  return (
    <div className="how-it-works-page">
      <div className="how-it-works-container">
        <div className="content-wrapper">
          <div className="generation-back" onClick={() => navigate('/')} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate('/'); } }} aria-label="Back to headlines">
            <img src={arrowBack} alt="" className="back-arrow" width="16" height="16" />
            <span className="back-text">Back to headlines</span>
          </div>

          <div className="how-it-works-hero">
            <h1 className="how-it-works-title">How it works</h1>
            <p className="how-it-works-subtext"><a href="https://github.com/wilsonskinner/cartoongen" target="_blank" rel="noopener noreferrer" className="footer-link"> View Github repository</a></p>
          </div>

          <div className="how-it-works-content">
            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">Pick a headline</h2>
              <p className="how-it-works-p">
                On the home page you’ll see a list of today’s top news headlines from sources like the New York Times, NPR, and others. Each headline is a real story that was published recently. Tap or click any headline to turn it into a cartoon.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">We draw the cartoon for you</h2>
              <p className="how-it-works-p">
                After you choose a headline, our system reads the story and creates a single-panel political cartoon that captures the idea in a simple, visual way. You don’t need to draw anything—the cartoon is generated in a few seconds. You can then download it, copy it, or try again to get a different take.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">How the site was built</h2>
              <p className="how-it-works-p">
                CartoonGen started as a project at a San Francisco hackathon. The app pulls in real headlines from news feeds, then uses an AI image model to illustrate them in a cartoon style. The goal is to make it easy for anyone to see a quick, satirical take on the news—no design or coding skills required.
              </p>
            </section>

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">A note on limits and safety</h2>
              <p className="how-it-works-p">
                To keep the service fast and fair for everyone, we limit how many cartoons each person can generate in a short period. Sometimes the AI may decline to illustrate a headline if it touches on sensitive topics; in those cases you’ll see a short message and can try a different headline instead.
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
