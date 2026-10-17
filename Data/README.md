# Data

The data files are not stored in this repository. They contain classroom data about students and teachers, and the largest file is too big for GitHub.

To set up the data, place the `Track A` folder inside this `Data` folder. The notebooks read files from paths such as `Data/Track A/all_observations_combined.csv`, so the folder name must be exactly `Track A`.

After setup, the folder should look like this:

```
Data/
  README.md
  Track A/
    Deidentified segment transcripts/
    all_observations_combined.csv
    liwc2022.tsv
    observation_metadata.csv
    students_liwc22.csv
    teacher_demographics.csv
```

Git ignores everything in this folder except this README file, so the data will never be committed by accident.
