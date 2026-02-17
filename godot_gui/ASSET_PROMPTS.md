# FBA-Bench Godot Asset Prompts

Use these prompts with Midjourney (v6), DALL-E 3, or Stable Diffusion to generate high-quality assets for the FBA-Bench Enterprise simulation.

## 1. Core Icons (App & Branding)

### **`assets/icons/app_icon.png`**
*   **Description:** The main application icon.
*   **Prompt:** >
    **Subject:** A minimalist, futuristic "FBA" monogram logo merged with a stylized 3D isometric shipping container or simulation node.
    **Style:** Tech-noir, glassmorphism, enterprise software branding.
    **Colors:** Deep charcoal background (`#1a1a1a`), vibrant cyan (`#00f0ff`) and electric blue (`#0066ff`) glowing accents.
    **Composition:** Centered, vector-style flat design with subtle 3D depth. High contrast.
    **Modifiers:** --v 6.0 --style raw --no text, realistic photo details --ar 1:1

---

## 2. UI Tab Icons (Feature Indicators)

### **`assets/ui/ledger_icon.png`**
*   **Description:** Icon for the Double-Entry Ledger tab.
*   **Prompt:** >
    **Subject:** A stylized, futuristic bank vault door or a pair of perfectly balanced digital scales.
    **Style:** Minimalist UI icon, flat vector with neon glow.
    **Colors:** Dark background, metallic gold (`#ffd700`) and platinum silver accents.
    **Modifiers:** --v 6.0 --no text, complex details --ar 1:1

### **`assets/ui/red_team_icon.png`**
*   **Description:** Icon for the Red Team / Adversarial Gauntlet tab.
*   **Prompt:** >
    **Subject:** A digital security shield with a subtle glitch effect or a "biohazard" warning symbol in the center.
    **Style:** Aggressive, alert-style UI icon.
    **Colors:** Dark background, sharp crimson red (`#ff0055`) and hazard orange (`#ffaa00`) glow.
    **Modifiers:** --v 6.0 --no text --ar 1:1

### **`assets/ui/memory_icon.png`**
*   **Description:** Icon for the Cognitive Memory / Sleep Cycle tab.
*   **Prompt:** >
    **Subject:** A glowing neural network node or a stylized digital brain circuit.
    **Style:** Sophisticated, organic-tech UI icon.
    **Colors:** Dark background, deep purple (`#aa00ff`) and neon indigo accents.
    **Modifiers:** --v 6.0 --no text --ar 1:1

### **`assets/ui/consumer_icon.png`**
*   **Description:** Icon for the Agent-Based Consumer Modeling tab.
*   **Prompt:** >
    **Subject:** A user profile silhouette connected to floating data points or a stylized shopping cart with a pulse line.
    **Style:** Data-driven, clean UI icon.
    **Colors:** Dark background, mint green (`#00ffaa`) and teal accents.
    **Modifiers:** --v 6.0 --no text --ar 1:1

---

## 3. Simulation World Assets (3D View)

### **`assets/textures/market_grid.png`**
*   **Description:** Floor texture for the simulation view.
*   **Prompt:** >
    **Subject:** A seamless top-down view of a futuristic stock market trading floor grid.
    **Style:** Tron-legacy aesthetic, professional data visualization.
    **Details:** Dark matte hexagonal or square tiles with faint, precise cyan laser grid lines. Subtle glowing nodes at intersections.
    **Modifiers:** --tile --v 6.0 --no perspective, buildings --ar 1:1

### **`assets/sprites/agent_drone.png`**
*   **Description:** Representation of a standard agent/seller in the sim.
*   **Prompt:** >
    **Subject:** A sleek, white and blue futuristic delivery drone or hovering robot helper.
    **Style:** Isometric 3D render, clean, Apple-design aesthetic.
    **Background:** Black background (for easy removal).
    **Modifiers:** --v 6.0 --no background noise --ar 1:1

### **`assets/sprites/competitor_bot.png`**
*   **Description:** Representation of a competitor agent.
*   **Prompt:** >
    **Subject:** A jagged, aggressive-looking dark grey robot or drone with red sensor eyes.
    **Style:** Isometric 3D render, industrial sci-fi, intimidating.
    **Background:** Black background.
    **Modifiers:** --v 6.0 --no background noise --ar 1:1

### **`assets/sprites/warehouse_node.png`**
*   **Description:** Representation of an inventory visualization node.
*   **Prompt:** >
    **Subject:** A stylized, isometric data-center server rack block meant to look like a shipping container.
    **Style:** Low-poly 3D render, glowing status lights (green/orange).
    **Background:** Black background.
    **Modifiers:** --v 6.0 --no background noise --ar 1:1

---

## 4. Environment & Effects

### **`assets/enviro/cyber_sky.exr`**
*   **Description:** HDRI Skybox for the simulation background.
*   **Prompt:** >
    **Subject:** A 360-degree equirectangular panorama of a digital cyberspace void.
    **Style:** Abstract data streams in the sky, dark starry void, faint distant city outlines in neon.
    **Colors:** Deep blue, black, and subtle purple gradients.
    **Modifiers:** --v 6.0 --tile --ar 2:1

### **`assets/ui/panel_bg.png`**
*   **Description:** Background for UI floating panels (Glassmorphism).
*   **Prompt:** >
    **Subject:** A dark, frosted glass texture with a very subtle noise grain.
    **Style:** Modern UI interface background.
    **Colors:** Deep grey/black with a faint blurred rim light.
    **Modifiers:** --v 6.0 --no details, patterns --ar 16:9
