# Demo Video Script (~90 seconds)

Record your terminal (QuickTime/OBS/Loom all work) running through this.
Talking points are in *italics* — read them in your own words.

**1. Intro (10s)**
*"This is an FNOL claims processing agent — it extracts fields from loss
notice documents, flags missing or inconsistent data, and routes each
claim with an explanation."*

**2. Show the project structure (10s)**
```bash
ls
cat sample_docs/fnol_01_fast_track.txt
```
*"Here's a sample FNOL doc — a labeled auto claim form. I've got 8 of
these covering every routing rule plus a couple of edge cases."*

**3. Run one document (20s)**
```bash
python main.py sample_docs/fnol_01_fast_track.txt
```
*"It extracts all the fields into categories, finds no missing fields, and
routes this one to Fast-Track since the damage is under $25,000."*

**4. Run the precedence edge case (20s)**
```bash
python main.py sample_docs/fnol_06_multiple_flags.txt
```
*"This document actually qualifies for three different routes at once —
it's missing fields, has fraud keywords, and is an injury claim. Missing
data wins, so it correctly goes to Manual Review — that's the priority
order I built into the router."*

**5. Batch mode (15s)**
```bash
python main.py --batch sample_docs/
```
*"And here's the whole sample set processed at once, with a one-line
summary at the end showing every route matches what I'd expect."*

**6. Tests (10s)**
```bash
pytest -v
```
*"23 tests covering extraction, validation, and every routing rule,
including the precedence edge case — all passing."*

**7. Close (5s)**
*"Full write-up of the design decisions and assumptions is in the README.
Thanks for watching!"*
