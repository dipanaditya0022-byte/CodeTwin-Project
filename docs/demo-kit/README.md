# Demo kit

Files for showing CodeTwin from start to finish. All code is from the project's labelled set (`ml/data`);
the people are made up.

| Folder | Use it for | What happens |
|---|---|---|
| `1-form/` | Submit through the public form, one file per person. **In the form settings, mark *Full name* as "Identifies the person"**, so Week 2's ZIP (named by people) links to the same people | Aarav and Diya are flagged together: Diya's file is Aarav's with every name changed. Kabir's is his own. |
| `2-zip/week2-submissions.zip` | "Upload a ZIP" on a second assignment, matched by file name | Aarav and Diya copy again, so they appear under repeat pairs. `notes.txt` is rejected with a reason. |
| `3-google-forms/` | "Import a spreadsheet": `responses.csv` + `uploaded-files.zip` | Neha and Arjun import (Arjun's is a restructured copy of Neha's). Isha's row shows "no file in the ZIP matches". |
| `4-landing-demo/` | Paste into the two boxes of the demo on the landing page | "Would be flagged for review" |

**Why Full name?** CodeTwin links submissions to one person by the value that identifies them. A form set to
identify by email and a ZIP named by people's names create two separate records for the same person, so their
repeat pairs would not show. CodeTwin never guesses that a name and an email are the same person.
