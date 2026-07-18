const HOVER_MAP = {
  borderColor: ['--mm-h-bc', 'hBc'],
  background: ['--mm-h-bg', 'hBg'],
  color: ['--mm-h-c', 'hC'],
  filter: ['--mm-h-filter', 'hFilter'],
  opacity: ['--mm-h-op', 'hOp'],
  transform: ['--mm-h-tf', 'hTf'],
};

function hoverProps(hover = {}) {
  const style = {};
  const data = {};
  for (const [key, [cssVar, flag]] of Object.entries(HOVER_MAP)) {
    const val = hover[key];
    if (val != null && val !== '') {
      style[cssVar] = val;
      data[flag] = '';
    }
  }
  return { style, data };
}

/**
 * Hover через CSS :hover — не залипает после клика/focus (в отличие от React state).
 */
export default function Hoverable({
  as: Tag = 'div',
  style,
  hover = {},
  children,
  onClick,
  className = '',
  ...rest
}) {
  const interactive = typeof onClick === 'function';
  const { style: hovStyle, data: hovData } = hoverProps(hover);

  const handleClick = (e) => {
    onClick?.(e);
    if (e.currentTarget instanceof HTMLElement) {
      e.currentTarget.blur();
    }
  };

  return (
    <Tag
      {...rest}
      {...hovData}
      className={['mm-hov', className].filter(Boolean).join(' ')}
      style={{ boxSizing: 'border-box', ...style, ...hovStyle }}
      onClick={interactive ? handleClick : onClick}
      {...(interactive && Tag !== 'button'
        ? {
            role: rest.role ?? 'button',
            tabIndex: rest.tabIndex ?? -1,
            onKeyDown: (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleClick(e);
              }
              rest.onKeyDown?.(e);
            },
          }
        : {})}
    >
      {children}
    </Tag>
  );
}
