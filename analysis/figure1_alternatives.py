"""Figure 1 alternatives A (dot plot by partner) and B (outcome of every idea). Run after analysis/figure1_revision.py, from the repository root."""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

MIN_IDEAS = 5
OUT = Path("results/figure1_revision")  # reads the audited tables written by analysis/figure1_revision.py

ideas = pd.read_csv(OUT / "figure1_option2_idea_level.csv", keep_default_na=False)
links = pd.read_csv(OUT / "figure1_link_audit.csv", keep_default_na=False)
sample = pd.read_csv(OUT / "figure1_option2_student_observation.csv", keep_default_na=False)

# Each Self turn: developed (>= 1 valid Medium/High link), acknowledged only (valid links, all Low), or not taken up.
responded = set(zip(*[links.loc[(links["link_status"] == "ok") & (links["source_whose"] == "self"), c]
                      for c in ["observation_id", "source_turn_id"]]))
ideas["outcome"] = [
    "developed" if developed else ("acknowledged only" if (o, t) in responded else "not taken up")
    for developed, o, t in zip(ideas["received_developed_uptake"] == 1, ideas["observation_id"], ideas["source_turn_id"])
]
kept = (
    ideas.groupby(["observation_id", "student"])["outcome"].value_counts().unstack(fill_value=0)
    .reindex(columns=["developed", "acknowledged only", "not taken up"], fill_value=0).reset_index()
    .merge(sample[["observation_id", "student", "partner_names"]], on=["observation_id", "student"])
    .rename(columns={"observation_id": "observation", "student": "speaker", "partner_names": "partners"})
)
kept["ideas"] = kept[["developed", "acknowledged only", "not taken up"]].sum(axis=1)
kept["share_developed"] = kept["developed"] / kept["ideas"]
assert len(kept) == len(sample)
order = kept.groupby("speaker")["share_developed"].median().sort_values().index.tolist()
n_students, n_obs, n_ideas = len(order), kept["observation"].nunique(), int(kept["ideas"].sum())
print(f"{n_students} students, {len(kept)} student-observations in {n_obs} observations, {n_ideas} ideas")

# One consistent color per partner (group); multi-partner groups share a gray.
partner_labels = sorted(p for p in kept["partners"].unique() if "," not in p)
palette = [c for i, c in enumerate(plt.get_cmap("tab20").colors) if i not in (14, 15)]  # no grays
partner_color = {p: palette[i % len(palette)] for i, p in enumerate(partner_labels)}
GROUP_COLOR = "#7f7f7f"


def color_of(partners):
    return partner_color.get(partners, GROUP_COLOR)


# Option A: dot plot, share of ideas developed, color = partner, size = ideas offered.
figure, axis = plt.subplots(figsize=(10, 0.8 * len(order) + 1.6))
for y, student in enumerate(order):
    rows = kept[kept["speaker"] == student]
    axis.hlines(y, rows["share_developed"].min(), rows["share_developed"].max(), color="#d9d9d9", zorder=1)
    for is_group, marker in [(False, "o"), (True, "D")]:
        part = rows[rows["partners"].str.contains(",") == is_group]
        axis.scatter(part["share_developed"], [y] * len(part), s=part["ideas"] * 9, zorder=3, alpha=0.9, marker=marker,
                     color=[color_of(p) for p in part["partners"]], edgecolor="white", linewidth=0.8)
axis.set_yticks(range(len(order)))
axis.set_yticklabels([f"{s} ({(kept['speaker'] == s).sum()} obs., "
                      f"{int(kept.loc[kept['speaker'] == s, 'ideas'].sum())} ideas)" for s in order], fontsize=9)
axis.set_xlim(-0.03, 1.03)
axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
axis.set_xlabel("Share of the student's ideas that a partner developed (Medium or High)")
axis.spines[["top", "right", "left"]].set_visible(False)
partner_handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=8, color=partner_color[p], label=p)
                   for p in partner_labels]
partner_handles.append(plt.Line2D([], [], marker="D", linestyle="", markersize=7, color=GROUP_COLOR,
                                  label="Group of 3–4"))
legend = axis.legend(handles=partner_handles, title="Partner", frameon=False, fontsize=8, title_fontsize=9,
                     loc="upper left", bbox_to_anchor=(1.01, 1))
axis.add_artist(legend)
size_handles = [plt.scatter([], [], s=n * 9, color="#bbbbbb", label=f"{n} ideas") for n in (5, 15, 30)]
axis.legend(handles=size_handles, title="Ideas offered", frameon=False, fontsize=8, title_fontsize=9,
            loc="lower left", bbox_to_anchor=(1.01, 0), labelspacing=1.2)
axis.set_title("The share of a student's ideas developed by partners varies across observations",
               fontsize=10, pad=12)
figure.text(0.01, -0.02, f"N = {n_students} students, {len(kept)} student-observations ({n_obs} observations), "
            f"{n_ideas} ideas. Each dot is one observation; only observations where the student offered "
            f"at least {MIN_IDEAS} ideas.", fontsize=8, color="#555555")
figure.tight_layout()
figure.savefig(OUT / "figure1_optionA.png", dpi=200, bbox_inches="tight")
plt.close(figure)

# Option B: 100% stacked bars of what happened to each student's ideas, one panel per student.
COLORS = {"developed": "#2f5d9b", "acknowledged only": "#9db4d3", "not taken up": "#e6e6e6"}
widths = [(kept["speaker"] == s).sum() for s in order[::-1]]
rows_of_panels = [order[::-1][:4], order[::-1][4:]]
figure = plt.figure(figsize=(14, 8.4))
grid = figure.add_gridspec(2, 1, hspace=0.75)
for r, students in enumerate(rows_of_panels):
    sub = grid[r].subgridspec(1, len(students), width_ratios=[(kept["speaker"] == s).sum() + 0.6 for s in students],
                              wspace=0.15)
    for c, student in enumerate(students):
        axis = figure.add_subplot(sub[c])
        rows = kept[kept["speaker"] == student].sort_values(["partners", "share_developed"])
        x = np.arange(len(rows))
        bottom = np.zeros(len(rows))
        for category, color in COLORS.items():
            share = (rows[category] / rows["ideas"]).values
            axis.bar(x, share, bottom=bottom, color=color, width=0.75, label=category)
            bottom += share
        for position, (_, row) in zip(x, rows.iterrows()):
            axis.text(position, 1.02, f"n={int(row['ideas'])}", ha="center", va="bottom", fontsize=6.5, color="#555555")
        axis.set_xticks(x)
        axis.set_xticklabels([p.replace(", ", "\n") for p in rows["partners"]], rotation=90, fontsize=7)
        axis.set_ylim(0, 1.1)
        axis.set_yticks([0, 0.5, 1])
        axis.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        if c:
            axis.set_yticklabels([])
        axis.set_title(student, fontsize=10)
        axis.spines[["top", "right"]].set_visible(False)
handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in COLORS.values()]
figure.legend(handles, ["Developed by a partner (Medium or High)", "Acknowledged only (Low)", "Not taken up"],
              loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.03), fontsize=9)
figure.suptitle("What happened to each student's ideas, by observation and partner",
                fontsize=11, y=0.98)
figure.text(0.01, -0.07, f"N = {n_students} students, {len(kept)} student-observations ({n_obs} observations), "
            f"{n_ideas} ideas; n above each bar = ideas offered in that observation.", fontsize=8, color="#555555")
figure.savefig(OUT / "figure1_optionB.png", dpi=200, bbox_inches="tight")
plt.close(figure)

summary = kept.groupby("speaker").agg(obs=("observation", "size"), ideas=("ideas", "sum"),
                                       min=("share_developed", "min"), median=("share_developed", "median"),
                                       max=("share_developed", "max")).round(2)
print(summary.loc[order].to_string())
for student in ["Miguel", "Milagros", "Adam"]:
    rows = kept[kept["speaker"] == student].sort_values("share_developed")
    print(student, rows[["observation", "partners", "ideas", "developed", "acknowledged only", "not taken up",
                         "share_developed"]].round(2).to_string(index=False))
