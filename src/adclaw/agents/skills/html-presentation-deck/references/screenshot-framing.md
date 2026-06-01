# Screenshot Framing

Use screenshot framing when product UI, dashboards, website captures, or code screenshots need to fit the deck's visual system.

## Product Grid v2 Rules

- Use PG04 for one important screenshot and PG09 for evidence grids.
- Raw product screenshots with important UI labels use `.frame.r-16x10.fit-contain` and `data-image-slot="pg04-main-16x10"`.
- Generated or reconstructed evidence images must match their slot ratio and should not use `fit-contain`.
- Do not add fake browser chrome, drop shadows, rounded wrappers, gradient backgrounds, or nested frames.
- If a screenshot is too tall, split it into multiple slides or crop to the workflow region; do not shrink it until labels are unreadable.
- If screenshot text is not legible at 1440 x 900, the slide fails.

## Rules

- Preserve screenshot content when labels, numbers, or UI state matter.
- Choose the slide layout before choosing the screenshot crop.
- Use generated backgrounds as quiet framing surfaces, not as main illustrations.
- Do not add logos, mock browser chrome, or decorative frames unless the screenshot needs context.
- Hide sensitive data before placing the image.

## Background Assets

All built-in backgrounds are 2048×1152 WebP and crop-safe for `21:9`, `16:10`, `16:9`, `4:3`, and `1:1`.
Use asset root `../assets` with the asset keys below.

### Editorial

| Theme | Asset Key | Use |
|---|---|---|
| Ink Paper | `screenshot-backgrounds/editorial/ink-paper.webp` | Neutral paper texture and light ink wash |
| Indigo Porcelain | `screenshot-backgrounds/editorial/indigo-porcelain.webp` | Cool technology and research decks |
| Forest Ledger | `screenshot-backgrounds/editorial/forest-ledger.webp` | Operations, sustainability, and community |
| Warm Archive | `screenshot-backgrounds/editorial/warm-archive.webp` | Retrospectives and case studies |
| Sand Gallery | `screenshot-backgrounds/editorial/sand-gallery.webp` | Calm creative and design narratives |

### Clean Grid

| Theme | Asset Key | Use |
|---|---|---|
| Blue Anchor | `screenshot-backgrounds/clean-grid/blue-anchor.webp` | Product, engineering, and board decks |
| Lemon Signal | `screenshot-backgrounds/clean-grid/lemon-signal.webp` | Sharp contrast and decision moments |
| Lime Circuit | `screenshot-backgrounds/clean-grid/lime-circuit.webp` | Growth systems and automation |
| Orange Marker | `screenshot-backgrounds/clean-grid/orange-marker.webp` | Launches and urgent decisions |

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
Create a 2048x1152 abstract crop-safe presentation screenshot background. It must have no text, no logo, no people, no devices, no icons, no border, and no focal object. Keep the center and corners quiet so the image can be cropped to 21:9, 16:10, 4:3, or 1:1. Use subtle texture, low contrast, and the specified theme colors only.
```
