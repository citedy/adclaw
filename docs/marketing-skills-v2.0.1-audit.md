# Marketing Skills v2.0.1 Audit

Date: 2026-05-26

Source package: `coreyhaines31/marketingskills`

Installer result: `npx skills add coreyhaines31/marketingskills -y` found 41 skills.

## Result

- Upgraded 31 existing AdClaw built-in marketing skills by syncing v2.0.1 content into the existing `marketing-*` skill directories.
- Added 10 new AdClaw built-in marketing skills using the existing `marketing-*` naming convention.
- Left existing Citedy, SEO, ads, agency, and platform skills in place.
- Private AdClaw static skill security scan passed for all 41 v2.0.1 source skills with zero missing skills, blocked findings, or warnings.
- Targeted private validator regression tests passed: `90 passed, 1 skipped`.
- Live LLM audit was attempted through `tests/test_skill_validator_real.py`, but the test file skipped because no `QWEN_API_KEY`, `GLM_API_KEY`, or `OPENAI_API_KEY` was available in `/root/.env` or the private checkout.

## Upgraded Existing Skills

| v2.0.1 source | AdClaw built-in skill |
| --- | --- |
| `ab-testing` | `marketing-ab-test-setup` |
| `ad-creative` | `marketing-ad-creative` |
| `ads` | `marketing-paid-ads` |
| `ai-seo` | `marketing-ai-seo` |
| `analytics` | `marketing-analytics-tracking` |
| `churn-prevention` | `marketing-churn-prevention` |
| `cold-email` | `marketing-cold-email` |
| `competitors` | `marketing-competitor-alternatives` |
| `content-strategy` | `marketing-content-strategy` |
| `copy-editing` | `marketing-copy-editing` |
| `copywriting` | `marketing-copywriting` |
| `cro` | `marketing-page-cro` |
| `emails` | `marketing-email-sequence` |
| `free-tools` | `marketing-free-tool-strategy` |
| `launch` | `marketing-launch-strategy` |
| `marketing-ideas` | `marketing-marketing-ideas` |
| `marketing-psychology` | `marketing-psychology` |
| `onboarding` | `marketing-onboarding-cro` |
| `paywalls` | `marketing-paywall-upgrade-cro` |
| `popups` | `marketing-popup-cro` |
| `pricing` | `marketing-pricing-strategy` |
| `product-marketing` | `marketing-product-marketing-context` |
| `programmatic-seo` | `marketing-programmatic-seo` |
| `referrals` | `marketing-referral-program` |
| `revops` | `marketing-revops` |
| `sales-enablement` | `marketing-sales-enablement` |
| `schema` | `marketing-schema-markup` |
| `seo-audit` | `marketing-seo-audit` |
| `signup` | `marketing-signup-flow-cro` |
| `site-architecture` | `marketing-site-architecture` |
| `social` | `marketing-social-content` |

## Added New Skills

| v2.0.1 source | New AdClaw built-in skill |
| --- | --- |
| `aso` | `marketing-aso` |
| `co-marketing` | `marketing-co-marketing` |
| `community-marketing` | `marketing-community-marketing` |
| `competitor-profiling` | `marketing-competitor-profiling` |
| `customer-research` | `marketing-customer-research` |
| `directory-submissions` | `marketing-directory-submissions` |
| `image` | `marketing-image` |
| `lead-magnets` | `marketing-lead-magnets` |
| `sms` | `marketing-sms` |
| `video` | `marketing-video` |

## Notable v2.0.1 Additions Verified

- `marketing-image` includes the May 2026 image model lineup: Gemini Nano Banana Pro, Flux, Ideogram 3.0, ChatGPT Images 2.0 / GPT Image, Midjourney v7, Recraft V3, and Stable Diffusion.
- `marketing-video` includes the May 2026 video model lineup: Veo 3, Sora 2, Runway Gen-4, Kling 2.5/3.0, Seedance, Hailuo / MiniMax, Pika 2.x, Hunyuan Video, and Wan 2.
- `marketing-ad-creative` includes ChatGPT Images 2.0 in its generative tools reference.
- Community PR coverage is present through the new skills and references for community marketing, competitor profiling, directory submissions, AI SEO, and research workflows.
