# Results for the quantitative comparison

This folder holds everything needed to compare human coding, the two LLM prompts, and GCA on two observations of Miguel and Gregorio in Ms. Gallagher's class: OBS_26-0498 (segments c and d, 97 lines) and OBS_26-0515 (segments a and b, 151 lines). All files contain codes and scores only. Transcript text, translations, and the LLMs' written reasons are left out so that classroom data stays out of this public repository; every file has a `row` ID (for example `c12`, meaning segment c, line 12) that joins back to the transcript in `Data/Track A/all_observations_combined.csv`.

## Folders

| Folder | Contents |
|---|---|
| `comparison_data/` | The input data: `analysis_table.csv` and the per-method files described below. |
| `llm_agreement/` | Outputs of `A4 - LLM Agreement.ipynb`: turn-level agreement tables, agreement bars, and confusion matrices. |
| `co_construction/` | Outputs of `A4 - Co-construction Detection.ipynb`: which co-construction turns each method surfaces, misses, and GCA score plots. |

## Start here

`comparison_data/analysis_table.csv` combines everything into one table with one row per transcript line for both observations. Use it for the notebook, because all methods are already aligned on the same rows. The separate files below hold the same data, split by method and observation, in case you need them on their own.

## Columns in `analysis_table.csv`

| Column | Meaning |
|---|---|
| `observation`, `row`, `segment`, `speaker` | Which line this is. |
| `is_adult` | True for Ms. Gallagher and Ms. Benoit. Adult lines are never coded, so filter them out before computing agreement. |
| `vishal_whose`, `vishal_level`, `caesar_whose`, `caesar_level` | Each coder's codes as shown in the adjudication tool, before adjudication. |
| `human_final_whose`, `human_final_level` | The adjudicated (consensus) codes. Treat these as the human reference. |
| `basic_explanation`, `basic_peer_engagement` | The basic prompt's two labels. It gives every line both an explanation label and an engagement label, so it never says Self or Other directly. To compare it with the human Level, use `basic_explanation` on lines the humans coded Self and `basic_peer_engagement` on lines they coded Other. |
| `enhanced_turn`, `enhanced_whose`, `enhanced_builds_on`, `enhanced_level` | The enhanced prompt's codes. Its Level appears only on the last line of each turn, which is the same rule the human coders followed. |
| `gca_unit` | The GCA unit the line belongs to. GCA merges each speaker's consecutive lines into one unit and keeps only Miguel and Gregorio, so adult lines and the third student ("Other") have no unit. |
| `gca_social_impact`, `gca_impact_pct` | How similar the next few peer units are to this unit, and its percentile within the observation. |
| `gca_responsivity`, `gca_responsivity_pct` | How similar this unit is to the previous few peer units, and its percentile within the observation. |

## Other files in `comparison_data/`

- `human_adjudicated_<observation>_<segments>.csv`: the human columns above, for one observation.
- `llm_basic_<observation>_<segments>.csv` and `llm_enhanced_<observation>_<segments>.csv`: each LLM's codes for one observation.
- `gca_merged_units_<observation>.csv`: one row per GCA unit for the whole observation, with the rows it covers (`unit_rows`) and its scores.

## Things to keep in mind

- Compare codes by turn rather than by line where possible. Level sits on the last line of a turn, so a line-by-line comparison counts differences in where the Level was written as disagreements.
- Labels differ in capitalization between methods (for example "Some detail" and "some detail"), and the enhanced prompt writes "Unclear / not coded". Lowercase all labels, and treat blank, "N/A", "Unclear", and "Unclear / not coded" as "not coded", before comparing.
- OBS_26-0515 segments a and b were also used to calibrate the codebook, so the LLM results there are a development check rather than a clean test. OBS_26-0498 segments c and d are the clean test set.
- The human inter-rater reliability for OBS_26-0498 is already computed by `analysis/irr_semantic.py`, with its results in `Data/human_coding/normalized/`.
