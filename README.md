# CPSC383-A2 — Multi-Agent Systems

**Course:** CPSC 383 — Explorations in AI and Machine Learning (Winter 2026)
**Assignment:** A2 — Multi-Agent Systems, Planning, Re-Planning, Cooperation
**Team:** Camila Hernandez · Jose Lozano · Matias Campuzano · Jose Zea

---

## Prerequisites

- **Python 3.13** — required by the AEGIS package
- **macOS** — the bundled GUI client (`client/AEGIS.app`) is macOS-only

Check your Python version:
```bash
python3 --version
```

---

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd CPSC383-A2
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` at the start of your terminal prompt.

### 4. Install the AEGIS package

```bash
pip install aegis-game
```

Verify the install:
```bash
aegis --version
```

---

## Running the Simulation

Make sure your virtual environment is active (`source .venv/bin/activate`) before running any of the commands below.

### Option A — With the GUI client (recommended)

**Step 1:** Open the AEGIS desktop app:
```bash
open client/AEGIS.app
```
Or double-click `client/AEGIS.app` in Finder.

**Step 2:** In a terminal, launch the simulation with a world file:
```bash
aegis run --agent agent_mas --world worlds/challenge1_1.world
```

The GUI will display the agents moving in real time.

### Option B — Headless (terminal only)

```bash
aegis run --agent agent_mas --world worlds/challenge1_1.world --headless
```

---

## Project Structure

```
CPSC383-A2/
├── agents/
│   └── agent_mas/
│       └── main.py          # Agent logic — edit this file
├── client/
│   └── AEGIS.app            # macOS GUI client (v2.9.9)
├── config/
│   └── config.yaml          # Simulation feature flags
├── worlds/
│   ├── challenge1_1.world   # Challenge 1 test maps (solo vs. cooperative)
│   ├── challenge2_1.world   # Challenge 2 test maps (energy/charging)
│   ├── challenge3_1.world   # Challenge 3 test maps (DRONE_SCAN)
│   ├── challenge4_1.world   # Challenge 4 test maps (multi-survivor split)
│   ├── challenge5_1.world   # Challenge 5 test maps (re-planning)
│   └── example.world        # Basic example map
└── README.md
```

---

## Configuration

`config/config.yaml` controls which features are enabled. The current settings for A2:

| Feature | Value | Description |
|---|---|---|
| `ALLOW_AGENT_MESSAGES` | `true` | Agents can use `send_message` / `read_messages` |
| `ALLOW_DRONE_SCAN` | `true` | Agents can use `drone_scan` |
| `ALLOW_AGENT_PREDICTIONS` | `false` | Not needed for A2 |
| `DEFAULT_AGENT_AMOUNT` | `7` | 7 agents spawn per simulation |

---

## Testing the Challenges

Run each challenge category to verify agent behaviour:

```bash
# Challenge 1 — Solo vs. cooperative (2-agent DIG)
aegis run --agent agent_mas --world worlds/challenge1_1.world

# Challenge 2 — Energy management / charging grid
aegis run --agent agent_mas --world worlds/challenge2_1.world

# Challenge 3 — DRONE_SCAN for distant rubble
aegis run --agent agent_mas --world worlds/challenge3_1.world

# Challenge 4 — Multi-survivor split (time-limited)
aegis run --agent agent_mas --world worlds/challenge4_1.world

# Challenge 5 — Re-planning / goal chaining
aegis run --agent agent_mas --world worlds/challenge5_1.world
```

Agent logs are printed to the terminal in the format `[A<id>] Round <n> | ...` — use these to trace each agent's decisions.

---

## Deactivating the Environment

```bash
deactivate
```

---

## Troubleshooting

**`aegis: command not found`**
→ The virtual environment is not active. Run `source .venv/bin/activate` first.

**`Failed to compile main.py: variable name starts with "_"`**
→ The AEGIS sandbox uses RestrictedPython which blocks names starting with `_`. Rename any such variables.

**`send_message is not defined`**
→ Check that `ALLOW_AGENT_MESSAGES: true` is set in `config/config.yaml`.

**`AEGIS.app` won't open on macOS**
→ Go to System Settings → Privacy & Security → allow the app. Or run: `xattr -cr client/AEGIS.app`
