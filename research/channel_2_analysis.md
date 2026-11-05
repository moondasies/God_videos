# Channel 2 — `@godspov_` ("Gods POV")

URL provided: https://www.instagram.com/godspov_
Research date: 2026-11-05

## Status: PARTIAL. The account was identified, but no reels were watched.

I have **not** viewed any reel, caption or comment from this account. Instagram, YouTube and
the article below were all blocked by the build environment's network policy. Everything here
comes from **search-engine result snippets**, so treat it as second-hand information.

### What could be established (from search snippets only)

| Claim | Source (snippet) | Confidence |
|---|---|---|
| The account is run under the name **"Gods POV"**. | Search result: Social Ketchup creator page *"What if God could casually call out our religious hypocrisies? God's POV imagines what that might look like"* — https://www.socialketchup.in/creators/gods-pov-12490893 | Medium |
| The format imagines **Lord Krishna as a casual, blunt God** who talks with believers about everyday habits and points out inconsistencies in how they practise faith. | Same Social Ketchup snippet | Medium (not verified by viewing) |
| A linked **YouTube Shorts channel `@Gods_pov`** lists `godspov_` as its Instagram and describes *animated stories from the Bhagavad Gita, Mahabharata, Ramayana and Hindu mythology*, with **weekly** new episodes. | https://www.youtube.com/@Gods_pov/shorts (search snippet) | Medium |
| Language of the reels | Not stated in any accessible source | Unknown |
| Follower counts, views, engagement | Not available | Unknown |

### What was attempted

| Attempt | Result |
|---|---|
| `curl` / WebFetch `instagram.com/godspov_` | blocked (`403` / `ENOTFOUND`) |
| WebFetch `socialketchup.in` creator page | blocked (`ENOTFOUND`) |
| WebFetch `youtube.com/@Gods_pov/shorts` | blocked (`ENOTFOUND`) |

**0 reels inspected.**

### Implications we can draw *without* copying anything (hypotheses)

* *Hypothesis:* a **conversational, humanised deity** (a casual, direct God talking to an
  ordinary person) is the format's core appeal. **Mahadev & Me** shares the premise of a
  conversation with the divine, but differs on purpose:
  * a **different deity** (Mahadev rather than Krishna);
  * a **fixed recurring human protagonist** (the girl), giving an ongoing friendship arc;
  * the focus is on **inner-life problems** such as self-worth, overthinking and boundaries,
    rather than calling out ritual hypocrisy;
  * the tone is **compassionate, with light playfulness**, rather than blunt call-outs.
* *Hypothesis:* episodic, weekly, story-led animation builds habitual viewing. We adopt a
  numbered series ("EP 1, EP 2") and a consistent title card.

Do not reuse their scripts, scenes, character designs, voices, catch-phrases or distinctive
visual assets.

## How to complete this analysis

Follow the same steps as `channel_1_analysis.md`, using `private/research/godspov/` and
`research/analyze_reels.py`.
