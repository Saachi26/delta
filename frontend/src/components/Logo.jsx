// the delta symbol drawn open, so it reads as change rather than a solid arrow
export default function Logo() {
  return (
    <svg
      className="logo"
      viewBox="6 5.5 12 12.5"
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10 17H7L12 6.5L17 17H14" />
    </svg>
  );
}
