# Screenshot Framing

Use screenshot framing when product UI, dashboards, website captures, or code screenshots need to fit the deck's visual system.

## Rules

- Preserve screenshot content when labels, numbers, or UI state matter.
- Choose the slide layout before choosing the screenshot crop.
- Use generated backgrounds as quiet framing surfaces, not as main illustrations.
- Do not add logos, mock browser chrome, or decorative frames unless the screenshot needs context.
- Hide sensitive data before placing the image.

## Background Assets

All built-in backgrounds are 1920×1080 WebP and crop-safe for `21:9`, `16:10`, `16:9`, `4:3`, and `1:1`.

### Editorial

| Theme | Asset | Use |
|---|---|---|
| Ink Paper | `assets/screenshot-backgrounds/editorial/ink-paper.webp` | Neutral paper texture and light ink wash |
| Indigo Porcelain | `assets/screenshot-backgrounds/editorial/indigo-porcelain.webp` | Cool technology and research decks |
| Forest Ledger | `assets/screenshot-backgrounds/editorial/forest-ledger.webp` | Operations, sustainability, and community |
| Warm Archive | `assets/screenshot-backgrounds/editorial/warm-archive.webp` | Retrospectives and case studies |
| Sand Gallery | `assets/screenshot-backgrounds/editorial/sand-gallery.webp` | Calm creative and design narratives |

### Clean Grid

| Theme | Asset | Use |
|---|---|---|
| Blue Anchor | `assets/screenshot-backgrounds/clean-grid/blue-anchor.webp` | Product, engineering, and board decks |
| Lemon Signal | `assets/screenshot-backgrounds/clean-grid/lemon-signal.webp` | Sharp contrast and decision moments |
| Lime Circuit | `assets/screenshot-backgrounds/clean-grid/lime-circuit.webp` | Growth systems and automation |
| Orange Marker | `assets/screenshot-backgrounds/clean-grid/orange-marker.webp` | Launches and urgent decisions |

## Framing Presets

Editorial screenshot:

```text
ratio: 16:10
background: editorial theme asset
padding: 7%
shadow: soft
corners: 12px
alignment: center
```

Clean Grid screenshot:

```text
ratio: 21:9 or 16:10
background: clean grid theme asset
padding: 5%
shadow: none
corners: 0
alignment: center
```

## Asset Generation Prompt Pattern

Use this only when regenerating the committed assets.

```text
Create a 1920x1080 abstract crop-safe presentation screenshot background. It must have no text, no logo, no people, no devices, no icons, no border, and no focal object. Keep the center and corners quiet so the image can be cropped to 21:9, 16:10, 4:3, or 1:1. Use subtle texture, low contrast, and the specified theme colors only.
```
