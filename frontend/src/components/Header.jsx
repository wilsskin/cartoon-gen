import { useNavigate, useLocation } from 'react-router-dom';

const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const scrollToHeadlines = () => {
    const headlinesSection = document.getElementById('headlines-section');
    if (headlinesSection) {
      headlinesSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleGenerateClick = () => {
    if (location.pathname === '/') {
      scrollToHeadlines();
    } else {
      navigate('/');
      setTimeout(scrollToHeadlines, 100);
    }
  };

  return (
    <header className="header">
      <div className="header-content">
        <h1 className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          Cartoon Gen
        </h1>
        <nav className="nav">
          <button onClick={() => navigate('/')} className="nav-btn">
            Home
          </button>
          <button onClick={handleGenerateClick} className="nav-btn">
            Generate
          </button>
          <button onClick={handleGenerateClick} className="nav-btn primary">
            Get Started
          </button>
        </nav>
      </div>
    </header>
  );
};

export default Header;
