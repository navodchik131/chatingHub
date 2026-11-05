import { useState } from 'react';

/**
 * The prototype used a non-standard `style-hover="..."` attribute.
 * React has no hover pseudo-class for inline styles, so this primitive
 * merges a hover patch into the base style on pointer enter/leave.
 *
 * Usage:
 *   <Hoverable as="div" style={base} hover={{ borderColor: '...' }} onClick={...}>
 */
export default function Hoverable({
  as: Tag = 'div',
  style,
  hover = {},
  children,
  onClick,
  ...rest
}) {
  const [on, setOn] = useState(false);

  const interactive = typeof onClick === 'function';

  return (
    <Tag
      style={on ? { ...style, ...hover } : style}
      onMouseEnter={() => setOn(true)}
      onMouseLeave={() => setOn(false)}
      onFocus={() => setOn(true)}
      onBlur={() => setOn(false)}
      onClick={onClick}
      {...(interactive && Tag !== 'button'
        ? {
            role: rest.role ?? 'button',
            tabIndex: rest.tabIndex ?? 0,
            onKeyDown: (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick(e);
              }
              rest.onKeyDown?.(e);
            },
          }
        : {})}
      {...rest}
    >
      {children}
    </Tag>
  );
}
