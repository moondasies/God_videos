# QA report – episode_002 (final)

**Overall: PASSED**

| Area | Check | Status | Detail |
|---|---|---|---|
| technical | resolution | PASS | 1080x1920 (expected 1080x1920, 9:16) |
| technical | frame rate | PASS | 30.00 fps |
| technical | video codec | PASS | h264 yuv420p High |
| technical | audio codec | PASS | aac 48000 Hz 2 ch |
| technical | decode integrity | PASS | decoded without errors |
| timing | duration 30-40 s | PASS | 39.93s |
| animation | no missing frames | PASS | 1198 frames (expected ~1198) |
| animation | no frozen stretches >1.5 s | PASS | min motion per 1.5 s window ok; mean frame delta 2.058 |
| animation | every shot has visible movement | PASS | s01:0.416, s02:0.762, s03:4.305, s04:0.68, s05:1.058, s06:0.568, s07:0.864, s08:1.181, s09:3.445 |
| animation | no unintended black frames | PASS | none before the final fade |
| audio | integrated loudness | PASS | -13.9 LUFS (target -14) |
| audio | true peak / no clipping | PASS | -1.2 dBFS |
| audio | dialogue audible over music | PASS | speech -20.3 dB vs music -36.8 dB under speech (gap 16.5 dB, need >= 10) |
| voice | girl: correct profile | PASS | girl_preview via piper |
| voice | girl: production voice | WARN | PREVIEW voice – Piper hi_IN-priyamvada (CC BY-NC-SA 4.0) - preview only |
| voice | mahadev: correct profile | PASS | mahadev_preview via piper |
| voice | mahadev: production voice | WARN | PREVIEW voice – Piper hi_IN-pratham (CC BY-NC-SA 4.0) - preview only |
| voice | no clipped words / unexpected silence | PASS | all lines clean |
| lip-sync | mouth opening tracks speech energy | PASS | mean correlation 0.75 over 7 on-screen lines (method: hybrid(energy+rhubarb)) |
| subtitles | timing, punctuation & width | PASS | all caption chunks fit, readable >= 0.35 s each |
| subtitles | safe-zone placement | PASS | caption band y=1370-1560 px of 1920 (keeps clear of top 13% / bottom 17% UI) |
| spiritual | no fabricated scriptural attribution | PASS | all lines marked original fiction / cited |
| spiritual | sensitive-topic safeguard | PASS | ok |
| character | girl: locked identity spec | PASS | hash 121cebf95063f6bc |
| character | mahadev: locked identity spec | PASS | hash 1aa106f37ad244b3 |
| character | wardrobe continuity | PASS | girl outfit(s) in episode: ['blazer_plaid'] |
