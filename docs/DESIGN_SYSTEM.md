# Fabietti Corp. Design System
## Minimalist Dashboard Styling Guide

This design system replicates the clean, brutalist aesthetic of Fabietti Corp. for building consistent, professional dashboards.

---

## Core Philosophy

- **Brutalist & Minimal**: No rounded corners, no shadows, no gradients
- **Technical Aesthetic**: Monospace fonts, thin borders, sharp edges
- **High Contrast**: Black text on white background
- **Function Over Form**: Clean data presentation, minimal decoration
- **Consistent Spacing**: Tailwind-inspired rem-based spacing system

---

## Typography

### Font Family
```css
font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
```

### Base Settings
```css
html {
    font-size: 14px;
}

body {
    line-height: 1.5;
}
```

### Font Sizes
- **Headings (h1)**: `2.25rem` (36px), `font-weight: 600`, `line-height: 2.5rem`
- **Section Titles (h2)**: `1.125rem` (18px), `font-weight: 600`
- **Subtitle/Description**: `1rem` (16px), `color: #6b7280`
- **Body Text**: `0.875rem` (14px)
- **Small Text/Labels**: `0.75rem` (12px)
- **Tiny Text**: `0.625rem` (10px)

### Text Colors
- **Primary Text**: `#000` (pure black)
- **Secondary Text**: `#6b7280` (gray-600)
- **Tertiary Text**: `#9ca3af` (gray-400)
- **Disabled/Muted**: `#d1d5db` (gray-300)

### Text Transforms
- **Labels**: UPPERCASE, `letter-spacing: 0.025em`
- **Body**: Normal case

---

## Colors

### Background
- **Primary Background**: `#fff` (pure white)
- **Secondary Background**: `#f9fafb` (gray-50) - for table headers, hover states
- **Tertiary Background**: `#fafafa` - for chart containers

### Borders
- **Default Border**: `#e5e7eb` (gray-200)
- **Hover Border**: `#9ca3af` (gray-400)
- **Focus Border**: `#d1d5db` (gray-300)

### Accent Colors
Use sparingly, only for status indicators:

**Success/Long Signals:**
- Background: `#f0fdf4` (green-50)
- Border: `#bbf7d0` (green-200)
- Text: `#166534` (green-800)
- Solid: `#22c55e` (green-500)

**Danger/Short Signals:**
- Background: `#fef2f2` (red-50)
- Border: `#fecaca` (red-200)
- Text: `#991b1b` (red-800)
- Solid: `#ef4444` (red-500)

**Warning/Moderate:**
- Background: `#fefce8` (yellow-50)
- Border: `#fef08a` (yellow-200)
- Text: `#854d0e` (yellow-800)
- Solid: `#eab308` (yellow-500)

**Neutral:**
- Background: `#f9fafb` (gray-50)
- Border: `#e5e7eb` (gray-200)
- Text: `#6b7280` (gray-600)

---

## Borders & Shapes

### Border Width
```css
border-width: 0.85px;
```
**Always use 0.85px** - this is Fabietti Corp.'s signature thin border

### Border Radius
```css
border-radius: 0;
```
**NO ROUNDED CORNERS** - Everything is perfectly square

### Border Style
```css
border-style: solid;
```

---

## Spacing System

Use rem-based spacing following Tailwind conventions:

```css
/* Gap/Padding/Margin values */
0.125rem  /* 2px - tiny gaps */
0.375rem  /* 6px - small gaps */
0.625rem  /* 10px - default small padding */
0.9375rem /* 15px - medium gaps */
1.25rem   /* 20px - default padding for cards */
1.875rem  /* 30px - large padding */
2.5rem    /* 40px - extra large */
```

### Component Spacing
- **Card Padding**: `1.25rem` (20px)
- **Table Cell Padding**: `1.25rem` horizontal, `0.9375rem` vertical
- **Button Padding**: `0.625rem 1.25rem` (10px 20px)
- **Badge Padding**: `0.125rem 0.625rem` (2px 10px)
- **Section Gaps**: `1.25rem` to `2.5rem`

---

## Components

### Cards/Containers

```css
.card {
    background: #fff;
    border: 0.85px solid #e5e7eb;
    padding: 1.25rem;
    transition: all 0.15s;
}

.card:hover {
    border-color: #9ca3af;
}
```

### Buttons

**Primary Button:**
```css
.button-primary {
    background: #000;
    color: #fff;
    border: none;
    padding: 0.625rem 1.25rem;
    font-family: inherit;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.15s;
}

.button-primary:hover {
    background: #374151;
}
```

**Secondary Button:**
```css
.button-secondary {
    background: #fff;
    color: #000;
    border: 0.85px solid #e5e7eb;
    padding: 0.625rem 1.25rem;
    font-family: inherit;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.15s;
}

.button-secondary:hover {
    background: #f9fafb;
    border-color: #9ca3af;
}
```

### Badges

```css
.badge {
    display: inline-block;
    padding: 0.125rem 0.625rem;
    font-size: 0.75rem;
    font-weight: 500;
    border: 0.85px solid;
}

/* Status variants */
.badge-success {
    background: #f0fdf4;
    color: #166534;
    border-color: #bbf7d0;
}

.badge-danger {
    background: #fef2f2;
    color: #991b1b;
    border-color: #fecaca;
}

.badge-warning {
    background: #fefce8;
    color: #854d0e;
    border-color: #fef08a;
}

.badge-neutral {
    background: #f9fafb;
    color: #6b7280;
    border-color: #e5e7eb;
}
```

### Tables

```css
table {
    width: 100%;
    border-collapse: collapse;
}

thead {
    background: #f9fafb;
    border-bottom: 0.85px solid #e5e7eb;
}

th {
    padding: 0.9375rem 1.25rem;
    text-align: left;
    font-size: 0.75rem;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

td {
    padding: 1.25rem;
    border-bottom: 0.85px solid #e5e7eb;
    font-size: 0.875rem;
}

tbody tr:hover {
    background: #f9fafb;
}

tbody tr:last-child td {
    border-bottom: none;
}
```

### Inputs

```css
input, textarea, select {
    background: #fff;
    border: 0.85px solid #e5e7eb;
    padding: 0.625rem 1.25rem;
    font-family: inherit;
    font-size: 0.875rem;
    color: #000;
    transition: all 0.15s;
}

input:hover, textarea:hover, select:hover {
    border-color: #9ca3af;
}

input:focus, textarea:focus, select:focus {
    outline: none;
    border-color: #000;
}

::placeholder {
    color: #9ca3af;
}
```

### Modal

```css
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.25rem;
}

.modal {
    background: #fff;
    border: 0.85px solid #e5e7eb;
    max-width: 56rem;
    width: 100%;
    max-height: 80vh;
    overflow-y: auto;
}

.modal-header {
    padding: 1.25rem;
    border-bottom: 0.85px solid #e5e7eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-body {
    padding: 1.25rem;
}
```

### Progress/Loading Indicators

```css
.loading-spinner {
    width: 1.875rem;
    height: 1.875rem;
    border: 0.85px solid #e5e7eb;
    border-top-color: #000;
    border-radius: 9999px;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
```

### Status Dot

```css
.status-dot {
    width: 0.375rem;
    height: 0.375rem;
    border-radius: 9999px;
    background: #22c55e;
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
    50% { opacity: 0.5; }
}
```

---

## Layout Patterns

### Container
```css
.container {
    max-width: 80rem; /* 1280px */
    margin: 0 auto;
    padding: 2.5rem 1.25rem;
}
```

### Grid Layouts
```css
/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1.25rem;
}

/* 2 Column */
.grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.25rem;
}

/* 3 Column */
.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
}
```

### Flexbox Patterns
```css
/* Space Between */
.flex-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Centered */
.flex-center {
    display: flex;
    justify-content: center;
    align-items: center;
}

/* Column */
.flex-col {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
}
```

---

## Animations & Transitions

### Standard Transition
```css
transition: all 0.15s;
```
**Always use 0.15s** for consistency

### Hover States
- Border color change
- Background color change (subtle)
- **NO** scale transforms
- **NO** shadows

### Animation Guidelines
- Use sparingly
- Only for loading states and status indicators
- Keep timing consistent: `1s` for spin, `2s` for pulse

---

## Scrollbars

```css
::-webkit-scrollbar {
    width: 0.5rem;
    height: 0.5rem;
}

::-webkit-scrollbar-track {
    background: transparent;
}

::-webkit-scrollbar-thumb {
    background: #d1d5db;
}

::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
}
```

---

## Responsive Design

### Breakpoints
```css
/* Mobile First Approach */
@media (max-width: 640px) {
    /* Mobile styles */
    body {
        padding: 1.25rem;
    }
    
    h1 {
        font-size: 1.5rem;
        line-height: 2rem;
    }
}

@media (min-width: 768px) {
    /* Tablet styles */
}

@media (min-width: 1024px) {
    /* Desktop styles */
}
```

### Mobile Adjustments
- Reduce padding: `2.5rem` → `1.25rem`
- Reduce heading sizes by 25-30%
- Stack grids to single column
- Reduce table padding
- Ensure touch-friendly hit areas (min 44px)

---

## Don'ts (Critical Rules)

1. ❌ **NO border-radius** (except for circles: dots, spinners)
2. ❌ **NO box-shadows**
3. ❌ **NO gradients**
4. ❌ **NO custom fonts** (use system monospace)
5. ❌ **NO animations** (except loading/status)
6. ❌ **NO transform effects** (except rotate for spinners)
7. ❌ **NO background images**
8. ❌ **NO opacity effects** (except for disabled states)

---

## Quick Reference Template

```css
/* Base Setup */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html {
    font-size: 14px;
}

body {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    background: #fff;
    color: #000;
    line-height: 1.5;
}

/* Universal Border */
* {
    border-width: 0.85px;
    border-color: #e5e7eb;
}

/* Universal Transition */
button, a, input, select, textarea, .card, .badge {
    transition: all 0.15s;
}
```

---

## Usage Instructions for Claude Code

When building a dashboard with this design system:

1. **Start with the base setup** (fonts, colors, spacing)
2. **Use exact border width**: Always `0.85px solid #e5e7eb`
3. **No rounded corners**: All `border-radius: 0` (except circles)
4. **Monospace font**: Use the specified font-family for everything
5. **Follow spacing system**: Use the rem values specified
6. **Keep it minimal**: When in doubt, remove decoration
7. **Black buttons**: Primary actions are always black background, white text
8. **Thin borders everywhere**: Tables, cards, inputs, badges - all use 0.85px
9. **Gray scale first**: Only add color for status (red/green/yellow)
10. **Hover = darker border**: Most hover states just darken the border

---

## Example Component Implementations

### Stat Card
```html
<div class="stat-card">
    <div class="stat-label">Active Users</div>
    <div class="stat-value">1,247</div>
</div>
```

```css
.stat-card {
    background: #fff;
    border: 0.85px solid #e5e7eb;
    padding: 1.25rem;
    transition: all 0.15s;
}

.stat-card:hover {
    border-color: #9ca3af;
}

.stat-label {
    font-size: 0.75rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.025em;
    margin-bottom: 0.625rem;
}

.stat-value {
    font-size: 1.875rem;
    font-weight: 600;
    line-height: 2.25rem;
}
```

### Signal Badge
```html
<span class="signal-badge signal-short-strong">SHORT</span>
```

```css
.signal-badge {
    display: inline-block;
    padding: 0.125rem 0.625rem;
    font-size: 0.75rem;
    font-weight: 500;
    border: 0.85px solid;
}

.signal-short-strong {
    background: #fef2f2;
    color: #991b1b;
    border-color: #fecaca;
}
```

This design system ensures all dashboards in your project maintain the same clean, brutalist, Fabietti Corp.-inspired aesthetic.
