# AI Book Editor - Manual Test Plan

Copy to Google Sheets with columns: **Test ID | Step | Expected Result | Pass/Fail | Notes**

---

## Phase 1: New Project Setup (First-Time Experience)

| ID | Step | Expected Result |
|----|------|-----------------|
| 1.1 | Create new repo from template (or fork ai-book-editor) | Repo created with all workflows and files |
| 1.2 | Add `ANTHROPIC_API_KEY` secret in Settings → Secrets → Actions | Secret saved successfully |
| 1.3 | Create first issue with `voice_transcription` label and a raw transcript | Issue created, workflow triggers within 30 seconds |
| 1.4 | Wait for AI response (2-5 minutes) | AI comments with welcome message + analysis |
| 1.5 | Verify welcome message includes "Welcome!" and asks discovery questions | 4 questions about book vision, audience, goals, polish level |
| 1.6 | Verify AI adds `ai-reviewed` label automatically | Label appears on issue |
| 1.7 | Check that NO `book.yaml` exists yet (new project detection) | File should not exist in `.ai-context/` |

---

## Phase 2: Basic Voice Memo Processing

| ID | Step | Expected Result |
|----|------|-----------------|
| 2.1 | Submit transcript with filler words: "Um, so like, you know, I was thinking..." | Cleaned transcript removes ums, likes, you knows |
| 2.2 | Check cleaned transcript preserves author's meaning and voice | Content meaning unchanged, just cleaner |
| 2.3 | Verify "Content Analysis" section identifies themes/topics | Themes listed, relevant to content |
| 2.4 | Verify "Suggested Placement" recommends chapter or location | Specific chapter suggestion or "new chapter" recommendation |
| 2.5 | Verify "Editorial Notes" has "What's working" section | Positive feedback present |
| 2.6 | Verify "Editorial Notes" has questions for author | At least 1-2 clarifying questions |
| 2.7 | Check "Editorial Reasoning" collapsible section exists | Expandable section explaining AI's thinking |
| 2.8 | Verify token usage shown at bottom of comment | Shows model, tokens, cost |

---

## Phase 3: Conversational Interaction

| ID | Step | Expected Result |
|----|------|-----------------|
| 3.1 | Reply: `@margot-ai-editor I want this in chapter 1` | AI acknowledges placement, may ask follow-up |
| 3.2 | Reply: `@margot-ai-editor what do you think of the opening hook?` | AI responds conversationally about the content |
| 3.3 | Reply: `@margot-ai-editor create PR` | AI creates a PR with the content |
| 3.4 | Verify PR has cleaned content in correct location | Content in `chapters/` directory |
| 3.5 | Reply: `@margot-ai-editor place in chapter-intro.md` then `create PR` | PR targets the specified file |
| 3.6 | Reply: `@margot-ai-editor status` | AI reports project progress (chapters, phase, etc.) |

---

## Phase 4: Persona Switching

| ID | Step | Expected Result |
|----|------|-----------------|
| 4.1 | Reply: `@margot-ai-editor use sage` | AI confirms switch, responds in Sage's nurturing voice |
| 4.2 | Submit new issue with label `persona:the-axe` | AI responds in brutal, cutting style |
| 4.3 | Reply: `@margot-ai-editor as the-axe: review this harshly` | Inline persona switch for that response |
| 4.4 | Reply: `@margot-ai-editor list personas` | AI lists all available personas with descriptions |
| 4.5 | Verify persona voice is consistent (compare Margot vs Sage responses) | Distinct tone, vocabulary, approach |

---

## Phase 5: Feedback Intensity Controls

| ID | Step | Expected Result |
|----|------|-----------------|
| 5.1 | Reply: `@margot-ai-editor be harsher` | AI acknowledges, next feedback is more critical |
| 5.2 | Reply: `@margot-ai-editor be gentler` | AI acknowledges, feedback becomes more encouraging |
| 5.3 | Reply: `@margot-ai-editor I'm ready for tough love` | AI shifts to rigorous feedback mode |
| 5.4 | Reply: `@margot-ai-editor skip the questions, just review` | AI skips discovery, gives direct feedback |
| 5.5 | Add `quick-review` label to new issue | AI skips discovery phase entirely |

---

## Phase 6: Book Phase Adaptation

| ID | Step | Expected Result |
|----|------|-----------------|
| 6.1 | (New project) Verify feedback is encouraging, minimal criticism | Focus on ideas, not nitpicking |
| 6.2 | After ~3 chapters exist, submit new memo | AI tracks consistency, notes themes |
| 6.3 | Reply: `@margot-ai-editor I'm ready to revise` | AI acknowledges phase transition |
| 6.4 | Submit content in REVISING phase | Feedback is structural, rigorous, challenging |
| 6.5 | Reply: `@margot-ai-editor let's polish this` | AI shifts to line-editing mode |
| 6.6 | Submit content in POLISHING phase | Feedback focuses on grammar, word choice, rhythm |

---

## Phase 7: PR Creation & Review

| ID | Step | Expected Result |
|----|------|-----------------|
| 7.1 | After `create PR`, check PR title and description | Clear title, body summarizes content |
| 7.2 | Check PR targets correct branch (main) | Base branch is default branch |
| 7.3 | Push a branch that modifies `chapters/*.md` | AI automatically reviews the PR |
| 7.4 | Check AI PR review has editorial feedback | Review comment with suggestions |
| 7.5 | Merge PR, verify content in book | Chapter file updated correctly |

---

## Phase 8: Learning & Configuration

| ID | Step | Expected Result |
|----|------|-----------------|
| 8.1 | Answer AI's discovery questions with specific preferences | AI should remember these |
| 8.2 | Check if AI creates PR to update `.ai-context/book.yaml` | PR appears with learned info |
| 8.3 | Review book.yaml PR content | Contains title, audience, themes from conversation |
| 8.4 | Merge book.yaml PR, submit new content | AI references the learned context |
| 8.5 | Correct the AI: "Actually, my audience is developers, not managers" | AI acknowledges, may propose config update |

---

## Phase 9: Labels & Automation

| ID | Step | Expected Result |
|----|------|-----------------|
| 9.1 | Create issue without `voice_transcription` label | Workflow does NOT trigger |
| 9.2 | Add `voice_transcription` label to existing issue | Workflow triggers on label add |
| 9.3 | Create issue with `whole-book` label | AI reads all chapters, gives cross-chapter analysis |
| 9.4 | Check phase labels are auto-applied | `phase:discovery` or `phase:feedback` appears |
| 9.5 | Verify `ai-reviewed` label added after processing | Label present |

---

## Phase 10: Edge Cases & Error Handling

| ID | Step | Expected Result |
|----|------|-----------------|
| 10.1 | Submit issue with empty body | AI responds with helpful error message |
| 10.2 | Submit very long transcript (5000+ words) | AI processes without timeout, may summarize |
| 10.3 | Submit content in non-English language | AI handles gracefully (may note language) |
| 10.4 | Send conflicting commands: "be harsher" then "be gentler" in same comment | AI uses last instruction or asks for clarification |
| 10.5 | Mention `@margot-ai-editor` without a command | AI responds conversationally |
| 10.6 | Create 3 issues rapidly with `voice_transcription` label | All 3 process without race conditions |

---

## Scoring Summary

| Phase | Tests | Passed | Failed | Notes |
|-------|-------|--------|--------|-------|
| 1. New Project Setup | 7 | | | |
| 2. Voice Memo Processing | 8 | | | |
| 3. Conversational Interaction | 6 | | | |
| 4. Persona Switching | 5 | | | |
| 5. Feedback Intensity | 5 | | | |
| 6. Book Phase Adaptation | 6 | | | |
| 7. PR Creation & Review | 5 | | | |
| 8. Learning & Configuration | 5 | | | |
| 9. Labels & Automation | 5 | | | |
| 10. Edge Cases | 6 | | | |
| **TOTAL** | **58** | | | |

---

## Quick Reference: Test Data

### Sample Voice Memo (use for 2.x tests)
```
Um, so I've been thinking about, you know, how to open this book.
I think we should start with a story, like a real example of someone
who struggled with this before they found the solution. You know what
I mean? It's important to hook the reader right away. And then, uh,
we can get into the methodology after they're invested.
```

### Sample Long Transcript (use for 10.2)
```
[Paste 5000+ word transcript here for stress testing]
```

### Test Personas
- `margot` - Default, sharp
- `sage` - Nurturing
- `the-axe` - Brutal
- `blueprint` - Structure-focused
- `sterling` - Commercial
