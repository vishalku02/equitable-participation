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
