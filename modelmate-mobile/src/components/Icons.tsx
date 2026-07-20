import type { ReactNode } from 'react';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { color } from '@/src/styles/tokens';

type IconProps = { size?: number; stroke?: string };

function IconBase({ size = 16, stroke = color.text, children }: IconProps & { children: ReactNode }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </Svg>
  );
}

export function IcoHome({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M4 11.5L12 4l8 7.5" />
      <Path d="M6 10v9.5h12V10" />
    </IconBase>
  );
}

export function IcoChat({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M21 12c0 4.4-4 8-9 8-1.2 0-2.4-.2-3.4-.6L3 21l1.7-4.1C3.6 15.5 3 13.8 3 12c0-4.4 4-8 9-8s9 3.6 9 8z" />
    </IconBase>
  );
}

export function IcoBolt({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M13 2.5L5 13.5h6l-1 8 9-11.5h-6z" />
    </IconBase>
  );
}

export function IcoUser({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Circle cx="12" cy="8.5" r="3.8" />
      <Path d="M4.5 20c1-4 3.8-6.2 7.5-6.2s6.5 2.2 7.5 6.2" />
    </IconBase>
  );
}

export function IcoShield({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M12 3l7 3v5.5c0 4.5-3 7.8-7 9.5-4-1.7-7-5-7-9.5V6z" />
      <Path d="M9 12l2 2 4-4" />
    </IconBase>
  );
}

export function IcoImage({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Rect x="3" y="4" width="18" height="16" rx="3" />
      <Circle cx="9" cy="10" r="1.8" />
      <Path d="M3.5 18l5-5 3.5 3.5L16 12l4.5 5" />
    </IconBase>
  );
}

export function IcoFilm({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Rect x="3" y="5" width="18" height="14" rx="3" />
      <Path d="M10 9.5l5 2.5-5 2.5z" />
    </IconBase>
  );
}

export function IcoStar({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Circle cx="12" cy="8.5" r="3.6" />
      <Path d="M5 20c.8-3.4 3.6-5.4 7-5.4s6.2 2 7 5.4" />
    </IconBase>
  );
}

export function IcoHeart({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M12 20.5S4 15.3 4 9.8C4 7 6.2 5 8.7 5c1.4 0 2.6.7 3.3 1.7C12.7 5.7 13.9 5 15.3 5 17.8 5 20 7 20 9.8c0 5.5-8 10.7-8 10.7z" />
    </IconBase>
  );
}

export function IcoSend({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M5 12h14M13 6l6 6-6 6" />
    </IconBase>
  );
}

export function IcoPlus({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M12 5v14M5 12h14" />
    </IconBase>
  );
}

export function IcoBack({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M15 5l-7 7 7 7" />
    </IconBase>
  );
}

export function IcoChevron({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M9 6l6 6-6 6" />
    </IconBase>
  );
}

export function IcoUsers({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Circle cx="9" cy="9" r="3.2" />
      <Path d="M3.5 19.5c.6-2.9 2.9-4.6 5.5-4.6s4.9 1.7 5.5 4.6" />
      <Circle cx="17" cy="10" r="2.5" />
      <Path d="M16 15.2c2.3.2 4 1.7 4.5 4.3" />
    </IconBase>
  );
}

export function IcoCard({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Rect x="3" y="5.5" width="18" height="13" rx="3" />
      <Path d="M3 10h18" />
    </IconBase>
  );
}

export function IcoPlug({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M9 7V3.5M15 7V3.5" />
      <Path d="M7 7h10v4a5 5 0 0 1-10 0z" />
      <Path d="M12 16v4.5" />
    </IconBase>
  );
}

export function IcoCog({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Circle cx="12" cy="12" r="3" />
      <Path d="M12 3.5v2M12 18.5v2M20.5 12h-2M5.5 12h-2M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4M17.7 17.7l-1.4-1.4M7.7 7.7L6.3 6.3" />
    </IconBase>
  );
}

export function IcoFinger({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M12 4a7 7 0 0 1 7 7c0 3-1 4.5-1 7" />
      <Path d="M12 4a7 7 0 0 0-7 7c0 2 .3 3.4.9 4.6" />
      <Path d="M12 8.2a3 3 0 0 1 3 3c0 3.2-1 5-2.2 7.5" />
      <Path d="M12 8.2a3 3 0 0 0-3 3c0 1.7.2 2.9.6 4" />
      <Path d="M12 12.2a1 1 0 0 1 1 1c0 2.6-.6 4-1.4 5.8" />
    </IconBase>
  );
}

export function IcoTelegram({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M21 4.5L3.5 11.2c-.9.35-.85 1.6.1 1.85l4.4 1.2 1.7 5.2c.3.85 1.4 1 1.9.3l2.4-3.1 4.5 3.3c.75.55 1.8.15 2-.75L23 6c.25-1.1-.85-2-1.9-1.5z" />
    </IconBase>
  );
}

export function IcoWand({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M4 20L15 9" />
      <Path d="M17 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z" />
      <Path d="M6.5 3.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z" />
      <Path d="M18.5 13.5l.5 1.2 1.2.5-1.2.5-.5 1.2-.5-1.2-1.2-.5 1.2-.5z" />
    </IconBase>
  );
}

export function IcoIdCard({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Rect x="3" y="5" width="18" height="14" rx="3" />
      <Circle cx="9" cy="11" r="2" />
      <Path d="M6 16c.6-1.6 1.7-2.4 3-2.4s2.4.8 3 2.4" />
      <Path d="M14.5 9.5h4M14.5 12.5h4" />
    </IconBase>
  );
}

export function IcoUpload({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M12 16V5" />
      <Path d="M7.5 9L12 4.5 16.5 9" />
      <Path d="M4 16.5v1.5A2.5 2.5 0 0 0 6.5 20.5h11a2.5 2.5 0 0 0 2.5-2.5v-1.5" />
    </IconBase>
  );
}

export function IcoFaceId({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Rect x="4" y="4" width="16" height="16" rx="6" />
      <Circle cx="9" cy="10" r="1" />
      <Circle cx="15" cy="10" r="1" />
      <Path d="M9 15c1 1 2 1.4 3 1.4s2-.4 3-1.4" />
      <Path d="M4 8V6.5A2.5 2.5 0 0 1 6.5 4H8M16 4h1.5A2.5 2.5 0 0 1 20 6.5V8M20 16v1.5a2.5 2.5 0 0 1-2.5 2.5H16M8 20H6.5A2.5 2.5 0 0 1 4 17.5V16" />
    </IconBase>
  );
}

/** 2×2 grid — кнопка выбора темы чата (ModelMate Mobile.dc.html). */
export function IcoThemeGrid({ size = 25, stroke = color.muted }: IconProps) {
  return (
    <Svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <Rect x="3" y="3" width="7" height="7" rx="2" />
      <Rect x="14" y="3" width="7" height="7" rx="2" />
      <Rect x="3" y="14" width="7" height="7" rx="2" />
      <Rect x="14" y="14" width="7" height="7" rx="2" />
    </Svg>
  );
}

/** Приоткрытая дверь + стрелка наружу — выход из аккаунта. */
export function IcoLogout({ size, stroke }: IconProps) {
  return (
    <IconBase size={size} stroke={stroke}>
      <Path d="M3 21V5a2 2 0 0 1 2-2h7v18H5a2 2 0 0 1-2-2z" />
      <Path d="M12 3l7 2.2v13.6L12 21" />
      <Path d="M15.5 12H22" />
      <Path d="M19.5 9.5L22 12l-2.5 2.5" />
    </IconBase>
  );
}
