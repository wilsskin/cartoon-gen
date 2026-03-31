import { Link, useNavigate } from 'react-router-dom';
import foxLogo from '../assets/images/fox-us.svg';
import nbcLogo from '../assets/images/nbc.svg';
import nytLogo from '../assets/images/nyt.svg';
import nprLogo from '../assets/images/npr.svg';
import wsjLogo from '../assets/images/wsj.svg';

const FEED_LOGOS = {
  fox_us: foxLogo,
  nbc_top: nbcLogo,
  nyt_home: nytLogo,
  npr_news: nprLogo,
  wsj_us: wsjLogo,
};

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
              <div className="how-it-works-logo-row">
                {['fox_us', 'nbc_top', 'nyt_home', 'npr_news', 'wsj_us'].map((feedId) => (
                  <span key={feedId} className={`logo-frame logo-frame--how logo-feed--${feedId}`}>
                    <img src={FEED_LOGOS[feedId]} alt="" />
                  </span>
                ))}
              </div>
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

            <section className="how-it-works-section">
              <h2 className="how-it-works-h2">Gemini Prompt</h2>
              <div className="prompt-block">
                <pre className="prompt-pre">{`Create a political cartoon about this headline: `}<span className="prompt-var">{`{headline}`}</span>{`\nContext: `}<span className="prompt-var">{`{summary}`}</span>{`\n\n`}<span className="prompt-section">{`## Task & Constraints`}</span>{`\n- Square format (1:1 aspect ratio), solid white background\n- Maximum 2–3 visual elements total\n- New Yorker editorial cartoon style: confident ink lines, limited color palette (black, white, gray + 1–2 accent colors max)\n- Use satire to critique power, systems, or institutions. Avoid personal attacks\n\n`}<span className="prompt-section">{`## Style & Approach`}</span>{`\n- Must work as a visual joke, pun, or ironic juxtaposition. Not a literal illustration of the headline\n- If depicting a real person: exaggerate distinctive features (hair, expression, posture) for instant recognition\n- Use a single strong visual metaphor that creates an "aha" moment\n- Do not create infographics, diagrams, or explanatory illustrations\n\n`}<span className="prompt-section">{`## Text Rules`}</span>{`\n- Use text only for: speech bubbles, signs held by characters, or essential 1–2 word labels\n- Never use text to explain the joke or add multiple labels\n- When in doubt, use less text`}</pre>
              </div>
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
