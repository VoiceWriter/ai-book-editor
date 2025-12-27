# AI Book Editor - Manual Test Plan

A real-world test journey: Starting a book about dog training for first-time owners.

---

## Phase 1: Day 1 - Getting Started

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1.1 | Fork/create repo from ai-book-editor template | Repo created with workflows |
| 1.2 | Add ANTHROPIC_API_KEY in Settings → Secrets → Actions | Secret saved |
| 1.3 | Create issue "Voice memo: My book idea" with raw transcript, add `voice_transcription` label | Workflow triggers |
| 1.4 | Wait 2-3 minutes for AI response | AI welcomes you, asks about your book vision |
| 1.5 | Reply: "This is a book about dog training for first-time owners" | AI acknowledges, asks follow-up |
| 1.6 | Reply: "My audience is busy professionals who just got a puppy" | AI confirms understanding |
| 1.7 | Reply: "I want a conversational tone like talking to a friend" | AI responds warmly, gives first feedback |

---

## Phase 2: First Week - Capturing Ideas

| Step | Action | Expected Result |
|------|--------|-----------------|
| 2.1 | Submit voice memo with filler words: "um so the first thing people need to understand is that dogs don't speak english right..." | AI cleans filler words, preserves meaning |
| 2.2 | Check cleaned transcript | No more "um" "so" "like" but voice preserved |
| 2.3 | Submit memo about different topic (crate training) | AI notes this could be separate chapter |
| 2.4 | Submit third memo referencing the first | AI notices connection between memos |
| 2.5 | Reply: "@margot-ai-editor how many chapters do I have so far?" | AI reports ~2-3 potential chapters |
| 2.6 | Reply: "@margot-ai-editor create PR for the introduction" | AI creates PR with polished intro |

---

## Phase 3: Building Chapters

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.1 | Merge the intro PR | Content now in chapters/ folder |
| 3.2 | Submit memo about common puppy mistakes | AI suggests chapter 2 or 3 |
| 3.3 | Reply: "@margot-ai-editor put this in chapter-02-mistakes.md" | AI confirms placement |
| 3.4 | Reply: "@margot-ai-editor create PR" | PR created targeting specified file |
| 3.5 | Check PR diff | Clean markdown with headings |
| 3.6 | Merge PR and submit new memo | AI references existing chapters |

---

## Phase 4: Working With Your Editor

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.1 | Reply: "@margot-ai-editor what's working in my writing so far?" | Encouraging overview of strengths |
| 4.2 | Reply: "@margot-ai-editor what should I focus on?" | 2-3 specific suggestions |
| 4.3 | Reply: "@margot-ai-editor I'm feeling stuck on chapter 3" | AI asks discovery questions |
| 4.4 | Reply: "I don't know how to transition from training to bonding" | AI suggests specific approaches |
| 4.5 | Submit messy stream-of-consciousness memo | AI finds core message, suggests structure |

---

## Phase 5: Switching Personas

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.1 | Reply: "@margot-ai-editor use sage for this next piece" | AI confirms switch to Sage |
| 5.2 | Submit vulnerable content about personal dog story | Sage responds gently |
| 5.3 | Reply: "@margot-ai-editor I need brutal honesty now" | AI switches to critical mode |
| 5.4 | Add label `persona:the-axe` to new issue | The Axe tears into prose ruthlessly |
| 5.5 | Reply: "@margot-ai-editor list all personas" | Shows 8 personas with descriptions |

---

## Phase 6: Ready to Revise

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.1 | Reply: "@margot-ai-editor I'm done drafting - ready for real feedback" | AI acknowledges phase transition |
| 6.2 | Submit content that was previously praised | AI now points out overlooked issues |
| 6.3 | Reply: "@margot-ai-editor review chapter 1 again" | Structural feedback: pacing, flow, arc |
| 6.4 | Reply: "@margot-ai-editor is my chapter order right?" | AI suggests reordering if needed |
| 6.5 | Push branch with edits to chapters/ | AI reviews PR with line comments |

---

## Phase 7: Polish Phase

| Step | Action | Expected Result |
|------|--------|-----------------|
| 7.1 | Reply: "@margot-ai-editor let's polish chapter 1" | AI shifts to line-editing mode |
| 7.2 | Submit polished content | Feedback on word choice, rhythm, clarity |
| 7.3 | Reply: "@margot-ai-editor check for passive voice" | AI identifies passive constructions |
| 7.4 | Reply: "@margot-ai-editor is this sentence too long?" | AI analyzes and suggests alternatives |
| 7.5 | Push PR modifying chapter 1 | Text Statistics posts readability scores |

---

## Phase 8: Whole Book Review

| Step | Action | Expected Result |
|------|--------|-----------------|
| 8.1 | Create issue with `whole-book` label | AI reads all chapters |
| 8.2 | Wait 5+ minutes for analysis | Cross-chapter analysis posted |
| 8.3 | Check for theme consistency | Recurring themes identified |
| 8.4 | Check for repetition detection | Repeated content flagged |
| 8.5 | Check for promise/payoff tracking | Unresolved setups noted |

---

## Phase 9: Ask the Editor

| Step | Action | Expected Result |
|------|--------|-----------------|
| 9.1 | Create issue with `ask-editor` label: "How long should chapters be?" | Thoughtful answer |
| 9.2 | Create issue: "Should I include personal stories?" | Context-aware response |
| 9.3 | Create issue: "Is my title working?" | Honest assessment with alternatives |
| 9.4 | Close the issue after answer | Knowledge extracted for future |

---

## Phase 10: Text Statistics

| Step | Action | Expected Result |
|------|--------|-----------------|
| 10.1 | Push PR adding new chapter | Text stats comment on PR |
| 10.2 | Check readability score | Flesch score and grade level |
| 10.3 | Check corpus comparison | "New vs Existing vs After Adding" table |
| 10.4 | Add chapter with lots of passive voice | Impact warning about passive increase |
| 10.5 | Run workflow manually via Actions | Analyze all chapters or specific file |

---

## Phase 11: Real Scenarios

### Writer's Block
| Step | Action | Expected Result |
|------|--------|-----------------|
| 11.1 | Submit: "I've been staring at a blank page for an hour" | AI asks questions, doesn't lecture |
| 11.2 | Reply: "I just don't know what comes next" | AI suggests freewriting or prompts |

### Sensitive Content
| Step | Action | Expected Result |
|------|--------|-----------------|
| 11.3 | Submit personal story about losing a pet | Appropriate sensitivity |
| 11.4 | Add label: be gentle | Tone adjusts accordingly |

### Disagreement
| Step | Action | Expected Result |
|------|--------|-----------------|
| 11.5 | Reply: "I disagree - I want to keep that paragraph" | AI respects choice, explains trade-offs |
| 11.6 | Reply: "Why do you keep suggesting I cut this?" | AI explains without being defensive |

---

## Phase 12: Long-Term Learning

| Step | Action | Expected Result |
|------|--------|-----------------|
| 12.1 | After 5+ interactions, check `.ai-context/knowledge.jsonl` | Q&A pairs from conversations |
| 12.2 | Check if AI remembers target audience | References without reminders |
| 12.3 | Check terminology consistency | Uses your preferred terms |
| 12.4 | Submit memo using corrected term | AI uses your preferred term now |

---

## Phase 13: Edge Cases

| Step | Action | Expected Result |
|------|--------|-----------------|
| 13.1 | Submit issue with empty body | Helpful error/prompt |
| 13.2 | Submit 10,000+ word transcript | Processes without timeout |
| 13.3 | Create 3 issues rapidly | All process without conflicts |
| 13.4 | Mention @margot-ai-editor in joke comment | Responds appropriately |
| 13.5 | Submit code snippet in transcript | Handles non-prose gracefully |

---

## Scoring Summary

| Phase | Tests | Passed | Failed | Notes |
|-------|-------|--------|--------|-------|
| 1. Day 1: Getting Started | 7 | | | |
| 2. First Week: Capturing Ideas | 6 | | | |
| 3. Building Chapters | 6 | | | |
| 4. Working With Your Editor | 5 | | | |
| 5. Switching Personas | 5 | | | |
| 6. Ready to Revise | 5 | | | |
| 7. Polish Phase | 5 | | | |
| 8. Whole Book Review | 5 | | | |
| 9. Ask the Editor | 4 | | | |
| 10. Text Statistics | 5 | | | |
| 11. Real Scenarios | 6 | | | |
| 12. Long-Term Learning | 4 | | | |
| 13. Edge Cases | 5 | | | |
| **TOTAL** | **68** | | | |

---

## Sample Test Content

### First Voice Memo (Day 1)
```
okay so this is me just talking through it dont clean it up yet this is
for you as the editor to get the shape of it in your head i think the
book should be about 300 pages maybe a little more maybe less but roughly
that and split into 10 chapters that feels right not too many not too few
enough room to breathe and go deep and chapter 1 is really about orientation
its for the new dog owner who is overwhelmed and excited and tired already
and doesnt know where to start...
```

### Messy Stream-of-Consciousness (Phase 4)
```
so the thing about bonding with your dog is like its not just treats
right its about being present and like when youre on your phone and
the dogs just sitting there waiting thats not bonding thats coexisting
and I want people to understand that the first 3 months matter so much
more than they think and also like the whole dominance thing is mostly
BS but I dont want to be too aggressive about saying that...
```

### Test Personas
- `margot` - Default, sharp, no-nonsense
- `sage` - Nurturing, encouraging
- `the-axe` - Brutal, cuts ruthlessly
- `blueprint` - Structure-focused
- `sterling` - Commercial/market-aware
- `cheerleader` - Pure encouragement
- `ivory-tower` - Literary/academic
- `bestseller` - Maximum readability

---

## Phase 14: Context Management & State Tracking

| Step | Action | Expected Result |
|------|--------|-----------------|
| 14.1 | Have 20+ back-and-forth exchanges in single issue | AI summarizes older conversation, keeps recent 3 exchanges verbatim |
| 14.2 | Establish a fact: "My dog's name is Max" early in conversation | AI remembers Max in later exchanges without reminder |
| 14.3 | Close an issue after productive conversation | Summary comment posted with established facts, decisions, and outstanding items |
| 14.4 | Check `.ai-context/knowledge.jsonl` after closing | New entries from conversation persisted |
| 14.5 | Open new issue and reference fact from closed issue | AI knows facts from knowledge base |
| 14.6 | Create PR from voice memo issue | PR body includes text statistics, editorial reasoning, and context references |
| 14.7 | Check PR body for "Decisions Made" section | Shows established facts and decisions from conversation |
| 14.8 | Check PR body for "Outstanding Items" section | Shows unanswered questions if any |

---

## Scoring Summary

| Phase | Tests | Passed | Failed | Notes |
|-------|-------|--------|--------|-------|
| 1. Day 1: Getting Started | 7 | | | |
| 2. First Week: Capturing Ideas | 6 | | | |
| 3. Building Chapters | 6 | | | |
| 4. Working With Your Editor | 5 | | | |
| 5. Switching Personas | 5 | | | |
| 6. Ready to Revise | 5 | | | |
| 7. Polish Phase | 5 | | | |
| 8. Whole Book Review | 5 | | | |
| 9. Ask the Editor | 4 | | | |
| 10. Text Statistics | 5 | | | |
| 11. Real Scenarios | 6 | | | |
| 12. Long-Term Learning | 4 | | | |
| 13. Edge Cases | 5 | | | |
| 14. Context Management & State | 8 | | | |
| **TOTAL** | **76** | | | |

---

## Sample Test Content

### First Voice Memo (Day 1)
```
okay so this is me just talking through it dont clean it up yet this is
for you as the editor to get the shape of it in your head i think the
book should be about 300 pages maybe a little more maybe less but roughly
that and split into 10 chapters that feels right not too many not too few
enough room to breathe and go deep and chapter 1 is really about orientation
its for the new dog owner who is overwhelmed and excited and tired already
and doesnt know where to start...
```

### Messy Stream-of-Consciousness (Phase 4)
```
so the thing about bonding with your dog is like its not just treats
right its about being present and like when youre on your phone and
the dogs just sitting there waiting thats not bonding thats coexisting
and I want people to understand that the first 3 months matter so much
more than they think and also like the whole dominance thing is mostly
BS but I dont want to be too aggressive about saying that...
```

### Test Personas
- `margot` - Default, sharp, no-nonsense
- `sage` - Nurturing, encouraging
- `the-axe` - Brutal, cuts ruthlessly
- `blueprint` - Structure-focused
- `sterling` - Commercial/market-aware
- `cheerleader` - Pure encouragement
- `ivory-tower` - Literary/academic
- `bestseller` - Maximum readability

---

**Upload `TEST_PLAN.csv` to Google Sheets to track progress.**
