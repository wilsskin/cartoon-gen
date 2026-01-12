import headerIcon from '../assets/images/header-icon-3da00a.svg';

const Header = () => {
  // Get current date and format it as "Friday, October 10th"
  const currentDate = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric' };
  const formattedDate = currentDate.toLocaleDateString('en-US', options);

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-icon">
          <img src={headerIcon} alt="" width="24" height="24" />
        </div>
        <div className="header-date">
          {formattedDate}
        </div>
      </div>
    </header>
  );
};

export default Header;
