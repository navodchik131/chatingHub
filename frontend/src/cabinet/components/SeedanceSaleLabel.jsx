import { color } from '../styles/tokens';

/** «Seedance» + акцентное «Sale» для пункта меню и заголовков. */
export default function SeedanceSaleLabel({
  active = false,
  style,
  prefixStyle,
  accentStyle,
}) {
  const accentColor = active ? color.lime : '#FFB088';
  return (
    <span style={style}>
      <span style={prefixStyle}>Seedance</span>
      {' '}
      <span
        style={{
          color: accentColor,
          fontWeight: 800,
          letterSpacing: '0.02em',
          ...accentStyle,
        }}
      >
        Sale
      </span>
    </span>
  );
}
