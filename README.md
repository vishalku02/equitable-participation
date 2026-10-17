# Equitable Participation

## Data setup

The data files are not stored in this repository, because they contain classroom data about students and teachers. Before running the notebooks, create a `Data` folder in the top level of the repository and place the `Track A` folder inside it. The notebooks read files from paths such as `Data/Track A/all_observations_combined.csv`, so the folder names must match exactly, including the capital letters and the space in `Track A`.

After setup, the repository should look like this:

```
equitable-participation/
  README.md
  A4 - Methods.ipynb
  Data/
    Track A/
      Deidentified segment transcripts/
      all_observations_combined.csv
      liwc2022.tsv
      observation_metadata.csv
      students_liwc22.csv
      teacher_demographics.csv
```

Git ignores the whole `Data` folder, so the data will never be committed by accident.
