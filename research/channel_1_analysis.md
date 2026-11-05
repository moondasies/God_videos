# Channel 1 — `@yelefinn.official` (Instagram)

URL provided: https://www.instagram.com/yelefinn.official
Research date: 2026-11-05

## Status: NOT ANALYSED. The content was inaccessible from the build environment.

I have **not** watched any reel from this account. Nothing below describes its content, and no
numbers, hooks, styles or comments are claimed.

### What was attempted (verifiable log)

| Attempt | Result |
|---|---|
| `curl https://www.instagram.com/...` from the build container | `CONNECT tunnel failed, response 403` (instagram.com blocked by the session's network policy) |
| WebFetch of `https://www.instagram.com/yelefinn.official/` | `getaddrinfo ENOTFOUND www.instagram.com` (host not allowed in this session) |
| Web search `"yelefinn" instagram` (extended) | No result for this handle. Closest hits were unrelated accounts (`@yeloufins`, `@finfinofficial`). |
| Web search `yelefinn.official reels` (extended) | No indexed page for this account. |

Conclusion: the account is not indexed by the search engine available here, and Instagram itself
is blocked. **0 of N reels inspected.**

## How to complete this analysis (you or a future session with access)

1. On your own device, open the account and save the reels you are allowed to view. Use the
   Instagram "Save" feature for viewing; download only content you are permitted to download.
   Place local copies in `private/research/yelefinn/` (git-ignored).
2. Fill `research/templates/reel_log_template.csv` (one row per reel: URL, date, views,
   likes, comments, caption, and your notes on the hook, arc and comments).
3. Run the measurement tool, which records **observations only**:
   ```bash
   python research/analyze_reels.py private/research/yelefinn --log research/yelefinn_log.csv --out research/channel_1_measured.md
   ```
   It measures duration, shot-cut count and pacing, the first-3-second contact sheet, speech vs
   music loudness, and caption-band brightness. Interpretation (why something performed) stays a
   **hypothesis** column you fill in yourself.
4. Ask the pipeline maintainer (or Claude in a session where instagram.com is allowed in the
   network settings) to turn the measured table into this report.

## Per-video capture schema (to be filled)

| Field | Value |
|---|---|
| Title / URL / date / duration | — |
| Views / likes / comments (if visible) | — |
| Hook (first 3 s) | — |
| Story structure & emotional arc | — |
| Characters, expressions, interactions | — |
| Framing, visual style, backgrounds, transitions | — |
| Voice delivery, pacing, music, SFX | — |
| Caption style, typography, position | — |
| Moral / takeaway | — |
| Recurring audience comments / needs | — |
| Engagement factors: **observation** vs **hypothesis** | — |
