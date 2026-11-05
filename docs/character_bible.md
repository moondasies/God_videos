# Character bible

Both characters are drawn by a **procedural 2.5D vector rig** (`animation/characters.py`) from
locked identity specs (`GIRL_IDENTITY`, `MAHADEV_IDENTITY`). QA checks the SHA-1 of each spec
against `config/identity.lock.json`, so an accidental redesign fails QA.

Reference sheets: `assets/characters/<name>/{turnaround,expressions,mouth_shapes,blinks,gestures}.png`,
the girl's `wardrobe.png`, and transparent poses `pose_*.png`. Regenerate them with
`python -m pipeline assets`.

## Honest note on likeness
The rig was designed from your **illustrated character sheet**: palette, hair, parting, eye
colour, accessories, outfit and proportions. It is a **stylised, simplified interpretation**, not
a pixel copy of the painted sheet. The sheet itself and your photograph are kept in `private/` and
never committed. Before locking the face for production, compare `assets/characters/girl/expressions.png`
with the sheet and tell me what to adjust (jaw, eye size, nose, smile). Each change is a few numbers
in `GIRL_IDENTITY` plus a re-lock (`python -c "from pipeline.qa import lock_identities; lock_identities()"`).

## The girl (working name not yet chosen)
* **Face:** soft oval with a gently tapered chin, warm light skin #f2c6a6, light blush.
* **Eyes:** large almond-shaped eyes, dark-brown iris #5a361f, winged lash flick, soft brows.
* **Hair:** long, straight, dark brown #2b1b15, **centre parting**, falling in front of both
  shoulders to the chest.
* **Always-on accessories:** small gold hoop earrings and a thin gold chain with an oval pendant.
* **Height:** about 163 cm. Mahadev is about 188 cm.
* **Rig capabilities:** yaw −1…+1 (front to near-profile), pitch, roll; 17 expressions; 9 mouth
  shapes; blink; 12 gestures with IK arms; hair sway; breathing; back view.

### Wardrobe (clothes change, identity doesn't)
| Key | Use |
|---|---|
| `blazer_plaid` | Office / approved sheet look: beige plaid blazer, black tee |
| `home_tshirt` | Bedroom / night: oversized lilac tee |
| `kurta` | Spiritual / family: peach cotton kurta, gold-dot neckline |
| `home_kurti` | Emotional home scenes: teal kurti |
| `hoodie` | Winter / rain: slate hoodie |
| `casual_denim` | Coffee shop / weekend: cream top, denim jacket |
| `winter_jacket` | City winter: hoodie under an olive jacket |

## Mahadev
* Blue-grey skin #8091c4 with lighter highlights. Long, flowing navy-black hair (wavy locks over
  the shoulders). **Jata topknot** wrapped with **rudraksha** bands.
* **Crescent moon** on his left side of the topknot, with a soft glow.
* **Tripundra:** three white ash lines and a red bindu.
* Gold hoop earrings. A **serpent (Vasuki)** coiled at the neck, its hood raised beside his right
  cheek. It sways and occasionally flicks its tongue.
* Rudraksha malas, armbands and bracelets. A **tiger-skin** drape over his left shoulder, with a
  tiger dhoti and orange sash.
* Optional **trishul with damru** prop (`props: {trishul: true}`).
* Expression range: calm, compassionate, smiling, playful, gently laughing, thoughtful. Never
  aggressive. Abhaya (blessing) gesture.
* Divine presence: a soft golden aura and converging light motes when he appears.

## Known rig limitations (be aware when writing scenes)
* **Upper-body rig only.** No legs, walking or full sitting poses yet. Use medium shots, close-ups
  and back views; sitting is implied by framing.
* Yaw ±1 is a strong three-quarter view, **not a true side profile**.
* No finger-level animation beyond hand-shape presets. No touching or contact between the characters.
