# Godot GUI Asset Prompts (Expert V2)

These prompts are optimized for Midjourney v6 or DALL-E 3 to generate high-quality, game-ready assets.

## Core Sprites (Top-Down 2D)

### 1. Agent Drone (Player)
**Goal:** A clean, high-tech, friendly-but-functional drone. Needs to look good when rotated.
**Prompt:**
> 2d game asset, top-down view of a futuristic logistics drone, circular chassis with glowing blue core, sleek white and grey plating, industrial design, clean vector style, soft ambient occlusion, isolated on black background --no shadow, perspective, 3d render

### 2. Competitor Bot (Enemy)
**Goal:** Aggressive, angular, distinct from the player. "The Red Team".
**Prompt:**
> 2d game asset, top-down view of a hostile security bot, triangular chassis, aggressive red branding, dark metal plating with exposed wiring, tactical design, sharp angles, warning lights, clean vector style, isolated on black background --no shadow, perspective, 3d render

### 3. Warehouse Floor (Texture)
**Goal:** A seamless, subtle tech grid for the background. Dark mode aesthetic.
**Prompt:**
> seamless pattern, top-down view of high-tech warehouse floor, dark hexagonal grid tiles, subtle blue emissive lines, brushed metal texture, low contrast, dark blue-grey palette, cyberpunk architecture style --tile --v 6.0

## FX & Polish Assets

### 4. Scanner Beam (Sprite)
**Goal:** A soft, conical gradient to use for the "vision cone" of agents.
**Prompt:**
> white gradient cone shape on black background, soft edges, fading to transparent, light beam effect, alpha mask style --no noise, texture, detail

### 5. Glow/Shadow Blob (Sprite)
**Goal:** A soft, radial gradient to place *under* units to ground them.
**Prompt:**
> soft black radial gradient circle on white background, ambient occlusion shadow blob, smooth fade to transparent edges --no noise

## Integration Tips
1.  **Scale:** Ensure sprites are roughly square (e.g., 256x256).
2.  **Alpha:** Remove black backgrounds to create transparent PNGs.
3.  **Rotation:** By default, Godot sprites face RIGHT (0 degrees). Ensure the "front" of your drone/bot points to the RIGHT in the image file.
