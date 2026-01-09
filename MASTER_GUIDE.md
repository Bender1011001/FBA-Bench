# 🦅 FBA-Bench Enterprise: The Master Guide

**Version**: 1.0 (2026-01-08)  
**Objective**: Complete ownership manual for the CEO/Deployer.

---

## 1. Executive Summary
**FBA-Bench Enterprise** is a dual-purpose platform:
1.  **Public Benchmark**: A "Consumer Reports" for LLMs, proving which models (GPT-5, Grok, etc.) can actually *do work* (run a business), not just chat.
2.  **Enterprise SaaS**: A "War Games" simulator where e-commerce companies upload their catalogs to test how AI agents pricing strategies against them.

---

## 2. Your Immediate "To-Do" List 📋

### A. Technical Security (Critical)
You mentioned `JWT_SECRET`. Here is the plain English explanation:

*   **What it is:** Think of it like the **wax seal on a royal decree**. When a user logs in, the server gives them a "Token" (ID card). It stamps this token with the `JWT_SECRET`.
*   **Why you change it:** If a hacker knows your secret (currently `CHANGE_ME_demo`), they can buy their own wax stamp and forge "Royal Decrees" saying "I am the Admin."
*   **Action:** Run this command in your terminal to get a secure one: `openssl rand -hex 32`. Copy that string into your real `.env` file on the server. Do not commit it to GitHub.

### B. Business & Legal
*   **Form an LLC:** Yes. This software simulates financial markets.
    *   *Why?* If a user loses money because they trusted your simulation and sues, the LLC protects your personal house/car. The LLC gets sued, not you.
*   **Terms of Service:** You have `TERMS_OF_SERVICE.md`. Ensure it explicitly states "For Educational/Research Use Only. Not Financial Advice."
*   **Domain:** You own `fbabench.com`. Keep it secure.

---

## 3. Codebase Atlas: "Why does this file exist?"

### 🧠 The Brain (`src/`)
This is where the actual logic lives.
*   `src/fba_bench_core/`: The physics engine of the market. It calculates sales, inventory, and profit.
*   `src/fba_bench_api/`: The "Switchboard". It enables the website and Godot app to talk to the Brain.
*   `src/agent_runners/`: The "Players". Code that connects GPT-4, Claude, etc., to our game.

### 💂 The Face (`godot_gui/`)
*   **Why Godot?** It allows for a high-performance, video-game-like visualization of the market (thousands of agents moving).
*   **Files:** `*.tscn` (Scenes), `*.gd` (Scripts).
*   **Status:** Desktop only. Premium visualization tool.

### 🌐 The Web Portal (`web/` & `docs/`)
*   `docs/` (Leaderboard): Static HTML files. **Why?** It's free to host on Cloudflare Pages and impossible to hack. This is your public face.
*   `web/` (React App): The SaaS dashboard. **Why?** Enterprise customers don't want to download a game (Godot); they want a website to log in and see graphs.

### 🏗️ The Skeleton (`infrastructure/` & root files) 
*   `Dockerfile` / `docker-compose.yml`: **The Shipping Container.** It bundles all your code, database, and dependencies into one box so it runs exactly the same on your laptop as it does on a massive Amazon server.
*   `poetry.lock` / `pyproject.toml`: **The Shopping List.** Tells the computer exactly which libraries (and versions) to install so nothing breaks.
*   `alembic/`: **The Time Machine.** Manages database changes. If you add a "User Phone Number" column, this tool tracks that change so you can undo it if needed.

---

## 4. Hosting Strategy: "Where does it live?"

### Phase 1: Reputation (The Leaderboard)
*   **Files:** `docs/*`
*   **Where:** Cloudflare Pages.
*   **Cost:** $0/mo.
*   **Goal:** Get traffic, show off "Verified Runs", build authority.

### Phase 2: Product (The SaaS)
*   **Files:** `src/` (API) + `web/` (Frontend) + Database.
*   **Where:** Cloud (Railway/AWS/DigitalOcean).
*   **Cost:** ~$50/mo.
*   **Goal:** Allow users to log in and run their own simulations.

---

## 5. Deployment Checklist
1.  [ ] **Generate Secrets:** `JWT_SECRET`, `STRIPE_KEYS` (if charging money).
2.  [ ] **Deploy Phase 1:** Push `docs/` to Cloudflare.
3.  [ ] **Audit:** Review `TERMS_OF_SERVICE.md`.
4.  [ ] **Legal:** File LLC paperwork (Delaware or Wyoming are popular for software).

