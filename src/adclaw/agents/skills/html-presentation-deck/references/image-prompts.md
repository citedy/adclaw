# Image Prompts

Use these prompts when the deck needs generated images. Keep prompts short and tied to the slide slot.

## General Rules

- Match the selected visual system: Editorial or Clean Grid.
- Generate to the final slot ratio before placing the image.
- Do not generate slide chrome, page numbers, titles, footers, watermarks, or logos inside images.
- If text must appear inside an image, keep it in the same language as the deck.
- Prefer real-world visual evidence over decorative filler.

## Product Grid Slot Rules

Product Grid v2 images must be generated for the target slot before insertion:

- `pg01-hero-16x9`: product launch visual, realistic product context, no UI labels unless they are meant to be inspected.
- `pg04-main-16x10`: raw product screenshot or screenshot reconstruction; preserve all important UI text.
- `pg09-evidence-16x9`: evidence visual, market proof, workflow diagram, or before/after graphic.

Do not generate atmospheric filler. If the slide needs proof, use a real screenshot
or a diagram with clear information hierarchy.

## Product Grid Launch Visual

```text
16:9 product launch visual for [product]. Clean SaaS presentation style, real product context, strict rectangular composition, generous whitespace, one accent color, no gradients, no glassmorphism, no rounded cards, no slide title, no footer, no watermark.
```

## Product Grid Screenshot Reconstruction

```text
16:10 product UI screenshot reconstruction for [workflow]. Keep labels short and readable, align to a strict grid, use realistic SaaS controls, one accent color, no browser chrome, no decorative background, no watermark.
```

## Product Grid Evidence Diagram

```text
16:9 evidence diagram for [claim]. Three to five rectangular modules, left-aligned labels, thin rules, one accent color, high contrast, no gradient, no shadow, no rounded shapes, no footer, no logo.
```

## Editorial Photo

```text
Horizontal editorial documentary photograph about [topic]. Natural light, restrained color, quiet negative space, realistic environment, subtle grain, premium magazine feel. No logo, no watermark, no text, no artificial interface. Ratio: [16:9 or 16:10].
```

## Editorial Diagram

```text
Horizontal editorial information graphic explaining [concept]. Paper texture, thin ink lines, numbered structure, restrained accent color, generous whitespace. Text labels in English only and under four words each. No logo, no decorative border. Ratio: 16:9.
```

## Clean Grid Diagram

```text
Horizontal clean grid information graphic explaining [system]. Sharp rectangular modules, left-aligned short labels, one accent color, black white and gray only, no gradients, no rounded glass effects, no 3D, no logo. Ratio: [21:9 or 16:10].
```

## Clean Grid Data Visual

```text
Minimal data visual for [metric]. Large number, thin rules, strict grid, one accent color, high contrast, executive presentation style. No page header, no footer, no logo, no watermark. Ratio: 16:9.
```
