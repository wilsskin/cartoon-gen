import { useNavigate } from 'react-router-dom';
import cgLogo from '../assets/images/cg-logo.png';

const Header = () => {
  const navigate = useNavigate();

  // Get current date and format it as "Friday, October 10th"
  const currentDate = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric' };
  const formattedDate = currentDate.toLocaleDateString('en-US', options);

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-icon" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <img src={cgLogo} alt="CartoonGen Logo" height="24" />
        </div>
        <div className="header-date">
          {formattedDate}
        </div>
      </div>
    </header>
  );
};

export default Header;
