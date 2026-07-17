# ASP Guide (Explain Like I'm Five, Grandpa Edition)

Listen here, rookie. The problem is simple: your AI agents have the memory of a goldfish. Yesterday you spent half a day explaining your architecture, and today you open a fresh chat and it starts building everything from scratch while asking stupid questions.

**ASP (Agent Session Protocol)** is just a damn notebook. A hard, fireproof notebook that sits in the `.asp/` folder right inside your project.

The agent wakes up, opens this notebook (`STATE.md` and `BOARD.md`), sees exactly which line of code it left off at yesterday, and gets back to work. No whining, no repeating yourself.

## How to fire it up (for the specially gifted)

**Step 1. Beat the rules into the agent's skull (Once per machine)**
You have agents living on your machine (Claude, Gemini, Cursor, whatever). Download ASP and run the script. It writes a global rule into their brains telling them to always read the notebook.
```bash
git clone https://github.com/vacterro/asp
cd asp
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**Step 2. Start it in your project**
Open your terminal or editor in your project folder, call the agent, and tell it straight to its face:
> `asp SET` 

It will grumble, create an `.asp/` folder, and start writing a list of tasks (tickets). Bam, the patient is on the hook.

**Step 3. Make it work**
- You type `/asp continue` — the agent shuts up, reads what it planned, picks the top task, and does it.
- The next day, you open a completely blank chat, type `/asp continue` again — it picks up the old notes from the folder and resumes exactly where it stopped.

And if you need it to permanently remember that you only use Tabs and not Spaces — toss a text file into `.asp/KNOWLEDGE/`. It will read it like the Ten Commandments before every single task.

**Step 4. Evolution (for lazy asses)**
Board empty? Bored? Type `/asp`.
Agent won't whine 'how can I help?'. It jumps to **HUNT**, seeks bugs. No bugs? Hits **ADD** and builds a new feature by strict rules: zero hardcoding, bulletproof persistence, user controls everything. You just sit, smoke, watch the app grow muscles itself.

Any questions? No? Then get back to work.
