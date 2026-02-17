# Godot Observer UI Design System

## Objective
Transform the Godot GUI into an observer-first simulation theater that is legible, cinematic, and replayable without backend integration changes.

## UX Audit (What Was Blocking Storytelling)
- Visual hierarchy was flat: nearly all controls looked the same, so key moments did not stand out.
- Typography was too small/inconsistent for recording and high-DPI screens.
- Styling was scattered (scene overrides + ad-hoc script styling), making polish hard to maintain.
- Simulation view had strong live visuals, but replay controls were missing; reviewers could not scrub narrative beats.
- Event narration existed but lacked explicit signaling for strategy/memory/attack outcomes.

## Visual Directions Considered
1. **Command Deck Neon (Chosen)**
- Deep navy surfaces, cyan/green signal accents, amber warning, rose error.
- Emphasis on cinematic observer mood and high contrast in recordings.
- Supports animated callouts and HUD overlays cleanly.

2. **Broadcast Scoreboard**
- Brighter neutral background with card-heavy sports-broadcast styling.
- Strong table readability, weaker atmosphere for cinematic warehouse playback.

### Why Direction 1 Was Selected
- Better fit for end-to-end “watchable story” runs.
- Stronger legibility against animated warehouse visuals.
- Integrates naturally with cinematic mode and event callouts.

## Implemented System

### Foundation
- Added centralized design/autoscaling autoload: `godot_gui/autoload/UiDesignSystem.gd`.
- Added shared theme: `godot_gui/themes/ObserverTheme.tres`.
- Enabled project-level theme + scaling hooks in `godot_gui/project.godot`.

### Tokens
- Spacing scale (`SPACE_1..SPACE_5`) and type scale (`TYPE_LABEL..TYPE_TITLE`) in `UiDesignSystem`.
- Color tokens in `UiDesignSystem` (`COLOR_BG`, `COLOR_ACCENT`, `COLOR_GOOD`, `COLOR_WARN`, `COLOR_DANGER`).
- Theme variants in `ObserverTheme`:
  - `ObserverTitle`
  - `ObserverSection`
  - `ObserverMuted`
  - `ObserverValue`
  - `ObserverPanel`
  - `ObserverTopBar`
  - `ObserverInsetPanel`
  - `ObserverChip`

### Reusable Components
- `godot_gui/scenes/components/MetricCard.tscn` + `.gd`
- `godot_gui/scenes/components/StoryFeedPanel.tscn` + `.gd`
- `godot_gui/scenes/components/ReplayControlsBar.tscn` + `.gd`

### Interaction Model
- **Live Mode**: real-time updates, event narration, camera emphasis, metric cards.
- **Replay Mode**: scrub timeline, play/pause, speed control, go-live handoff.
- **Cinematic Mode (`C`)**: collapses control chrome, keeps observer HUD/event panel.

### Motion Layer
- Main shell view transitions use fade + horizontal glide.
- Cinematic camera auto-focus reacts to inventory/revenue events.
- Event callouts and package-path animations use lightweight tweens only.

## Milestones (Implemented)
1. **Foundation**: centralized tokens, scaling, project-level theme.
2. **Components**: metric cards, story feed panel, replay transport bar.
3. **Cinematic Layer**: observer HUD, event emphasis, camera focus behavior.
4. **Polish**: shell transitions, recording layout toggle, docs + runbook updates.

## Key Files Changed
- `godot_gui/scenes/main/Main.tscn`
- `godot_gui/scenes/main/Main.gd`
- `godot_gui/scenes/simulation/SimulationViewer.tscn`
- `godot_gui/scenes/simulation/SimulationViewer.gd`
- `godot_gui/scenes/simulation/PerformanceChart.gd`
- `godot_gui/scenes/simulation/AgentInspector.gd`
- `godot_gui/scenes/leaderboard/Leaderboard.gd`
- `godot_gui/scenes/sandbox/Sandbox.gd`

## Asset Policy
Current pass uses only engine-generated primitives and system fonts (no third-party art dependencies).

### Placeholder/Final Asset Plan (Future)
- Font upgrade: Inter Tight or Sora (SIL Open Font License).
- Icon set: Tabler Icons (MIT).
- Subtle background texture/noise: procedural or self-generated PNGs.

## Before/After Capture Notes
- **Before**: flat dark panel style, no replay scrubber, small labels.
- **After**: themed shell, metric cards, story feed panels, replay bar, recording layout toggle, stronger motion transitions.

## Known Limitations
- Replay currently re-renders from buffered tick payloads, not a dedicated persisted replay file.
- Event prominence depends on upstream event payload richness.
- Godot runtime execution was not available in this environment; validation was static/code-level.

## Next Improvements
1. Add event-marker ticks directly on replay scrubber.
2. Add comparative multi-series chart (revenue vs profit vs inventory pressure).
3. Add scene-level preset profiles (`Presentation`, `Analyst`, `Debug`).
