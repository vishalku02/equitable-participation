"""Two candidate revisions of Figure 1: how the uptake of the same student's ideas varies across observations.

Run from the top of the repository:

    python analysis/figure1_revision.py

Inputs are the enhanced LLM codes (results/llm_enhanced_full/), the transcript and metadata in Data/Track A/
(git-ignored; only speaker, row, and line order are read, never the dialogue), and the original Figure 1 table
(results/uptake_participation/findings_uptake_by_student.csv), which is used only to check the reproduction.
Outputs go to results/figure1_revision/ and the original Figure 1 is left untouched.

Turns, roles, and the row-matching rule follow `A5 - Uptake and Participation.ipynb`:

- A turn is one of the LLM's own `turn` IDs. Its Whose is the last Whose on its lines and its Level the last Level,
  because the prompt writes Level only on a turn's last line.
- A named student is listed in the metadata. The speaker labeled "Other" is an unnamed student unless the LLM coded
  every one of their lines N/A, in which case they are treated as an adult (OBS_25-0259). "Other" as a speaker is
  never confused with Whose = Other.
- `builds_on` is parsed for row IDs (a range counts once, at its first row), and each cited row is mapped to the
  turn that contains it.
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parent))
from a4_turns import clean, last_code  # noqa: E402

LLM_OUTPUTS = sorted(Path("results/llm_enhanced_full").glob("llm_enhanced_*.csv"))
TRANSCRIPT = Path("Data/Track A/all_observations_combined.csv")
METADATA = Path("Data/Track A/observation_metadata.csv")
ORIGINAL_FIGURE1 = Path("results/uptake_participation/findings_uptake_by_student.csv")
OUT = Path("results/figure1_revision")
OUT.mkdir(parents=True, exist_ok=True)

DEVELOPED_LEVELS = {"medium", "high"}
UNNAMED_STUDENT = "Other"
ROW_PATTERN = re.compile(r"\b([a-z])(\d+)(?:\s*[-–]\s*[a-z]?\d+)?\b")
MIN_IDEAS, MIN_OBSERVATIONS = 5, 3  # the original Figure 1 sample rule

# ACL two-column text width is about 6.3 in; fonts are sized for that width.
plt.rcParams.update({"font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7, "xtick.labelsize": 6.5,
                     "ytick.labelsize": 6.5, "legend.fontsize": 6.5, "pdf.fonttype": 42})


def short_id(observation):
    return observation.replace("OBS_", "")


# ---------------------------------------------------------------------------------------------------------------
# 1. Turns
# ---------------------------------------------------------------------------------------------------------------
llm = pd.concat([pd.read_csv(path, keep_default_na=False, dtype=str) for path in LLM_OUTPUTS], ignore_index=True)
observations = sorted(llm["observation"].unique())

transcript = pd.read_csv(TRANSCRIPT, usecols=["observation", "segment", "#", "speaker", "line_order"],
                         dtype=str, keep_default_na=False)
transcript = transcript[transcript["observation"].isin(observations)].copy()
transcript["row"] = transcript["segment"] + transcript["#"]
transcript["line_order"] = transcript["line_order"].astype(int)

metadata = pd.read_csv(METADATA, usecols=["obs_index", "teacher_pseudonym", "student_pseudonyms"],
                       dtype=str, keep_default_na=False)
metadata["observation"] = metadata["obs_index"].str.strip().str.replace(r"^OBS-", "OBS_", regex=True)
named_students = {o: set(re.findall(r"'([^']+)'", names))
                  for o, names in zip(metadata["observation"], metadata["student_pseudonyms"])}
classroom_of = dict(zip(metadata["observation"], metadata["teacher_pseudonym"].str.strip()))

lines = llm.merge(transcript[["observation", "row", "line_order"]], on=["observation", "row"], how="left")
assert lines["line_order"].notna().all(), "Some LLM rows have no transcript match."
for column in ["whose", "level"]:
    lines[column] = lines[column].map(clean)
unnamed = lines[lines["speaker"] == UNNAMED_STUDENT]
adult_like = {o for o, g in unnamed.groupby("observation") if (g["whose"] == "n/a").all()}


def role(observation, speaker):
    if speaker in named_students.get(observation, set()):
        return "Student"
    if speaker == UNNAMED_STUDENT and observation not in adult_like:
        return "Unnamed student"
    return "Adult"


lines["role"] = [role(o, s) for o, s in zip(lines["observation"], lines["speaker"])]
student_lines = lines[(lines["role"] != "Adult") & (lines["turn"] != "")]

turns = (
    student_lines.sort_values(["observation", "line_order"])
    .groupby(["observation", "turn"], sort=False)
    .agg(student=("speaker", "last"), speakers=("speaker", "nunique"), role=("role", "last"),
         row_ids=("row", " ".join), first_line=("line_order", "min"),
         whose=("whose", last_code), level=("level", last_code),
         builds_on_raw=("builds_on", lambda v: " | ".join(x for x in v if x)))
    .reset_index()
    .rename(columns={"observation": "observation_id", "turn": "turn_id"})
)
turns.insert(1, "classroom", turns["observation_id"].map(classroom_of))
mixed_speaker_turns = int((turns["speakers"] > 1).sum())
turns = turns.drop(columns="speakers")
turns.to_csv(OUT / "figure1_turns.csv", index=False)

row_speaker = lines.set_index(["observation", "row"])["speaker"]
row_order = lines.set_index(["observation", "row"])["line_order"]
row_turn = student_lines.set_index(["observation", "row"])["turn"]
turn_info = turns.set_index(["observation_id", "turn_id"])

# ---------------------------------------------------------------------------------------------------------------
# 2. Peer-uptake links: one row per unique (response turn, source turn); unresolved citations keep a status.
# ---------------------------------------------------------------------------------------------------------------
links = []
for _, response in turns[turns["whose"] == "other"].iterrows():
    o, t = response["observation_id"], response["turn_id"]
    base = {"observation_id": o, "response_turn_id": t, "responder": response["student"],
            "responder_role": response["role"], "response_level": response["level"],
            "response_developed": response["level"] in DEVELOPED_LEVELS, "builds_on_raw": response["builds_on_raw"]}
    cited = []
    for match in ROW_PATTERN.finditer(response["builds_on_raw"]):
        row = match.group(1) + match.group(2)
        if row not in cited:
            cited.append(row)
    if not cited:
        links.append({**base, "source_row": "", "source_turn_id": "", "source_student": "", "source_role": "",
                      "source_whose": "", "link_status": "no_row_id"})
        continue
    for row in cited:
        record = {**base, "source_row": row, "source_turn_id": "", "source_student": "", "source_role": "",
                  "source_whose": ""}
        if (o, row) not in row_speaker.index:
            links.append({**record, "link_status": "row_not_in_observation"})
            continue
        source = row_speaker[(o, row)]
        record.update(source_student=source, source_role=role(o, source))
        if source == response["student"]:
            status = "source_is_responder"
        elif record["source_role"] == "Adult":
            status = "source_is_adult"
        elif (o, row) not in row_turn.index:
            status = "source_row_without_turn"
        else:
            source_turn = row_turn[(o, row)]
            record.update(source_turn_id=source_turn, source_whose=turn_info.loc[(o, source_turn), "whose"])
            status = "ok" if row_order[(o, row)] < response["first_line"] else "source_after_response"
        links.append({**record, "link_status": status})

links = pd.DataFrame(links)
# A response that cites several rows of one source turn keeps one link to that turn.
keyed = links["source_turn_id"] != ""
links = pd.concat([links[keyed].drop_duplicates(["observation_id", "response_turn_id", "source_turn_id"]),
                   links[~keyed]], ignore_index=True)
links.to_csv(OUT / "figure1_link_audit.csv", index=False)

valid = links[links["link_status"] == "ok"]
valid_to_self = valid[(valid["source_whose"] == "self") & (valid["source_role"] != "Adult")]
developed_turns = turns[(turns["whose"] == "other") & turns["level"].isin(DEVELOPED_LEVELS)]
developed_linked_to_self = valid_to_self[valid_to_self["response_developed"]]["response_turn_id"].groupby(
    valid_to_self["observation_id"]).nunique().sum()
multi_source = valid[valid["response_developed"]].groupby(["observation_id", "response_turn_id"])[
    "source_turn_id"].nunique()

check = pd.DataFrame([
    ("Student turns (named or unnamed students)", len(turns)),
    ("Turns whose lines have more than one speaker", mixed_speaker_turns),
    ("Self turns", int((turns["whose"] == "self").sum())),
    ("Other turns", int((turns["whose"] == "other").sum())),
    ("Medium/High Other turns", len(developed_turns)),
    ("Links (unique response turn x source turn, plus unresolved citations)", len(links)),
    ("  valid (source turn found, earlier, different student)", len(valid)),
    ("  invalid or unresolved", int((links["link_status"] != "ok").sum())),
    ("Medium/High responses with a valid link to a Self turn", int(developed_linked_to_self)),
    ("Medium/High responses with valid links to more than one source turn", int((multi_source > 1).sum())),
    ("Medium/High responses with no valid link to any Self turn",
     int(len(developed_turns) - developed_linked_to_self)),
], columns=["check", "count"])
check = pd.concat([check, links.groupby("link_status").size().rename("count").rename_axis("check")
                   .reset_index().assign(check=lambda d: "  status: " + d["check"])], ignore_index=True)
check.to_csv(OUT / "figure1_data_checks.csv", index=False)
print(check.to_string(index=False))
print("Valid links by source Whose:", valid["source_whose"].value_counts().to_dict())

# ---------------------------------------------------------------------------------------------------------------
# 3. Student-observation table and the shared sample
# ---------------------------------------------------------------------------------------------------------------
named_turns = turns[turns["role"] == "Student"]
records = []
for (o, student), group in named_turns.groupby(["observation_id", "student"]):
    records.append({"observation_id": o, "classroom": classroom_of[o], "student": student,
                    "partner_names": ", ".join(sorted(named_students[o] - {student})),
                    "n_student_turns": len(group), "n_self_turns": int((group["whose"] == "self").sum())})
records = pd.DataFrame(records)

# Option 1, original: as computed in the A5 notebook (section 7). A developed response counts once per source
# student; the cited row may be any line of that student (not only a Self turn), and the responder may be the
# unnamed student. This reproduces the original Figure 1.
original_links = links[~links["link_status"].isin(["no_row_id", "row_not_in_observation", "source_is_responder"])
                       & (links["source_role"] == "Student")]
original = (original_links[original_links["response_developed"]]
            .drop_duplicates(["observation_id", "response_turn_id", "source_student"])
            .groupby(["observation_id", "source_student"]).size().rename("n_developed_responses_received"))

# Option 1, corrected: unique developed response turns with a valid link to one of the student's Self turns.
corrected = (valid_to_self[valid_to_self["response_developed"]]
             .drop_duplicates(["observation_id", "response_turn_id", "source_student"])
             .groupby(["observation_id", "source_student"]).size()
             .rename("n_developed_responses_to_self_turns"))

# Option 2: Self turns with at least one valid Medium/High response from a different student.
ideas = named_turns[named_turns["whose"] == "self"][["observation_id", "classroom", "student", "turn_id",
                                                     "row_ids"]].rename(columns={"turn_id": "source_turn_id",
                                                                                 "row_ids": "source_row_ids"})
developed_links = valid_to_self[valid_to_self["response_developed"]]
per_idea = developed_links.groupby(["observation_id", "source_turn_id"]).agg(
    n_developed_responses_received=("response_turn_id", "nunique"),
    responding_peers=("responder", lambda r: ", ".join(sorted(set(r)))))
ideas = ideas.join(per_idea, on=["observation_id", "source_turn_id"])
ideas["n_developed_responses_received"] = ideas["n_developed_responses_received"].fillna(0).astype(int)
ideas["responding_peers"] = ideas["responding_peers"].fillna("")
ideas["received_developed_uptake"] = (ideas["n_developed_responses_received"] > 0).astype(int)
ideas.to_csv(OUT / "figure1_option2_idea_level.csv", index=False)

with_uptake = ideas.groupby(["observation_id", "student"])["received_developed_uptake"].sum()
records = (records.set_index(["observation_id", "student"])
           .join(original.rename_axis(["observation_id", "student"]))
           .join(corrected.rename_axis(["observation_id", "student"]))
           .join(with_uptake.rename("n_self_turns_with_developed_uptake"))
           .fillna({"n_developed_responses_received": 0, "n_developed_responses_to_self_turns": 0,
                    "n_self_turns_with_developed_uptake": 0})
           .reset_index())
for column in ["n_developed_responses_received", "n_developed_responses_to_self_turns",
               "n_self_turns_with_developed_uptake"]:
    records[column] = records[column].astype(int)
denominator = records["n_self_turns"].replace(0, np.nan)  # a zero denominator is missing, not zero
records["developed_responses_per_idea"] = records["n_developed_responses_received"] / denominator
records["developed_responses_to_self_per_idea"] = records["n_developed_responses_to_self_turns"] / denominator
records["proportion_ideas_with_uptake"] = records["n_self_turns_with_developed_uptake"] / denominator
assert (records["n_self_turns_with_developed_uptake"] <= records["n_self_turns"]).all()
assert records["proportion_ideas_with_uptake"].dropna().between(0, 1).all()

# Reproduction check against the original Figure 1 table.
saved = pd.read_csv(ORIGINAL_FIGURE1).rename(columns={"observation": "observation_id", "speaker": "student"})
reproduced = records.merge(saved, on=["observation_id", "student"], how="outer", indicator=True)
mismatch = reproduced[(reproduced["_merge"] != "both")
                      | (reproduced["n_self_turns"] != reproduced["ideas"])
                      | (reproduced["n_developed_responses_received"] != reproduced["developed"])]
print(f"\nReproduction of the original Figure 1 table: {len(mismatch)} mismatched rows of {len(saved)}")

zero_denominator = int((records["n_self_turns"] == 0).sum())
sample = records[records["n_self_turns"] >= MIN_IDEAS].groupby("student").filter(lambda g: len(g) >= MIN_OBSERVATIONS)
excluded = pd.DataFrame([
    ("named student-observations", len(records)),
    ("  with zero Self turns (metric missing)", zero_denominator),
    (f"  with 1-{MIN_IDEAS - 1} Self turns (below the per-observation minimum)",
     int(records["n_self_turns"].between(1, MIN_IDEAS - 1).sum())),
    (f"  kept: students with >= {MIN_IDEAS} Self turns in >= {MIN_OBSERVATIONS} observations", len(sample)),
], columns=["records", "count"])
excluded.to_csv(OUT / "figure1_sample.csv", index=False)
print(excluded.to_string(index=False))

order = sample.groupby("student")["developed_responses_per_idea"].median().sort_values(ascending=False).index.tolist()
sample = sample.sort_values(["student", "partner_names", "observation_id"])
sample[["observation_id", "classroom", "student", "partner_names", "n_self_turns", "n_developed_responses_received",
        "developed_responses_per_idea", "n_developed_responses_to_self_turns",
        "developed_responses_to_self_per_idea", "n_student_turns"]].to_csv(
    OUT / "figure1_option1_student_observation.csv", index=False)
sample[["observation_id", "classroom", "student", "partner_names", "n_self_turns",
        "n_self_turns_with_developed_uptake", "proportion_ideas_with_uptake"]].to_csv(
    OUT / "figure1_option2_student_observation.csv", index=False)
comparison = sample[["observation_id", "student", "partner_names", "n_self_turns", "n_developed_responses_received",
                     "n_developed_responses_to_self_turns", "n_self_turns_with_developed_uptake"]].assign(
    metric_1_original=sample["developed_responses_per_idea"].round(3),
    metric_1_corrected=sample["developed_responses_to_self_per_idea"].round(3),
    metric_2=sample["proportion_ideas_with_uptake"].round(3))
comparison.to_csv(OUT / "figure1_metric_comparison.csv", index=False)


# ---------------------------------------------------------------------------------------------------------------
# 4. Figures: one facet per focal student, rows = partner set, one dot per student-observation.
# ---------------------------------------------------------------------------------------------------------------
def layout(student):
    """Row positions for one facet: every observation on its own row, grouped under its partner set.

    Pairs come first (alphabetical), then larger groups; within a partner, rows follow observation ID, so both
    options use the same order.
    """
    rows = sample[sample["student"] == student]
    partners = sorted(rows["partner_names"].unique(), key=lambda p: (", " in p, p))
    positions, ticks, y = {}, [], 0.0
    for i, partner in enumerate(partners):
        ids = sorted(rows.loc[rows["partner_names"] == partner, "observation_id"])
        for observation in ids:
            positions[observation] = y
            y += 1
        ticks.append((positions[ids[0]] + positions[ids[-1]]) / 2)
        following = partners[i + 1] if i + 1 < len(partners) else ""
        # Gap between partner sets; a two-line group label needs more room on both sides.
        y += 1.2 if ", " in partner or ", " in following else 0.6
    return rows, partners, positions, ticks, y - 0.6


# Balance the two columns by number of rows, largest facets first.
facet_columns, column_rows = [[], []], [0, 0]
for student in sorted(order, key=lambda s: -(sample["student"] == s).sum()):
    target = int(column_rows[1] < column_rows[0])
    facet_columns[target].append(student)
    column_rows[target] += (sample["student"] == student).sum() + 2


def draw(metric, count, title, xlabel, path, xlim, percent=False):
    heights = [[layout(s)[4] + 2.2 for s in col] for col in facet_columns]
    figure = plt.figure(figsize=(6.3, 0.125 * max(sum(h) for h in heights) + 0.6))
    grid = figure.add_gridspec(1, 2, wspace=0.62)
    for c, students in enumerate(facet_columns):
        sub = grid[c].subgridspec(len(students), 1, height_ratios=heights[c], hspace=0.9)
        for r, student in enumerate(students):
            axis = figure.add_subplot(sub[r])
            rows, partners, positions, ticks, bottom = layout(student)
            colors = dict(zip(partners, plt.get_cmap("tab10").colors))
            for _, point in rows.iterrows():
                x, y = point[metric], positions[point["observation_id"]]
                axis.scatter(x, y, s=13, color=colors[point["partner_names"]], zorder=3, edgecolor="white",
                             linewidth=0.4)
                axis.annotate(f"{short_id(point['observation_id'])}  {int(point[count])}/{int(point['n_self_turns'])}",
                              (x, y), textcoords="offset points", xytext=(4, -1.8), fontsize=5, color="#444444")
            axis.set_yticks(ticks)
            axis.set_yticklabels([p.replace(", ", ",\n", 1) if ", " in p else p for p in partners], fontsize=5.6,
                                 linespacing=0.95)
            axis.set_ylim(bottom + 0.6, -0.6)
            axis.set_xlim(*xlim)
            if percent:
                axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
            axis.grid(axis="x", color="#eeeeee", linewidth=0.5, zorder=0)
            axis.spines[["top", "right"]].set_visible(False)
            axis.set_title(f"{student} ({len(rows)} obs., {int(rows['n_self_turns'].sum())} Self turns)",
                           loc="left", fontsize=7, pad=2)
            axis.tick_params(axis="x", labelsize=6, pad=1)
            if r == len(students) - 1:
                axis.set_xlabel(xlabel)
    figure.suptitle(title, fontsize=8.5, y=0.995)
    figure.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    figure.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)


upper = float(np.ceil(sample["developed_responses_per_idea"].max() * 10 + 1) / 10)
draw("developed_responses_per_idea", "n_developed_responses_received",
     "Peer uptake varies across observations for the same student",
     "Developed peer responses received per idea offered", OUT / "figure1_option1", (-0.05, upper))
draw("proportion_ideas_with_uptake", "n_self_turns_with_developed_uptake",
     "The proportion of ideas taken up varies across observations",
     "Ideas receiving developed peer uptake (%)", OUT / "figure1_option2", (-0.03, 1.08), percent=True)

# ---------------------------------------------------------------------------------------------------------------
# 5. Spread, small-denominator check, and real cases for manual review
# ---------------------------------------------------------------------------------------------------------------
spread = []
for metric in ["developed_responses_per_idea", "developed_responses_to_self_per_idea", "proportion_ideas_with_uptake"]:
    for minimum in [MIN_IDEAS, 10]:
        kept = records[records["n_self_turns"] >= minimum].groupby("student").filter(
            lambda g: len(g) >= MIN_OBSERVATIONS)
        by_student = kept.groupby("student")[metric]
        within, between = by_student.std().mean(), by_student.mean().std()
        spread.append({"metric": metric, "min_self_turns": minimum, "students": kept["student"].nunique(),
                       "records": len(kept), "mean_within_student_sd": round(within, 3),
                       "sd_of_student_means": round(between, 3), "ratio": round(within / between, 2),
                       "range_of_student_ranges": f"{(by_student.max() - by_student.min()).min():.2f}-"
                                                  f"{(by_student.max() - by_student.min()).max():.2f}"})
spread = pd.DataFrame(spread)
spread.to_csv(OUT / "figure1_spread.csv", index=False)
print("\n" + spread.to_string(index=False))

in_sample = ideas.merge(sample[["observation_id", "student"]], on=["observation_id", "student"])
cases = []
for label, rows in [("no developed response", in_sample[in_sample["n_developed_responses_received"] == 0]),
                    ("one developed response", in_sample[in_sample["n_developed_responses_received"] == 1]),
                    ("several developed responses", in_sample[in_sample["n_developed_responses_received"] >= 2])]:
    if len(rows):
        row = rows.iloc[0]
        cases.append({"case": label, "observation_id": row["observation_id"], "source_turn_id": row["source_turn_id"],
                      "student": row["student"], "source_row_ids": row["source_row_ids"],
                      "responses": "; ".join(f"{r.response_turn_id} {r.responder} {r.response_level}"
                                             for r in developed_links[(developed_links["observation_id"] == row["observation_id"])
                                                                      & (developed_links["source_turn_id"] == row["source_turn_id"])].itertuples())})
multi = valid[valid["response_developed"]].groupby(["observation_id", "response_turn_id"]).filter(
    lambda g: g["source_turn_id"].nunique() > 1)
if len(multi):
    first = multi.groupby(["observation_id", "response_turn_id"]).ngroup() == 0
    group = multi[first]
    cases.append({"case": "one response, several source turns", "observation_id": group["observation_id"].iloc[0],
                  "source_turn_id": ", ".join(group["source_turn_id"]), "student": ", ".join(group["source_student"]),
                  "source_row_ids": ", ".join(group["source_row"]),
                  "responses": f"{group['response_turn_id'].iloc[0]} {group['responder'].iloc[0]} "
                               f"{group['response_level'].iloc[0]}"})
cases = pd.DataFrame(cases)
cases.to_csv(OUT / "figure1_case_checks.csv", index=False)
print("\n" + cases.to_string(index=False))

print(f"\nSample: {sample['student'].nunique()} students, {sample['observation_id'].nunique()} observations, "
      f"{len(sample)} student-observations, {int(sample['n_self_turns'].sum())} Self turns, "
      f"{int(sample['n_developed_responses_received'].sum())} developed responses (original count), "
      f"{int(sample['n_developed_responses_to_self_turns'].sum())} to Self turns, "
      f"{int(sample['n_self_turns_with_developed_uptake'].sum())} Self turns with developed uptake")
