# Hyundai Application and Portfolio Refresh Design

## Objective

Refresh Jonggeol Park's Hyundai Motor entry-level application, public portfolio website, and attached portfolio PDF as one consistent application package. Preserve the existing editorial visual identity while improving role fit, factual consistency, readability, localization, and accessibility. The application must be saved with the revised PDF attached, but never submitted by Codex.

## Source of Truth

A canonical content record will be created for the facts reused across the three deliverables. At minimum it will define:

- Korean and English names (`박종걸`, `Jonggeol Park`)
- employer and project names
- project periods and participation status
- verified performance metrics
- preferred terminology and spelling
- Hyundai-role relevance statements

Unsupported or internally contradictory claims will be removed rather than guessed. In particular, the `전 세계 버튜버 순위 25위(2022년 7월)` claim will be omitted unless a reliable source and correct date are available.

## Application Form

The application will retain the candidate's original experiences and voice while making the evidence-to-role connection more explicit.

### Changes

- Rewrite both self-introduction responses within the 1,000-character limits.
- Lead with the business or customer problem, then show action, quantified result, learning, and Hyundai contribution.
- Remove repetitive framing and generic claims.
- Correct `사이니` to `샤이니`, `버츄얼` to `버추얼`, `런칭` to `론칭`, and `컨셉카` to `콘셉트카`.
- Fill missing project institutions for CJ ENM and Binggrae projects.
- Harmonize Banana Salon's end date/status across all deliverables.
- Attach the revised PDF and save the application.

### Safety Boundary

Codex will stop immediately before entering or uploading application data and request one action-time confirmation. After confirmation, Codex may edit and save the application. Codex will not press the final submission button.

## Portfolio Website

The Flask structure and current editorial art direction will be retained. Changes will focus on content correctness and interaction quality instead of a visual redesign.

### Content and Localization

- Correct project-title and terminology errors.
- Prevent ranges such as `67–82%` from rendering as `6782%`.
- Replace remaining Korean UI text on English pages.
- Improve English hero and category copy.
- Normalize ongoing-period labels in both languages.
- Keep fallback behavior explicit so missing English content does not silently create mixed-language cards.

### Accessibility and Public Surface

- Make project cards keyboard-operable semantic controls.
- Localize modal labels and accessible names.
- Preserve focus behavior when opening and closing modals.
- Remove the public administrator link from the footer while keeping the admin route functional.

### Content Deployment

Code and template changes will be committed to the repository and verified locally. Production database-backed copy will be updated through the authenticated administration interface if required. Deployment will be verified after the code is pushed through the repository's existing Railway workflow.

## Portfolio PDF

Because no editable source file is available, the PDF will be regenerated rather than patched in place. Existing imagery and the cream/editorial visual language will be reused where practical.

### Structure

Target length is approximately 13 pages:

1. Cover and positioning statement
2. Profile and compact career summary
3. Core capabilities and selected outcomes
4–10. Selected projects, prioritizing Hyundai-relevant brand, content, fandom, and experience-design work
11. Other projects and awards
12. Transferable value for Hyundai brand marketing
13. Contact and portfolio link

### Editorial Rules

- Reduce dense paragraphs and make each project scannable as problem, role, action, result, and relevance.
- Use consistent spacing for Korean numbers and units, including `1,300만 회`.
- Remove high-school history and vague tool-proficiency labels.
- Replace tool lists with concrete evidence of AI-assisted production or workflow improvement.
- Keep metrics only when supported by the application or portfolio source material.

### Output Requirements

- Render and visually inspect every page.
- Keep the final upload below Hyundai's 2 MB limit, targeting 1.5–1.8 MB.
- Confirm text extraction, page count, links, image clarity, and absence of clipping.
- Save the user-facing PDF under the Codex `outputs` directory.

## Testing and Verification

Website behavior changes will be developed test-first. Automated coverage will include:

- localized UI labels and period formatting
- safe metric-range rendering
- semantic keyboard-operable project controls
- absence of the public admin link

The Flask application will receive a local smoke test and relevant automated tests. The PDF will receive render-based visual QA plus structural checks. Application form values will be re-read after saving, and the final state will be reported as ready for the user's submission.

## Non-Goals

- Final submission of the Hyundai application
- Inventing or inflating accomplishments
- Replacing the website's established visual identity
- Deleting existing untracked repository content

