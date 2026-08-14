# Button Textures — Sandstone & Cement

## Overview

Procedural SVG filter-based textures for button surfaces using `feTurbulence`, `feDisplacementMap`, and `feDiffuseLighting`. Implemented on the kitchen sink cards & modals page for exploration and testing.

**Date:** 2026-08-09  
**Status:** Exploratory (not shipped)  
**Location:** `/app/public_app/templates/kitchen_sink/cards.html`

## Findings

### Dark Mode
- **Preferred texture:** Sandstone
- **Optimal depth:** 3.0
- **Edge roughness:** Disabled
- **Reason:** Sandstone's layered effect provides subtle depth without washing out text in dark backgrounds

### Light Mode
- **Preferred texture:** Cement
- **Optimal depth:** 4.0
- **Edge roughness:** Disabled
- **Reason:** Cement's uniform pattern scales better to higher depths; sandstone becomes too pronounced at depth 4

## CSS Implementation

```css
/* Sandstone filter — dark mode, depth 3.0 */
@media (prefers-color-scheme: dark) {
  main button::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    z-index: 1;
    pointer-events: none;
    opacity: 0.4;
    mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='texture' x='-50%25' y='-50%25' width='200%25' height='200%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='3' result='edgeNoise' seed='1'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='edgeNoise' scale='0' xChannelSelector='R' yChannelSelector='G' result='displacedGraphic'/%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.01 0.6' numOctaves='4' result='surfaceNoise'/%3E%3CfeDiffuseLighting in='surfaceNoise' lighting-color='%23ffffff' surfaceScale='5.0' result='bumpLight'%3E%3CfeDistantLight azimuth='45' elevation='60'/%3E%3C/feDiffuseLighting%3E%3CfeBlend mode='multiply' in='displacedGraphic' in2='bumpLight' result='texturedSolid'/%3E%3CfeComposite in='texturedSolid' in2='displacedGraphic' operator='in'/%3E%3C/filter%3E%3Crect width='256' height='256' fill='rgba(0,0,0,0.3)' filter='url(%23texture)'/%3E%3C/svg%3E");
    background-size: 256px 256px;
    background-attachment: scroll;
  }
}

/* Cement filter — light mode, depth 4.0 */
@media (prefers-color-scheme: light) {
  main button::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    z-index: 1;
    pointer-events: none;
    opacity: 0.8;
    mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='texture' x='-50%25' y='-50%25' width='200%25' height='200%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.08' numOctaves='5' result='noise1' seed='2'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='noise1' scale='0' xChannelSelector='R' yChannelSelector='G' result='displaced'/%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.03' numOctaves='3' result='noise2' seed='3'/%3E%3CfeDiffuseLighting in='noise2' lighting-color='%23ffffff' surfaceScale='4.8' result='lighting'%3E%3CfeDistantLight azimuth='135' elevation='45'/%3E%3C/feDiffuseLighting%3E%3CfeBlend mode='multiply' in='displaced' in2='lighting' result='textured'/%3E%3CfeComposite in='textured' in2='displaced' operator='in'/%3E%3C/filter%3E%3Crect width='256' height='256' fill='rgba(0,0,0,0.25)' filter='url(%23texture)'/%3E%3C/svg%3E");
    background-size: 256px 256px;
    background-attachment: scroll;
  }
}

main button {
  position: relative;
}

main button .icon,
main button span {
  position: relative;
  z-index: 2;
}
```

## Filter Parameters

### Sandstone (Dark Mode)
- `baseFrequency: 0.05` (coarse edge noise)
- `scale: 0` (edge roughness disabled)
- `surfaceScale: 5.0` (depth bump mapping)
- `opacity: 0.4` (reduced for dark backgrounds)
- `mix-blend-mode: overlay`

### Cement (Light Mode)
- `baseFrequency: 0.08` (finer, more uniform noise)
- `numOctaves: 5` (more detail layers)
- `scale: 0` (edge roughness disabled)
- `surfaceScale: 4.8` (moderate depth)
- `opacity: 0.8` (stronger presence on light backgrounds)
- `mix-blend-mode: overlay`

## Notes

- **Background attachment:** Always `scroll` (not `fixed`) so texture moves with button, not viewport
- **Text layer:** Ensure button text/icons have `position: relative; z-index: 2` to stay crisp above texture
- **Performance:** SVG filters are GPU-accelerated in modern browsers; test on mobile devices
- **Accessibility:** Textures are purely decorative; no functional impact on button behavior

## Next Steps

- Decide whether to ship textures or keep kitchen sink only
- If shipping, choose one texture type per mode or provide user preference toggle
- Consider performance impact on button-heavy pages (e.g., modal footers with 3+ buttons)
- Test on mobile Safari and older browsers (IE edge cases)
