# Writing rules

## Summary

All documentation in this repository uses ASD-STE100 Simplified Technical English (STE). This page gives the rules that apply here. It also gives the project word list. Use the [glossary](glossary.md) for technical names.

<details>
<summary>Why STE</summary>

STE gives one meaning to each word and a short, fixed sentence structure. Readers who do not have English as their first language can read it easily. Translation tools also give better results.

The official STE dictionary has a licence. This page does not copy it. It gives the writing rules and a small project word list. Technical names (for example ECU, ROM, IGT) are permitted, as STE rule 1.5 permits.

</details>

## Page structure

1. Start each page with a title (`#`) and a section `## Summary`.
2. Write the summary in five sentences or less, or as one table.
3. Put detail after the summary. Use sub-sections, or a `<details>` block, or a link to a different page.
4. Put the most important information first.
5. Write facts only. Do not write the history of the work (dates of tests, old errors, earlier opinions, who decided what).
6. Write the result of a test, not the story of the test.

## Words

1. Use one word for one meaning. Use the same word each time for the same thing.
2. Use the names in the [glossary](glossary.md). Do not use synonyms.
3. Do not use a noun cluster of more than three words. Use "of" or a short phrase instead.
4. Use these words, not the words in the right column:

   | Use | Do not use |
   |---|---|
   | make sure, examine | ensure, verify, check (as a verb) |
   | do | perform, carry out |
   | use | utilise, employ |
   | get | obtain, acquire |
   | before, after | prior to, subsequent to |
   | to | in order to |
   | start, stop | commence, terminate |
   | near, next to | adjacent to |
   | enough | sufficient |
   | show | indicate, demonstrate |
   | possibly | potentially, likely (as an adverb) |
   | the ECU | the unit, the box, the computer |

5. Write numbers as digits. Give the unit after each value (for example "800 rpm", "5 V", "20 µs").

## Verbs

1. Use only these tenses: simple present, simple past, simple future.
2. Do not use the "-ing" form of a verb, except in a technical name.
3. In procedures, use the imperative (command) form.
4. In descriptions, use the active voice where possible.

## Sentences

1. A sentence in a procedure has a maximum of 20 words.
2. A sentence in a description has a maximum of 25 words.
3. Write one instruction in each sentence. Two actions are permitted only if you do them at the same time.
4. Write one topic in each sentence.
5. A paragraph has a maximum of six sentences and one topic.
6. Use a vertical list for three or more items.

## Procedures

1. Write each step as one numbered instruction.
2. Write a condition before the instruction: "If the lamp is off, stop the test."
3. Write a warning or a caution before the step that it is for.
   - **WARNING:** a risk of injury.
   - **CAUTION:** a risk of damage to equipment.
4. Mark each step that applies electrical power with **(OWNER APPROVAL)**. The owner must approve that step on the day of the test (see [`CLAUDE.md`](../CLAUDE.md)).

## Evidence and confidence

Each technical statement gives its evidence and a confidence level.

| Tag | Evidence |
|---|---|
| `[ROM:$F863]` | the ROM bytes at that address |
| `[EMU:test]` | a simulation or emulator test (name the test) |
| `[BENCH:file]` | a bench measurement (name the capture file in `data/captures/`) |
| `[PDF:p12]` | a page of a reference document |

| Confidence | Meaning |
|---|---|
| CONFIRMED | the ROM bytes or a measurement show it |
| LIKELY | the evidence agrees, but it does not prove it |
| GUESS | a possible explanation that needs a test |

## Generated text

Some pages and tables come from a generator. A test fails if the text is not current. Do not edit generated text by hand. Change the generator, then run it again. Each generated page names its generator in its first lines.
