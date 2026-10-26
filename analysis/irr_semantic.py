from pathlib import Path

import pandas as pd

REPOSITORY = Path(__file__).resolve().parent.parent
CODING_FOLDER = REPOSITORY / "Data" / "human_coding"
OUTPUT_FOLDER = CODING_FOLDER / "normalized"

CODER_FILES = {
    "Vishal": CODING_FOLDER / "codes_OBS_26-0498_Vishal.csv",
    "Caesar": CODING_FOLDER / "humancodes_OBS_26_0498_Caesar.csv",
}
SEGMENTS = {"c", "d"}
REFERENCE_CODER = "Vishal"
ADULT_PREFIX = "Ms."
COORDINATION_ROWS = ["c2", "c3", "c4", "c7", "c33", "c35", "c41", "c44", "c45", "c53"]
TEACHER_RESPONSE_LEVELS = {"High": "Fully detailed", "Medium": "Some detail", "Low": "No detail"}
CODED_WHOSE = {"Self", "Other"}


def load_codes(path):
    codes = pd.read_csv(path, keep_default_na=False, dtype=str)
    codes = codes[codes["row"].str[0].isin(SEGMENTS)].reset_index(drop=True)
    codes["is_adult"] = codes["speaker"].str.startswith(ADULT_PREFIX)
    return codes


def clear_code(codes, index, coder, rule, log):
    log.append({"coder": coder, "row": codes.loc[index, "row"], "rule": rule,
                "before": f"{codes.loc[index, 'whose']} / {codes.loc[index, 'level']}", "after": "not coded"})
    codes.loc[index, ["whose", "level"]] = ""


def normalize(codes, coder, log):
    codes = codes.copy()
    for index in codes.index:
        if codes.loc[index, "is_adult"] and (codes.loc[index, "whose"] or codes.loc[index, "level"]):
            clear_code(codes, index, coder, "Adult lines are not coded", log)

    for index in codes.index[1:]:
        follows_adult = codes.loc[index - 1, "is_adult"] and codes.loc[index - 1, "row"][0] == codes.loc[index, "row"][0]
        if follows_adult and not codes.loc[index, "is_adult"] and codes.loc[index, "whose"] == "Other":
            old_level = codes.loc[index, "level"]
            new_level = TEACHER_RESPONSE_LEVELS.get(old_level, old_level)
            log.append({"coder": coder, "row": codes.loc[index, "row"], "rule": "Answers to the teacher are Self",
                        "before": f"Other / {old_level}", "after": f"Self / {new_level}"})
            codes.loc[index, ["whose", "level"]] = ["Self", new_level]

    for index in codes.index[codes["row"].isin(COORDINATION_ROWS)]:
        if codes.loc[index, "whose"] or codes.loc[index, "level"]:
            clear_code(codes, index, coder, "Coordination moves and starter prompts are not coded", log)

    for index in codes.index[codes["whose"] == "Unclear"]:
        clear_code(codes, index, coder, "Unclear is treated as not coded", log)
    return codes


def build_turns(reference):
    turns, open_turns = [], {}
    for index, record in reference.iterrows():
        if record["whose"] in CODED_WHOSE | {"Unclear"}:
            open_turns.setdefault(record["speaker"], []).append(index)
            if record["level"]:
                turns.append(open_turns.pop(record["speaker"]))
    return turns


def turn_code(codes, indexes):
    whose = [codes.loc[i, "whose"] for i in indexes if codes.loc[i, "whose"]]
    level = [codes.loc[i, "level"] for i in indexes if codes.loc[i, "level"]]
    return (whose[-1] if whose else ""), (level[-1] if level else "")


def cohens_kappa(first, second):
    first, second = list(first), list(second)
    total = len(first)
    if total == 0:
        return float("nan")
    observed = sum(a == b for a, b in zip(first, second)) / total
    expected = sum((first.count(label) / total) * (second.count(label) / total) for label in set(first) | set(second))
    return (observed - expected) / (1 - expected) if expected < 1 else float("nan")


def main():
    raw = {coder: load_codes(path) for coder, path in CODER_FILES.items()}
    first, second = raw.values()
    if list(first["row"]) != list(second["row"]):
        raise ValueError("The two codes files do not cover the same rows in the same order.")

    log = []
    normalized = {coder: normalize(codes, coder, log) for coder, codes in raw.items()}
    other_coder = next(coder for coder in CODER_FILES if coder != REFERENCE_CODER)

    turns = build_turns(raw[REFERENCE_CODER])
    rows_in_turns = {index for turn in turns for index in turn}
    extra_units = [[index] for index in normalized[other_coder].index
                   if index not in rows_in_turns and normalized[other_coder].loc[index, "whose"] in CODED_WHOSE]
    units = sorted(turns + extra_units, key=lambda unit: unit[-1])

    rows = raw[REFERENCE_CODER]["row"]
    comparison = []
    for unit in units:
        reference_whose, reference_level = turn_code(normalized[REFERENCE_CODER], unit)
        other_whose, other_level = turn_code(normalized[other_coder], unit)
        coded_by_both = reference_whose in CODED_WHOSE and other_whose in CODED_WHOSE
        same_whose = coded_by_both and reference_whose == other_whose
        level_compared = same_whose and bool(reference_level) and bool(other_level)
        comparison.append({
            "turn": f"{rows[unit[0]]}-{rows[unit[-1]]}" if len(unit) > 1 else rows[unit[0]],
            "rows": " ".join(rows[i] for i in unit),
            "speaker": raw[REFERENCE_CODER].loc[unit[-1], "speaker"],
            f"{REFERENCE_CODER.lower()}_whose": reference_whose,
            f"{REFERENCE_CODER.lower()}_level": reference_level,
            f"{other_coder.lower()}_whose": other_whose,
            f"{other_coder.lower()}_level": other_level,
            "coded_by_both": coded_by_both,
            "whose_agree": same_whose if coded_by_both else "",
            "level_compared": level_compared,
            "level_agree": (reference_level == other_level) if level_compared else "",
        })
    comparison = pd.DataFrame(comparison)

    both = comparison[comparison["coded_by_both"]]
    levels = comparison[comparison["level_compared"]]
    reference_key, other_key = REFERENCE_CODER.lower(), other_coder.lower()
    coded_by_one = (comparison[f"{reference_key}_whose"].isin(CODED_WHOSE) != comparison[f"{other_key}_whose"].isin(CODED_WHOSE)).sum()
    summary = pd.DataFrame([
        {"measure": "Whose (turns coded by both)", "units": len(both),
         "agreement": (both[f"{reference_key}_whose"] == both[f"{other_key}_whose"]).mean(),
         "kappa": cohens_kappa(both[f"{reference_key}_whose"], both[f"{other_key}_whose"])},
        {"measure": "Level (turns with the same Whose and a level from both)", "units": len(levels),
         "agreement": (levels[f"{reference_key}_level"] == levels[f"{other_key}_level"]).mean(),
         "kappa": cohens_kappa(levels[f"{reference_key}_level"], levels[f"{other_key}_level"])},
        {"measure": "Codability (share of turns both coders agreed to code or not code)", "units": len(comparison),
         "agreement": 1 - coded_by_one / len(comparison),
         "kappa": float("nan")},
    ])

    OUTPUT_FOLDER.mkdir(exist_ok=True)
    for coder, codes in normalized.items():
        codes.drop(columns="is_adult").to_csv(OUTPUT_FOLDER / f"codes_OBS_26-0498_cd_{coder}_normalized.csv", index=False)
    pd.DataFrame(log).to_csv(OUTPUT_FOLDER / "normalization_log_OBS_26-0498_cd.csv", index=False)
    comparison.to_csv(OUTPUT_FOLDER / "irr_turns_OBS_26-0498_cd.csv", index=False)
    summary.round(3).to_csv(OUTPUT_FOLDER / "irr_summary_OBS_26-0498_cd.csv", index=False)

    print(f"{len(log)} normalizations applied (see normalization_log_OBS_26-0498_cd.csv)")
    print(summary.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
