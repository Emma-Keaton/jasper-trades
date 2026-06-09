---
name: detailed-ui-wireframing
description: Creating implementation-ready UI wireframes with ASCII mockups, component specs, and design system documentation
source: auto-skill
extracted_at: '2026-05-30T20:52:15.421Z'
---

# Detailed UI Wireframing Method

When creating wireframes for a web application, follow this systematic approach to produce implementation-ready specifications:

## Step 1: Understand the Application Architecture

Before wireframing, gather context from:
- **Project plan/documentation** - Features, user flows, technical constraints
- **Existing codebase** - Current frontend structure, routing, components
- **Backend API structure** - Available endpoints, data models
- **Technology stack** - Framework choices (React, Vue, etc.), UI libraries

## Step 2: Define the Design System First

Create a foundational design system that all screens will follow:

### Colors
```yaml
Primary: #3B82F6 (Blue-500)
Secondary: #10B981 (Emerald-500)
Danger: #EF4444 (Red-500)
Warning: #F59E0B (Amber-500)
Background: #0F172A (Slate-900)
Surface: #1E293B (Slate-800)
Text Primary: #F8FAFC (Slate-50)
Text Secondary: #94A3B8 (Slate-400)
Border: #475569 (Slate-600)
```

### Typography
```yaml
Headings: Inter, sans-serif
Body: Inter, sans-serif
Mono: JetBrains Mono, monospace (for numbers, code)
```

### Spacing Scale
```yaml
xs: 4px, sm: 8px, md: 16px, lg: 24px, xl: 32px, 2xl: 48px
```

### Border Radius
```yaml
sm: 4px, md: 8px, lg: 12px, xl: 16px, full: 9999px
```

## Step 3: Define Shell Layout

Create the persistent layout that wraps all screens:

**Header:** Fixed top, 64px height, contains logo, search, user menu
**Sidebar:** Fixed left, collapsible (64px/240px), navigation items
**Status Bar:** Fixed bottom, 32px height, system status indicators
**Main Content Area:** Responsive, padded, scrolls independently

Draw ASCII mockup showing the full layout structure with dimensions.

## Step 4: Wireframe Each Screen

For each screen/route in the application:

### 4.1 Define Screen Purpose
One sentence describing what the screen does and its primary user action.

### 4.2 Create ASCII Mockup
Draw detailed ASCII representation showing:
- **Container boundaries** (use ┌─│┐└┘ characters)
- **Section divisions** with labeled headers
- **UI element placement** (buttons, inputs, tables, charts)
- **Sample data** to show content structure
- **Interactive elements** clearly marked

**ASCII Conventions:**
- `[Button]` - Clickable buttons
- `[Input     ]` - Text inputs
- `[Dropdown ▼]` - Select dropdowns
- `[☐]` - Checkboxes
- `( )` - Radio buttons
- `[████░░]` - Progress bars (filled/empty)
- `↗ ↘ →` - Trend indicators
- `🟢 🟡 🔴` - Status indicators

### 4.3 Write Component Specifications

For each major component on the screen, document:

```yaml
Container:
  - Background: {color hex/name}
  - Border-radius: {sm/md/lg/xl}
  - Padding: {value}
  - Margin: {value}
  - Border: {color and width}

Element Types:
  - Labels: {font size, weight, color}
  - Values: {font size, font family, color}
  - Icons: {size, color}

States:
  - Hover: {background/color changes}
  - Active: {styling when selected}
  - Disabled: {opacity, color changes}

Layout:
  - Grid columns: {number and behavior}
  - Flex directions: {row/column, wrap}
  - Responsive breakpoints: {behavior at sizes}
```

### 4.4 Document Interactions

For complex components:
- Dropdown behavior (trigger, animation, close behavior)
- Table interactions (sorting, filtering, pagination)
- Chart interactions (tooltips, zoom, timeframe selection)
- Modal/overlay behavior (trigger, dismissal, animations)

## Step 5: Document Responsive Behavior

For each screen, specify:

### Tablet (768px - 1024px)
```yaml
- Sidebar: Collapsed by default
- Grid layouts: 2 columns instead of 4
- Tables: Horizontal scroll
- Charts: Reduced height
```

### Mobile (320px - 767px)
```yaml
- Layout: Single column, stacked
- Navigation: Bottom tab bar
- Header: Simplified hamburger menu
- Tables: Card-based layout (one row = one card)
- Touch targets: 48px minimum
```

## Step 6: Document Interaction Patterns

Create a reference section for common patterns:

### Dropdowns
- Trigger, animation duration, positioning, close behavior

### Toast Notifications
- Position, duration, types, stacking behavior

### Loading States
- Skeleton screens, spinners, progress bars, shimmer effects

### Confirmation Dialogs
- Overlay, modal structure, button placement

## Step 7: Add Accessibility Requirements

Document:
- **Keyboard navigation:** Tab order, focus indicators, shortcuts
- **Screen reader support:** ARIA labels, live regions, heading hierarchy
- **Color contrast:** Minimum ratios (4.5:1 normal, 3:1 large text)
- **Non-color indicators:** Icons/text in addition to color

## Wireframe File Structure

Organize the wireframe document as:

```markdown
# Project Name - UI Wireframes

## Table of Contents
1. Layout & Navigation
2. Dashboard
3. Screen Name
...

## Design System
[Colors, typography, spacing, etc.]

## 1. Layout & Navigation
[Shell layout ASCII + specs]

## 2. Dashboard
[Purpose]
[ASCII mockup]
[Component specs]

## 3. Screen Name
...

## Mobile Responsive Breakpoints
[Tablet, mobile specs]

## Interaction Patterns
[Dropdowns, toasts, loading, etc.]

## Accessibility Requirements
[Keyboard, screen reader, contrast]
```

## Key Principles

- **Be specific:** Hex colors, pixel dimensions, font sizes
- **Be consistent:** Use design system tokens throughout
- **Show data:** Include realistic sample content in mockups
- **Show states:** Normal, hover, active, disabled, loading
- **Component-minded:** Structure specs so they map to React components
- **Implementation-ready:** Developer should not need to guess dimensions or colors

## Example Output

A complete wireframe document for a trading app included:
- 9 fully-wireframed screens (Dashboard, Agents, Signals, Copy Trading, Backtest, Alpha Zoo, Portfolio, Settings, Layout)
- 200+ lines of design system documentation
- ASCII mockups for each screen with realistic data
- Component specifications for 30+ unique components
- Responsive behavior for tablet and mobile
- 10+ interaction patterns documented
- Accessibility requirements section

This level of detail enables a frontend developer to build high-fidelity prototypes directly from the wireframe document without needing design tools.