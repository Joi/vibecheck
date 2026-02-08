# Phase 1: Critical Design Fixes - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 5 most critical design bugs in vibecheck: broken template style blocks, missing accessibility for motion, card grid overflow on phones, missing mobile navigation, and orphaned bookmarks link.

**Architecture:** All changes are in Jinja2 HTML templates (`src/vibecheck/templates/`) and one Python route file (`src/vibecheck/web.py`). No database changes, no new dependencies. CSS-first solutions preferred. Each fix is independently deployable.

**Tech Stack:** FastAPI, Jinja2, Python 3.11+, CSS custom properties, vanilla JS. Tests use pytest + FastAPI TestClient.

**Beads Issues:** vibecheck-gfk, vibecheck-mwz, vibecheck-1ip, vibecheck-n50, vibecheck-ckj

---

## Prerequisite: Understand the Codebase

**Key files you'll be editing:**

| File | Purpose | Lines |
|------|---------|-------|
| `src/vibecheck/templates/base.html` | Master layout template. All pages extend this. Contains global CSS, nav, footer. | 438 lines |
| `src/vibecheck/templates/discover.html` | Tinder-like swipe UI. ~530 lines of scoped CSS + ~370 lines of JS. | 955 lines |
| `src/vibecheck/templates/bookmarks.html` | Bookmarks page. Client-side rendered from localStorage. | 120 lines |
| `src/vibecheck/web.py` | All web routes. Template rendering with context variables. | 601 lines |
| `tests/test_web_templates.py` | NEW - template rendering tests. | Create |

**Template block structure in `base.html`:**
```
<head>
  ...global CSS (lines 10-401)...
  {% block extra_head %}{% endblock %}        ← line 402
</head>
<body>
  <header>..nav..</header>
  <main>{% block content %}{% endblock %}</main>   ← line 423
  <footer>...</footer>
  {% block extra_scripts %}{% endblock %}     ← line 436
</body>
```

Available blocks: `title`, `extra_head`, `content`, `extra_scripts`.
**There is NO `extra_styles` block.** This is the P0 bug.

---

## Task 1: Fix Discover + Bookmarks Template Style Block (vibecheck-gfk)

**Priority:** P0 - This may be silently dropping ALL page-specific CSS.

**The Bug:** `discover.html` line 5 uses `{% block extra_styles %}` and `bookmarks.html` line 5 uses `{% block extra_styles %}`. But `base.html` line 402 only defines `{% block extra_head %}`. In Jinja2, when a child template overrides a block that doesn't exist in the parent, the content is **silently discarded**. This means ~520 lines of Discover CSS and ~60 lines of Bookmarks CSS may not be rendering.

**Files:**
- Investigate: `src/vibecheck/templates/base.html:402` (block definition)
- Investigate: `src/vibecheck/templates/discover.html:5` (block usage)
- Investigate: `src/vibecheck/templates/bookmarks.html:5` (block usage)
- Create: `tests/test_web_templates.py`

### Step 1: Write a test to verify the bug exists

Create the test file that checks if styles from child templates actually appear in rendered HTML.

```bash
cat > tests/test_web_templates.py << 'EOF'
"""Tests for template rendering - verifying block inheritance works."""

import pytest
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


@pytest.fixture
def jinja_env():
    """Create a Jinja2 environment pointing at the templates directory."""
    templates_dir = Path(__file__).parent.parent / "src" / "vibecheck" / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)))


class TestTemplateBlockInheritance:
    """Verify that child templates' style blocks are actually rendered."""

    def test_discover_styles_present_in_rendered_html(self, jinja_env):
        """Discover page CSS must appear in the rendered HTML output.

        Regression test for: discover.html used {% block extra_styles %}
        but base.html only defined {% block extra_head %}, silently
        dropping ~520 lines of CSS.
        """
        template = jinja_env.get_template("discover.html")
        # Render with minimal context (template variables will be undefined but
        # we only care about whether the <style> block appears in output)
        html = template.render(
            request=None,
            active_page="discover",
            items=[],
            mode="mixed",
        )
        # The discover page defines .discover-container and .swipe-card in its CSS.
        # If the block inheritance is broken, these won't appear in the output.
        assert ".discover-container" in html, (
            "Discover page CSS is missing from rendered HTML! "
            "Check that discover.html's style block name matches base.html's block definition."
        )
        assert ".swipe-card" in html, (
            "Discover page CSS (.swipe-card) missing from rendered HTML!"
        )

    def test_bookmarks_styles_present_in_rendered_html(self, jinja_env):
        """Bookmarks page CSS must appear in the rendered HTML output.

        Same block name bug as discover.html.
        """
        template = jinja_env.get_template("bookmarks.html")
        html = template.render(
            request=None,
            active_page="bookmarks",
        )
        assert ".bookmark-card" in html, (
            "Bookmarks page CSS is missing from rendered HTML! "
            "Check that bookmarks.html's style block name matches base.html's block definition."
        )
EOF
```

### Step 2: Run the test to confirm the bug

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py -v
```

**Expected:** Both tests FAIL with the assertion messages about missing CSS. This confirms the block name mismatch is real and CSS is being silently dropped.

**If tests PASS:** The bug was already fixed or Jinja2 behavior differs from expected. Skip to Step 5 (commit the tests as regression guards) and move to Task 2.

### Step 3: Fix the block name in base.html

The fix is to add an `extra_styles` block to `base.html`, OR rename the blocks in child templates. Adding the block to `base.html` is safer because other templates might also use `extra_styles`.

**Option A (preferred): Add `extra_styles` block to base.html**

In `src/vibecheck/templates/base.html`, change line 402 from:

```html
    {% block extra_head %}{% endblock %}
```

to:

```html
    {% block extra_styles %}{% endblock %}
    {% block extra_head %}{% endblock %}
```

This adds the `extra_styles` block right before `extra_head` (still inside `<head>`), so both block names work. Templates using `extra_head` for non-CSS content (e.g., meta tags, scripts) continue to work. Templates using `extra_styles` for CSS now render correctly.

### Step 4: Run tests to confirm the fix

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py -v
```

**Expected:** Both tests PASS.

### Step 5: Scan for any other templates using extra_styles

```bash
cd /Users/joi/vibecheck && grep -rn "block extra_styles\|block extra_head" src/vibecheck/templates/
```

Verify every child template's block name now matches a defined block in base.html.

### Step 6: Commit

```bash
cd /Users/joi/vibecheck
git add tests/test_web_templates.py src/vibecheck/templates/base.html
git commit -m "fix(templates): add extra_styles block to base.html - P0

discover.html and bookmarks.html used {% block extra_styles %} but
base.html only defined {% block extra_head %}. Jinja2 silently discards
child blocks that don't exist in the parent, dropping ~520 lines of
Discover CSS and ~60 lines of Bookmarks CSS.

Added {% block extra_styles %} to base.html <head> section.
Added regression tests for template block inheritance.

Closes vibecheck-gfk"
```

---

## Task 2: Add prefers-reduced-motion Support (vibecheck-mwz)

**Priority:** P1 - WCAG 2.1 AA requirement. All animations run at full speed regardless of user preferences.

**The Bug:** No `@media (prefers-reduced-motion: reduce)` anywhere in the codebase. Users who have enabled "Reduce motion" in their OS settings still get: card hover animations, swipe gesture animations, fly-off animations, spring physics, button wind-ups.

**Files:**
- Modify: `src/vibecheck/templates/base.html` (add global CSS rule)
- Modify: `src/vibecheck/templates/discover.html` (add JS awareness)
- Test: `tests/test_web_templates.py` (add presence check)

### Step 1: Write tests for reduced-motion support

Append to `tests/test_web_templates.py`:

```python
class TestAccessibility:
    """Verify accessibility requirements are met in templates."""

    def test_base_template_has_reduced_motion_css(self, jinja_env):
        """base.html must include a prefers-reduced-motion media query."""
        template = jinja_env.get_template("base.html")
        html = template.render(
            request=None,
            active_page="tools",
        )
        assert "prefers-reduced-motion" in html, (
            "base.html must include @media (prefers-reduced-motion: reduce) "
            "to respect user motion preferences (WCAG 2.1 AA)."
        )

    def test_discover_js_checks_reduced_motion(self, jinja_env):
        """Discover page JS must check prefers-reduced-motion for gesture animations."""
        template = jinja_env.get_template("discover.html")
        html = template.render(
            request=None,
            active_page="discover",
            items=[],
            mode="mixed",
        )
        assert "prefers-reduced-motion" in html, (
            "Discover page JS must check prefers-reduced-motion to disable "
            "spring animations and fly-off effects for users who prefer reduced motion."
        )
```

### Step 2: Run tests to verify they fail

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestAccessibility -v
```

**Expected:** Both tests FAIL.

### Step 3: Add global reduced-motion CSS to base.html

In `src/vibecheck/templates/base.html`, add this CSS block immediately before the closing `</style>` tag (before line 401, after the existing `@media (max-width: 768px)` block):

```css
        /* Accessibility: Respect user's motion preferences */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
            .card:hover {
                transform: none;
            }
        }
```

This goes after line 400 (closing `}` of the 768px media query) and before line 401 (`</style>`).

### Step 4: Add JS reduced-motion awareness to discover.html

In `src/vibecheck/templates/discover.html`, add this line at the top of the `<script>` block, right after `let velocityX = 0, velocityY = 0;` (after line 596):

```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
```

Then modify the `completeSwipe` function. Find the line (currently ~line 900):
```javascript
    const speed = vel > 800 ? 0.2 : vel > 400 ? 0.28 : 0.35;
```

Replace with:
```javascript
    const speed = prefersReducedMotion ? 0.01 : (vel > 800 ? 0.2 : vel > 400 ? 0.28 : 0.35);
```

And modify the swipeCard button wind-up. Find (currently ~line 882):
```javascript
    currentCard.style.transition = 'transform 0.08s ease-in';
    currentCard.style.transform = windUp;
```

Replace with:
```javascript
    if (prefersReducedMotion) {
        completeSwipe(direction);
        return;
    }
    currentCard.style.transition = 'transform 0.08s ease-in';
    currentCard.style.transform = windUp;
```

### Step 5: Run tests to verify they pass

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestAccessibility -v
```

**Expected:** Both tests PASS.

### Step 6: Commit

```bash
cd /Users/joi/vibecheck
git add src/vibecheck/templates/base.html src/vibecheck/templates/discover.html tests/test_web_templates.py
git commit -m "fix(a11y): add prefers-reduced-motion support globally

Added @media (prefers-reduced-motion: reduce) to base.html that
disables all CSS transitions and animations site-wide.

Added JS awareness in discover.html so gesture animations and
button wind-ups are skipped for users who prefer reduced motion.

WCAG 2.1 AA compliance.

Closes vibecheck-mwz"
```

---

## Task 3: Fix Card Grid Overflow on Small Phones (vibecheck-1ip)

**Priority:** P1 - Cards overflow horizontally on phones < 400px wide (iPhone SE = 375px, with 48px padding = 327px available, but grid forces 350px minimum).

**The Bug:** `base.html` line 160:
```css
grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
```
On a 375px phone with `padding: 0 1.5rem` (48px total), the available width is 327px. `minmax(350px, 1fr)` forces cards to be at least 350px, causing horizontal overflow.

**The existing 768px media query** (line 384) sets `.cards { grid-template-columns: 1fr; }` which fixes it below 768px. But 768px is too generous - the grid works fine at 640px+ with two columns.

**Files:**
- Modify: `src/vibecheck/templates/base.html:158-162` (cards grid)
- Modify: `src/vibecheck/templates/base.html:379-400` (responsive rules)
- Test: `tests/test_web_templates.py` (verify CSS values)

### Step 1: Write a test to verify the fix

Append to `tests/test_web_templates.py`:

```python
class TestResponsiveCSS:
    """Verify responsive CSS patterns in templates."""

    def test_card_grid_is_mobile_first(self, jinja_env):
        """Card grid must use 1fr default (not minmax(350px)) to prevent phone overflow."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        # The default .cards rule should NOT contain minmax(350px
        # It should be 1fr by default, with auto-fill only in a media query
        assert "minmax(350px" not in html, (
            "Card grid still uses minmax(350px, 1fr) as default. "
            "This overflows on phones < 400px wide. Use 1fr default."
        )
```

### Step 2: Run test to verify it fails

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestResponsiveCSS -v
```

**Expected:** FAIL because `minmax(350px` is still in the base CSS.

### Step 3: Fix the grid CSS in base.html

In `src/vibecheck/templates/base.html`, change the `.cards` rule (lines 158-162) from:

```css
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }
```

to:

```css
        .cards {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
        }
```

Then update the responsive section. Replace the existing `@media (max-width: 768px)` block (lines 379-400) with a mobile-first approach:

```css
        /* Responsive - mobile-first */
        @media (min-width: 640px) {
            .cards {
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            }
        }

        @media (max-width: 768px) {
            h1 {
                font-size: 1.75rem;
            }

            nav {
                gap: 1rem;
            }

            .stats {
                gap: 1rem;
            }

            .stat {
                flex: 1;
                min-width: 120px;
            }
        }
```

Note: The `min-width: 640px` query activates the multi-column grid only when there's enough space. Below 640px, cards stack in a single column. The 300px minimum (down from 350px) works better on tablets.

### Step 4: Run tests to verify they pass

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestResponsiveCSS -v
```

**Expected:** PASS.

### Step 5: Visual verification

```bash
# Start the dev server and check on a phone-width viewport
cd /Users/joi/vibecheck && python -m uvicorn vibecheck.api:app --port 8000 &
# Open http://localhost:8000 in Chrome DevTools with iPhone SE viewport (375px)
# Cards should stack in single column with no horizontal overflow
```

### Step 6: Commit

```bash
cd /Users/joi/vibecheck
git add src/vibecheck/templates/base.html tests/test_web_templates.py
git commit -m "fix(responsive): mobile-first card grid to prevent phone overflow

Changed .cards grid from minmax(350px, 1fr) to 1fr default.
Added @media (min-width: 640px) to enable multi-column grid only
when viewport is wide enough. Prevents horizontal overflow on
phones < 400px (iPhone SE = 375px - 48px padding = 327px).

Closes vibecheck-1ip"
```

---

## Task 4: Add Mobile Navigation / Hamburger Menu (vibecheck-n50)

**Priority:** P1 - 6 nav links in a flex row need ~520px. An iPhone has ~220px after the logo. Links squeeze and break.

**Current state:** `base.html` lines 87-103 define `nav` as `display: flex; gap: 2rem;`. At 768px the gap shrinks to 1rem (line 389) but the links still don't fit on phones.

**Nav links (lines 410-417):**
```html
<nav>
    <a href="/">Tools</a>
    <a href="/articles">Articles</a>
    <a href="/discover">Discover</a>
    <a href="/communities">Communities</a>
    <a href="/docs">Docs</a>
    <a href="/admin/login">Admin</a>
</nav>
```

**Files:**
- Modify: `src/vibecheck/templates/base.html` (CSS + HTML for hamburger)
- Test: `tests/test_web_templates.py`

### Step 1: Write tests

Append to `tests/test_web_templates.py`:

```python
class TestMobileNavigation:
    """Verify mobile navigation elements exist."""

    def test_hamburger_button_exists(self, jinja_env):
        """base.html must have a hamburger menu button for mobile."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "nav-toggle" in html, (
            "base.html must include a hamburger menu button (class=nav-toggle) "
            "for mobile viewports."
        )

    def test_hamburger_has_aria_attributes(self, jinja_env):
        """Hamburger button must have proper ARIA attributes."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert 'aria-expanded' in html, (
            "Hamburger button must have aria-expanded attribute."
        )
        assert 'aria-label' in html, (
            "Hamburger button must have aria-label attribute."
        )
```

### Step 2: Run tests to verify they fail

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestMobileNavigation -v
```

**Expected:** FAIL.

### Step 3: Add hamburger button HTML to base.html

In `src/vibecheck/templates/base.html`, replace the `<nav>` section (lines 410-417) with:

```html
            <button class="nav-toggle" aria-label="Toggle navigation" aria-expanded="false" onclick="this.setAttribute('aria-expanded', this.getAttribute('aria-expanded') === 'false' ? 'true' : 'false'); document.querySelector('nav').classList.toggle('open');">
                <span></span><span></span><span></span>
            </button>
            <nav>
                <a href="/" class="{% if active_page == 'tools' %}active{% endif %}">Tools</a>
                <a href="/articles" class="{% if active_page == 'articles' %}active{% endif %}">Articles</a>
                <a href="/discover" class="{% if active_page == 'discover' %}active{% endif %}">Discover</a>
                <a href="/communities" class="{% if active_page == 'communities' %}active{% endif %}">Communities</a>
                <a href="/docs" class="{% if active_page == 'docs' %}active{% endif %}">Docs</a>
                <a href="/admin/login">Admin</a>
            </nav>
```

### Step 4: Add hamburger CSS to base.html

Add these styles inside the `<style>` block in `base.html`, right after the existing `nav a:hover, nav a.active` rule (after line 103):

```css
        /* Mobile hamburger menu */
        .nav-toggle {
            display: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 0.5rem;
            z-index: 101;
            flex-direction: column;
            gap: 5px;
        }

        .nav-toggle span {
            display: block;
            width: 24px;
            height: 2px;
            background: var(--text);
            border-radius: 2px;
            transition: transform 0.3s, opacity 0.3s;
        }

        .nav-toggle[aria-expanded="true"] span:nth-child(1) {
            transform: rotate(45deg) translate(5px, 5px);
        }
        .nav-toggle[aria-expanded="true"] span:nth-child(2) {
            opacity: 0;
        }
        .nav-toggle[aria-expanded="true"] span:nth-child(3) {
            transform: rotate(-45deg) translate(5px, -5px);
        }
```

Then update the `@media (max-width: 768px)` block to add mobile nav behavior. Add these rules inside that media query:

```css
            .nav-toggle {
                display: flex;
            }

            nav {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: rgba(10, 10, 10, 0.98);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid var(--border);
                flex-direction: column;
                padding: 1rem 1.5rem;
                gap: 0;
            }

            nav.open {
                display: flex;
            }

            nav a {
                padding: 0.75rem 0;
                border-bottom: 1px solid var(--border);
                min-height: 48px;
                display: flex;
                align-items: center;
            }

            nav a:last-child {
                border-bottom: none;
            }
```

### Step 5: Add Escape key handler to close menu

Add this to the `{% block extra_scripts %}` section. Since base.html doesn't have page-specific scripts, add a minimal inline script just before `{% block extra_scripts %}` (before line 436):

```html
    <script>
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const toggle = document.querySelector('.nav-toggle');
            const nav = document.querySelector('nav');
            if (toggle && nav.classList.contains('open')) {
                nav.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
                toggle.focus();
            }
        }
    });
    </script>
```

### Step 6: Run tests

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestMobileNavigation -v
```

**Expected:** PASS.

### Step 7: Commit

```bash
cd /Users/joi/vibecheck
git add src/vibecheck/templates/base.html tests/test_web_templates.py
git commit -m "feat(nav): add mobile hamburger menu with accessibility

Added CSS-only hamburger menu that appears at 768px breakpoint.
- 48px touch targets for all nav links
- aria-expanded toggle on button
- Escape key closes menu
- Animated hamburger-to-X icon transition
- Frosted glass dropdown matches header style

Closes vibecheck-n50"
```

---

## Task 5: Add Bookmarks Link to Navigation (vibecheck-ckj)

**Priority:** P1 - Discover creates bookmarks saved to localStorage, `/bookmarks` route exists (web.py line 338), but there's no link to it anywhere in the nav.

**Current nav links:** Tools, Articles, Discover, Communities, Docs, Admin.
**Missing:** Bookmarks (with active state - web.py already passes `active_page: 'bookmarks'`).

**Files:**
- Modify: `src/vibecheck/templates/base.html` (add nav link)
- Test: `tests/test_web_templates.py`

### Step 1: Write the test

Append to `tests/test_web_templates.py`:

```python
class TestNavigation:
    """Verify navigation completeness."""

    def test_bookmarks_link_in_nav(self, jinja_env):
        """Navigation must include a link to the bookmarks page."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert '/bookmarks' in html, (
            "Navigation must include a link to /bookmarks. "
            "The route exists (web.py) and Discover saves bookmarks, "
            "but users can't find them."
        )

    def test_bookmarks_link_active_state(self, jinja_env):
        """Bookmarks nav link must have active class when on bookmarks page."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="bookmarks")
        # Find the bookmarks link and verify it has the active class
        # We check that the rendered HTML contains href="/bookmarks" near "active"
        import re
        bookmarks_link = re.search(r'<a[^>]*href="/bookmarks"[^>]*>', html)
        assert bookmarks_link is not None, "Bookmarks link not found in nav"
        assert 'active' in bookmarks_link.group(), (
            "Bookmarks link should have 'active' class when active_page='bookmarks'"
        )
```

### Step 2: Run tests to verify they fail

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestNavigation -v
```

**Expected:** FAIL.

### Step 3: Add bookmarks link to nav in base.html

In `src/vibecheck/templates/base.html`, in the `<nav>` block (where the other links are), add the Bookmarks link after Discover and before Communities:

Find:
```html
                <a href="/discover" class="{% if active_page == 'discover' %}active{% endif %}">Discover</a>
                <a href="/communities" class="{% if active_page == 'communities' %}active{% endif %}">Communities</a>
```

Replace with:
```html
                <a href="/discover" class="{% if active_page == 'discover' %}active{% endif %}">Discover</a>
                <a href="/bookmarks" class="{% if active_page == 'bookmarks' %}active{% endif %}">Bookmarks</a>
                <a href="/communities" class="{% if active_page == 'communities' %}active{% endif %}">Communities</a>
```

### Step 4: Run tests

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py::TestNavigation -v
```

**Expected:** PASS.

### Step 5: Commit

```bash
cd /Users/joi/vibecheck
git add src/vibecheck/templates/base.html tests/test_web_templates.py
git commit -m "feat(nav): add Bookmarks link to navigation

The /bookmarks route existed and Discover saves bookmarks to
localStorage, but there was no nav link to access them.

Added between Discover and Communities in the nav bar.
Includes active state (web.py already passes active_page='bookmarks').

Closes vibecheck-ckj"
```

---

## Final: Run All Tests + Verify

### Step 1: Run all template tests

```bash
cd /Users/joi/vibecheck && python -m pytest tests/test_web_templates.py -v
```

**Expected:** All tests PASS.

### Step 2: Run existing tests to check for regressions

```bash
cd /Users/joi/vibecheck && python -m pytest tests/ -v
```

### Step 3: Start dev server and visual spot-check

```bash
cd /Users/joi/vibecheck && python -m uvicorn vibecheck.api:app --port 8000
```

Check in browser:
- [ ] Homepage loads, cards display correctly
- [ ] Discover page has all its styling (swipe cards, colors, animations)
- [ ] Bookmarks page has its styling
- [ ] Bookmarks link appears in nav, highlights when active
- [ ] At 375px viewport: cards stack in single column, hamburger menu appears
- [ ] Hamburger opens/closes, Escape key closes it
- [ ] With "Reduce motion" enabled in OS: no hover animations, Discover swipes are instant

### Step 4: Final commit for test file and close Phase 1

```bash
cd /Users/joi/vibecheck
git add -A
git commit -m "test: complete Phase 1 critical design fix verification

All 5 critical design issues addressed:
- vibecheck-gfk: Template style block inheritance fixed
- vibecheck-mwz: prefers-reduced-motion support added
- vibecheck-1ip: Card grid mobile overflow fixed
- vibecheck-n50: Mobile hamburger menu added
- vibecheck-ckj: Bookmarks nav link added"
```

---

## Execution Order Summary

| # | Issue | Type | Est. | Dependency |
|---|-------|------|------|------------|
| 1 | vibecheck-gfk | P0 bug | 10 min | None (do first!) |
| 2 | vibecheck-mwz | P1 a11y | 10 min | After Task 1 (base.html) |
| 3 | vibecheck-1ip | P1 bug | 8 min | After Task 2 (base.html) |
| 4 | vibecheck-n50 | P1 feat | 15 min | After Task 3 (base.html) |
| 5 | vibecheck-ckj | P1 bug | 5 min | After Task 4 (nav HTML) |

**Total estimated time:** ~48 minutes

Tasks 1-5 are serialized because they all modify `base.html` and later tasks build on earlier changes. Task 1 must be first since it's P0 and other templates depend on the fix.
