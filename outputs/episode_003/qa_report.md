# QA report – episode_003 (final)

**Overall: PASSED**

| Area | Check | Status | Detail |
|---|---|---|---|
| technical | resolution | PASS | 1080x1920 (expected 1080x1920, 9:16) |
| technical | frame rate | PASS | 30.00 fps |
| technical | video codec | PASS | h264 yuv420p High |
| technical | audio codec | PASS | aac 48000 Hz 2 ch |
| technical | decode integrity | PASS | decoded without errors |
| timing | duration 30-40 s | PASS | 32.23s |
| animation | no missing frames | PASS | 966 frames (expected ~967) |
| animation | no frozen stretches >1.5 s | PASS | min motion per 1.5 s window ok; mean frame delta 2.199 |
| animation | every shot has visible movement | PASS | s01:0.661, s02:0.63, s03:6.44, s04:0.739, s05:1.207, s06:0.641, s07:1.133, s08:2.628 |
| animation | no unintended black frames | PASS | none before the final fade |
| audio | integrated loudness | PASS | -14.3 LUFS (target -14) |
| audio | true peak / no clipping | PASS | -1.5 dBFS |
| audio | dialogue audible over music | PASS | speech -20.3 dB vs music -41.1 dB under speech (gap 20.8 dB, need >= 10) |
| voice | girl: correct profile | PASS | girl_preview via piper |
| voice | girl: production voice | WARN | PREVIEW voice – Piper hi_IN-priyamvada (CC BY-NC-SA 4.0) - preview only |
| voice | mahadev: correct profile | PASS | mahadev_preview via piper |
| voice | mahadev: production voice | WARN | PREVIEW voice – Piper hi_IN-pratham (CC BY-NC-SA 4.0) - preview only |
| voice | no clipped words / unexpected silence | PASS | all lines clean |
| lip-sync | mouth opening tracks speech energy | PASS | mean correlation 0.76 over 7 on-screen lines (method: hybrid(energy+rhubarb)) |
| subtitles | timing, punctuation & width | PASS | all caption chunks fit, readable >= 0.35 s each |
| subtitles | safe-zone placement | PASS | caption band y=1370-1560 px of 1920 (keeps clear of top 13% / bottom 17% UI) |
| spiritual | no fabricated scriptural attribution | PASS | all lines marked original fiction / cited |
| spiritual | sensitive-topic safeguard | PASS | ok |
| character | girl: locked identity spec | PASS | hash 121cebf95063f6bc |
| character | mahadev: locked identity spec | PASS | hash 1aa106f37ad244b3 |
| character | wardrobe continuity | PASS | girl outfit(s) in episode: ['home_tshirt'] |
