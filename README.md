# Equitable Participation

## Data setup

The data files are not stored in this repository, because they contain classroom data about students and teachers. Before running the notebooks, create a `Data` folder in the top level of the repository and place the `Track A` folder inside it. The notebooks read files from paths such as `Data/Track A/all_observations_combined.csv`, so the folder names must match exactly, including the capital letters and the space in `Track A`.

After setup, the repository should look like this:

```
equitable-participation/
  README.md
  A3 - Methods.ipynb
  Data/
    Track A/
      Deidentified segment transcripts/
      all_observations_combined.csv
      liwc2022.tsv
      observation_metadata.csv
      students_liwc22.csv
      teacher_demographics.csv
```

Git ignores everything in the `Data` folder except `Data/human_coding`, so the classroom data will never be committed by accident.

## Human and LLM coding files

The `Data/human_coding` folder holds our coding files, which contain codes but no transcript text. It includes our Assignment 3 coding of segments a, b, and d of observation `OBS_26-0758` (the low-social-impact observation). The transcript text is left out so that classroom data stays out of the repository. Each row has an ID such as `d58` (segment d, line 58), which matches the `segment` and `#` columns of `all_observations_combined.csv`, so you can join the codes back to the transcript.

- `human_codes_OBS_26-0758.csv` holds our codes, adapted from Webb et al. (2014). The `source` column records whether each code is the coder's original code (`original`), was changed during review (`corrected`), or was added during review (`added`), and the `notes` column explains each change.
- `human_vs_llm_OBS_26-0758.csv` adds the labels and reasons from the basic-prompt LLM run (Claude Sonnet 5.5) for comparison.

## Inter-rater reliability for OBS_26-0498, segments c and d

`analysis/irr_semantic.py` computes the semantic inter-rater reliability between Vishal's and Caesar's independent codes for segments c and d of `OBS_26-0498`. Run it from the top of the repository with `python3 analysis/irr_semantic.py`. It reads the two codes files in `Data/human_coding/` and writes its results to `Data/human_coding/normalized/`.

The script separates syntactic differences (a codebook rule that was not yet applied) from semantic differences (a real disagreement about a student's turn). It handles them in four steps:

1. It applies the codebook's existing rules to both coders' files, so that rule differences do not count as disagreements: adult lines are not coded; a student's answer coded Other right after an adult line becomes Self, with High, Medium, and Low mapped to Fully detailed, Some detail, and No detail; coordination moves and starter prompts (the rows listed in `COORDINATION_ROWS`) are not coded; and Unclear is treated as not coded. Every change is recorded in `normalization_log_OBS_26-0498_cd.csv`.
2. It compares whole turns rather than single lines, because the coders placed the Level on different lines of a turn. Turns come from Vishal's codes (a turn ends on the line where he recorded a Level), and lines that only Caesar coded are added as their own turns. Each coder's code for a turn is the last Whose and the last Level they gave within it.
3. It computes Cohen's kappa for Whose on the turns both coders coded, and for Level on the turns where both gave the same Whose and a Level, since Level is only comparable on the same scale.
4. It reports separately how many turns only one coder coded.

The outputs are each coder's normalized codes, the turn-by-turn comparison (`irr_turns_OBS_26-0498_cd.csv`), and the summary (`irr_summary_OBS_26-0498_cd.csv`). None of these files contain transcript text.
