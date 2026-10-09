# 11. Why does Opus 5.5 draw the French press upside down?

Status: prediction, committed 2026-10-09 before the runs.

Asked in words, Opus gets the filter order right 5 of 5. Drawing it, 2 of 5, and every drawing matches the order its own reply lists. So is it getting the order wrong while drawing, or can it not see the mistake?

Opus 5.5 only, 5 runs each:

- `svg-french-press-list-first`: write the order to order.txt, then draw.
- `autopsy-png-opus55-*`: its own five presses, three upside down, one off its axis and one right, asked what is wrong. It is not told they are its own.
- `harness/stated-order.mjs` puts what it said beside what it drew.

My prediction:

1. Listing first keeps it right: 4 or 5 of 5 drawn right.
2. It sees the mistake: the three upside-down stacks called upside down in 10 of 15 or more, the control in 1 of 5 or fewer. Fisher exact, p < 0.05.

If 1 fails, drawing changes its answer even with the order written down. If 2 fails, looking can't save it, which would explain why up to 8 rounds of rendering never fixed it.

Limits: 5 of 5 against the old 2 of 5 is only p = 0.17, so step 1 only shows a direction. All three upside-down presses also say the wrong order in text, so a miss may be Opus trusting the text. One model, one task.
