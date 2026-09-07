# Hyundai Application and Portfolio Refresh Implementation Plan

> **For Codex:** Execute each task in order. Keep the Hyundai final-submit action out of scope. Use test-first development for website behavior and fresh verification before reporting completion.

**Goal:** Deliver one factually consistent Hyundai application package across the application form, portfolio website, and a sub-2 MB portfolio PDF.

**Architecture:** Store reusable claims, names, dates, and terminology in a canonical JSON record. Add small presentation helpers to the Flask app for locale-aware labels and periods, keep content rendering in Jinja, and regenerate the PDF from HTML/CSS plus recovered portfolio imagery. Keep browser form editing until all local artifacts have passed verification.

**Tech Stack:** Flask, Jinja2, vanilla JavaScript/CSS, pytest, Playwright/browser inspection, Python PDF tooling, Poppler rendering.

---

## Task 1: Establish Canonical Application Content

**Files:**
- Create: `data/hyundai_application_2026.json`
- Create: `tests/test_application_content.py`

1. Write a failing schema/content test that requires consistent Korean/English names, project institutions, normalized project titles, periods, approved terminology, and two application responses of at most 1,000 Korean characters each.
2. Run `pytest tests/test_application_content.py -q` and confirm failure because the content record does not exist.
3. Create the canonical JSON using only claims present in the existing application, public website, or source PDF.
4. Remove the contradictory worldwide VTuber ranking claim unless it can be verified.
5. Run the focused test and confirm it passes.
6. Commit as `content: unify Hyundai application facts and copy`.

## Task 2: Add Locale and Display Helpers

**Files:**
- Modify: `app.py`
- Create: `tests/conftest.py`
- Create: `tests/test_public_portfolio.py`

1. Add failing tests for Korean/English labels, English ongoing-period display, and preservation of metric ranges such as `67–82%`.
2. Run `pytest tests/test_public_portfolio.py -q` and confirm the expected failures.
3. Add small locale dictionaries and a `display_period` helper in `app.py`; expose them to the public template.
4. Ensure text is escaped by default and no helper strips punctuation from KPI strings.
5. Run the focused tests and confirm they pass.
6. Commit as `feat: add locale-aware portfolio display helpers`.

## Task 3: Improve Public Project Interaction and Localization

**Files:**
- Modify: `templates/index.html`
- Modify: `templates/base.html`
- Modify: `static/js/main.js`
- Modify: `static/css/main.css`
- Modify: `tests/test_public_portfolio.py`

1. Add failing assertions for semantic keyboard-operable project controls, localized modal/gallery labels, locale-specific detail text, and absence of a public admin link.
2. Run the focused tests and confirm failure.
3. Give project cards button semantics and accessible names while retaining the visual card layout.
4. Localize `View details`, `Key results`, `Details`, modal close, gallery controls, slide labels, loading text, and view-count units.
5. Restore focus to the triggering card after modal close and support Enter/Space activation.
6. Replace the CSS-generated Korean-only detail label with locale-aware markup or a data attribute.
7. Remove the public footer admin link while preserving authenticated admin routes.
8. Run focused tests, then run the complete test suite.
9. Commit as `fix: localize and improve portfolio interactions`.

## Task 4: Correct Production Portfolio Content

**Files:**
- Modify through authenticated site administration as required.
- Read: `data/hyundai_application_2026.json`

1. Compare live profile and project records with the canonical content record.
2. Prepare a checklist of exact field changes, including `Jonggeol Park`, `샤이니의 빛돌기획`, `버추얼`, `론칭`, category names, hero copy, and Banana Salon status.
3. Do not change production data until local website tests pass.
4. Update authenticated admin fields, preserving existing images and links.
5. Reload Korean and English public pages and verify every corrected field visually.
6. Record any production-only data that could not be changed safely.

## Task 5: Regenerate the Portfolio PDF

**Files:**
- Create: `tools/build_portfolio_pdf.py`
- Create: `pdf/portfolio.html`
- Create: `pdf/portfolio.css`
- Create: `tests/test_portfolio_pdf.py`
- Output: `C:/Users/user/Documents/Codex/2026-09-07/new-chat/outputs/박종걸_현대자동차_포트폴리오_2026.pdf`

1. Mark the PDF edit operation exactly once before the first PDF creation command.
2. Add a failing test for expected page range, required corrected terms, forbidden typos/unsupported claims, working portfolio URL, and file size below 2 MB.
3. Recover reusable images from the source PDF and public portfolio assets into the working directory without altering originals.
4. Build the approximately 13-page HTML/CSS document from the canonical content record.
5. Generate the PDF and iterate on typography, image compression, and pagination until structural tests pass.
6. Render every page to PNG/JPEG and inspect for clipping, poor contrast, missing glyphs, broken links, or unreadable images.
7. Run the structural test again using the final output.
8. Commit generator, source, and tests as `feat: generate Hyundai-focused portfolio PDF`; do not commit the user-facing generated PDF unless repository policy calls for it.

## Task 6: Verify and Deploy the Website

**Files:**
- Verify all modified website and test files.

1. Run the complete automated test suite from a clean process.
2. Start the Flask app locally and smoke-test `/`, `/en`, and the project modal.
3. Inspect `git diff --check`, `git status --short`, and the branch diff for unrelated changes or sensitive values.
4. Push `codex/hyundai-portfolio-refresh` and integrate it into the deployment branch using a non-destructive fast-forward or reviewed merge.
5. Wait for Railway deployment and verify the public Korean and English pages.
6. If production content requires admin updates, complete and re-verify them now.

## Task 7: Update and Save the Hyundai Application

**Files:**
- Read: `data/hyundai_application_2026.json`
- Upload: `C:/Users/user/Documents/Codex/2026-09-07/new-chat/outputs/박종걸_현대자동차_포트폴리오_2026.pdf`

1. Re-open the Hyundai application and compare every target field with the canonical record.
2. Request one action-time confirmation before transmitting revised personal/professional data and uploading the PDF.
3. Replace the two self-introduction answers, update career/project fields, fill missing institutions, and normalize dates and terminology.
4. Upload the verified PDF.
5. Save without pressing the final submission button.
6. Re-read the saved fields, character counts, attachment filename, and application status.
7. Report that the application is ready for the user to review and submit, including any field that the site prevented from saving.

## Task 8: Final Evidence and Handoff

1. Run the full website tests and PDF validation one final time.
2. Confirm the deployed public URLs and the saved Hyundai application state.
3. Confirm no final submission occurred.
4. Provide the revised PDF as the sole downloadable artifact and summarize the substantive changes.

