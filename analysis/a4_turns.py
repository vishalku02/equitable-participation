"""Shared loading, label cleaning, and turn rules for the two A4 notebooks."""

from pathlib import Path

import pandas as pd

from irr_semantic import build_turns, normalize

REPOSITORY = Path(__file__).resolve().parent.parent
DATA_FOLDER = REPOSITORY / "results" / "comparison_data"
NORMALIZED_FOLDER = REPOSITORY / "Data" / "human_coding" / "normalized"

TEST = "OBS_26-0498"
CALIBRATION = "OBS_26-0515"
OBSERVATIONS = [TEST, CALIBRATION]
SAMPLE_LABELS = {TEST: "OBS_26-0498 c-d (test)", CALIBRATION: "OBS_26-0515 a-b (calibration)"}
CODERS = ["Vishal", "Caesar"]

SELF_LEVELS = ["fully detailed", "some detail", "wrong detail", "no detail"]
OTHER_LEVELS = ["high", "medium", "low"]
CODED_WHOSE = ["self", "other"]
NOT_CODED = {"", "n/a", "unclear", "unclear / not coded"}
CANONICAL_LABELS = {label.lower(): label for label in [
    "Self", "Other", "N/A", "Unclear",
    "Fully detailed", "Some detail", "Wrong detail", "No detail", "High", "Medium", "Low",
]}


def clean(label):
    label = str(label).strip().lower()
    return "" if label in NOT_CODED else label


def canonical(label):
    # The IRR rules expect the capitalization used in the codebook.
    label = str(label).strip()
    return CANONICAL_LABELS.get(label.lower(), label)


def last_code(labels):
    labels = [label for label in labels if label]
    return labels[-1] if labels else ""


def load_table():
    return pd.read_csv(DATA_FOLDER / "analysis_table.csv", keep_default_na=False, dtype=str)


def load_gca_units():
    return pd.concat([pd.read_csv(DATA_FOLDER / f"gca_merged_units_{observation}.csv")
                      for observation in OBSERVATIONS], ignore_index=True)


def observation_lines(table, observation):
    return table[table["observation"] == observation].reset_index(drop=True)


def coder_codes(table, observation, coder, log):
    """A coder's raw and normalized codes for student lines, using the IRR script's rules."""
    lines = observation_lines(table, observation)
    key = coder.lower()
    raw = pd.DataFrame({
        "row": lines["row"],
        "speaker": lines["speaker"],
        "whose": lines[f"{key}_whose"].map(canonical),
        "level": lines[f"{key}_level"].map(canonical),
        "is_adult": lines["is_adult"] == "True",
    })
    # Normalize with adult lines present, since one rule looks at the line before.
    normalized = normalize(raw, coder, log)
    students = ~raw["is_adult"]
    return (raw[students].drop(columns="is_adult").reset_index(drop=True),
            normalized[students].drop(columns="is_adult").reset_index(drop=True))


def adjudicated_codes(table, observation):
    """The final codes, plus turn boundaries that also end a turn where Vishal recorded a Level.

    The comparison tool fills a final value only when both coders agree, so a final Level
    is blank wherever we disagreed and did not resolve it. Without Vishal's boundaries,
    those lines would merge into long turns that neither of us drew.
    """
    lines = observation_lines(table, observation)
    lines = lines[lines["is_adult"] == "False"].reset_index(drop=True)
    codes = pd.DataFrame({
        "row": lines["row"],
        "speaker": lines["speaker"],
        "whose": lines["human_final_whose"],
        "level": lines["human_final_level"],
    })
    boundaries = codes.copy()
    missing = (boundaries["level"] == "") & (lines["vishal_level"].map(clean) != "")
    boundaries.loc[missing, "level"] = "turn end"
    return boundaries, codes


def segment_turns(boundaries):
    # build_turns runs over the whole file, so run it per segment to keep turns within segments.
    turns = []
    for _, segment in boundaries.groupby(boundaries["row"].str[0], sort=False):
        segment = segment.reset_index(drop=True)
        turns += [list(segment.loc[turn, "row"]) for turn in build_turns(segment)]
    return turns


def make_reference(boundaries, codes):
    codes = codes.set_index("row")
    return {
        "turns": segment_turns(boundaries),
        "speaker": codes["speaker"],
        "whose": codes["whose"].map(clean),
        "level": codes["level"].map(clean),
    }


def llm_labels(table, observation):
    lines = observation_lines(table, observation).set_index("row")
    labels = {column: lines[column].map(clean) for column in
              ["basic_explanation", "basic_peer_engagement", "enhanced_whose", "enhanced_level"]}
    labels["enhanced_turn"] = lines["enhanced_turn"]
    labels["gca_unit"] = lines["gca_unit"]
    labels["enhanced_turn_level"] = labels["enhanced_level"].groupby(lines["enhanced_turn"]).agg(last_code)
    return labels


def enhanced_code(labels, rows):
    """Last Whose within the turn, and the Level of the enhanced turn containing its last line.

    The enhanced prompt writes Level only on the last line of its own turns, which can
    fall after the end of the human turn.
    """
    turn_ids = [turn for turn in labels["enhanced_turn"][rows] if turn]
    level = labels["enhanced_turn_level"][turn_ids[-1]] if turn_ids else ""
    return last_code(labels["enhanced_whose"][rows]), level
