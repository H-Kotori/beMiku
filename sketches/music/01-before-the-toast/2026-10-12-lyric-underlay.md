# Before the toast — first lyric-to-note map

Date: **2026-10-12**. Map version: **0.1**, for score version **0.1**. This assigns the first two lines of our [original lyric](../../lyrics/2026-10-05-before-the-toast.md) to existing lead notes. **A planning map only: no vocal import, pronunciation test, listening, or new audio render.** The [A/B previews](README.md) and their score are unchanged.

## Proposed placement

The lines are **いつもの冗談 / 今日も聞かせて**, read **いつものじょうだん / きょうもきかせて**. Their 8 and 7 morae map to lead indices 0–7 and 8–14. A mora is a language timing unit; here it labels a lyric slot, not a musical beat or a requirement to give every slot equal duration.

The [editable CSV](underlay-first-two-lines.csv) records the proposed placement against [score.json](score.json). `lead_index` is zero-based; `line` and `mora` are one-based. Beat positions are zero-based quarter notes at 96 BPM. `written_unit` preserves the kana reading; `vocal_intent` is a human-readable cue, **not editor-specific phoneme syntax or ready-to-import lyrics**. The builder does not read this CSV.

| Lead index | Written unit | Vocal intent | Pitch | Start beat | End A | End B |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | い | i | G4 | 0 | 0.75 | 0.75 |
| 1 | つ | tsu | A4 | 1 | 1.5 | 1.5 |
| 2 | も | mo | C5 | 1.5 | 2.5 | 2.5 |
| 3 | の | no | B4 | 3 | 3.75 | 3.75 |
| 4 | じょ | jo | A4 | 4 | 4.5 | 4.5 |
| 5 | う | Continue the o vowel | G4 | 4.5 | 5.25 | 5.25 |
| 6 | だ | da | A4 | 5.5 | 6 | 6 |
| 7 | ん | Nasal ending | C5 | 6.25 | 7.5 | 7.5 |
| 8 | きょ | kyo | C5 | 8 | 8.75 | 8.75 |
| 9 | う | Continue the o vowel | D5 | 9 | 9.5 | 9.5 |
| 10 | も | mo | E5 | 9.5 | 10.25 | 10.25 |
| 11 | き | ki | D5 | 10.5 | 11 | 11 |
| 12 | か | ka | C5 | 11.25 | 12 | 12 |
| 13 | せ | se | B4 | 12.25 | 12.75 | 12.75 |
| 14 | て | te | D5 | 13 | 15.5 | 14 |

For the long vowels in じょう and きょう, the proposed second slot continues **o**, rather than introducing a new **u** vowel. The Japan Foundation's [kana-teaching material](https://www.jpf.go.jp/j/urawa/j_rsorcs/methods/dl/letter_p3_01.pdf), page 15, explicitly distinguishes the spelling きょう from its long-vowel reading. That supports the reading distinction, not the suitability of this musical placement. Roman letters above are approximate cues; no fine phonetic or pitch-accent prescription is made. Source accessed October 12, 2026.

## What the placement exposes

**Long vowel in 冗談:** notes 4 and 5 meet at beat 4.5, so this map has no MIDI gap inside じょう. A4 descends to G4. Adjoining MIDI notes alone do not ensure that a vocal editor will carry the vowel smoothly across them.

**Long vowel in 今日:** note 8 ends at beat 8.75; note 9 starts at beat 9. That is a **0.25-beat / 0.15625-second** gap inside the proposed long vowel. Our concern is that a literal rendering may break the word into two attacks. That is an untested delivery hypothesis, not an observation from the instrumental guide. A later comparison could extend only note 8's end to beat 9 while keeping its onset and both pitches fixed. Do not apply that change to the current A/B files.

**Nasal ending in 冗談:** note 6 ends at beat 6; note 7 starts at 6.25 and lasts 1.25 beats (**0.78125 seconds**), rising from A4 to C5. The proposed ん therefore follows a **0.15625-second** MIDI gap and occupies its own long note. Preserve the nasal in the reading, but leave its detailed onset and vowel-to-nasal transition unresolved. TUFS's [pronunciation guidance](https://www.coelang.tufs.ac.jp/mt/ja/pmod/practical/02-04-01.php), read October 12, explains that ん counts as a mora and its realization varies with context; our label does not prescribe an English n or an added vowel. We need to hear whether the word remains connected and intelligible; a separate nasal note is not automatically an error.

**The existing A/B question:** the changed note, index 14, now carries the final て of 聞かせて. A holds it for **1.5625 seconds**; B for **0.625 seconds**. This identifies what the existing comparison would change in a vocal setting without deciding which version communicates the scene better. Neither guide contains these words. All durations here are calculated from the authored score, not measured from a sung performance.

## Next decision

Keep this literal map as a baseline. Before importing it into a licensed editor, prepare one separate, clearly named articulation candidate for the 今日 join and decide how to handle the final nasal; do not mix those changes into the release comparison. The [Mitchie M study](../../../journal/2026-10-11-mitchie-m-and-natural-phrasing.md) motivates attention to transitions but supplies no tested settings for our phrase.

The remainder of the lyric is unmapped, including the small っ at the start of line three. Singability, spoken and sung accent, register suitability, breaths, and emotional effect remain open. The October 8 owner listening request remains pending without another prompt; browser integration and further model trials remain deferred.
