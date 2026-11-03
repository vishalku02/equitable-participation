import argparse
import base64
import csv
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
import pandas as pd
from pypdf import PdfWriter

REPOSITORY = Path(__file__).resolve().parent.parent
PROMPTS = REPOSITORY / "llm_prompts"
TRANSCRIPT = REPOSITORY / "Data" / "Track A" / "all_observations_combined.csv"
METADATA = REPOSITORY / "Data" / "Track A" / "observation_metadata.csv"
LESSON_MAP = PROMPTS / "observation_lessons.csv"
CURRICULUM = REPOSITORY / "Data" / "curriculum"
LESSON_PAGES = ["teacher", "student", "preparation"]
PRIVATE_OUTPUT = REPOSITORY / "Data" / "llm_coding" / "enhanced_v3"
PUBLIC_OUTPUT = REPOSITORY / "results" / "llm_enhanced_full"

MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 64000
UNNAMED_STUDENT = "Other"
MODEL_COLUMNS = ["row", "speaker", "turn", "whose", "builds_on", "level", "reason"]
OUTPUT_COLUMNS = ["observation"] + MODEL_COLUMNS
ALLOWED_WHOSE = {"Self", "Other", "Unclear / not coded", "N/A"}
ROW_SCHEMA = {
    "type": "object",
    "properties": {column: {"type": "string"} for column in MODEL_COLUMNS} | {"whose": {"type": "string", "enum": sorted(ALLOWED_WHOSE)}},
    "required": MODEL_COLUMNS,
    "additionalProperties": False,
}
OUTPUT_FORMAT = {"format": {"type": "json_schema", "schema": {
    "type": "object", "properties": {"rows": {"type": "array", "items": ROW_SCHEMA}},
    "required": ["rows"], "additionalProperties": False}}}


def load_transcript(observation):
    transcript = pd.read_csv(TRANSCRIPT, dtype=str, keep_default_na=False)
    lines = transcript[transcript["observation"] == observation].copy()
    if lines.empty:
        raise ValueError(f"{observation} is not in the transcript file.")
    lines["line_order"] = lines["line_order"].astype(int)
    lines = lines.sort_values("line_order")
    lines["row"] = lines["segment"] + lines["#"]
    return lines.rename(columns={"named_language": "language"})[["row", "speaker", "language", "dialogue"]]


def student_names(observation):
    metadata = pd.read_csv(METADATA, dtype=str, keep_default_na=False)
    metadata["observation"] = metadata["obs_index"].str.strip().str.replace(r"^OBS-", "OBS_", regex=True)
    names = metadata.loc[metadata["observation"] == observation, "student_pseudonyms"]
    return re.findall(r"'([^']+)'", names.iloc[0]) if len(names) else []


def describe_speakers(observation, lines):
    speaking_students = [name for name in student_names(observation) if name in set(lines["speaker"])]
    if not speaking_students:
        raise ValueError(f"{observation} has no named students in the metadata who speak in the transcript.")
    description = f"The students in this transcript are {', '.join(speaking_students)}."
    if UNNAMED_STUDENT in set(lines["speaker"]):
        description += f' The speaker "{UNNAMED_STUDENT}" is a student whose name is not recorded.'
    return description + " Every other speaker is an adult."


TASK_NOTE = ("The Illustrative Mathematics lesson this class was working on is attached as one PDF: "
             "the teacher guide, then the student edition, then the teacher preparation page. "
             "The pages were printed from the curriculum websites, so ignore site navigation and menus.")


def lesson_pdf(observation):
    lessons = pd.read_csv(LESSON_MAP, dtype=str, keep_default_na=False).set_index("observation")
    lesson = lessons.loc[observation, "lesson"]
    merged = PdfWriter()
    for page in LESSON_PAGES:
        merged.append(CURRICULUM / f"{lesson}_{page}.pdf")
    buffer = io.BytesIO()
    merged.write(buffer)
    return {"type": "document", "title": lesson,
            "source": {"type": "base64", "media_type": "application/pdf",
                       "data": base64.standard_b64encode(buffer.getvalue()).decode()}}


def build_prompt(observation, lines):
    template = (PROMPTS / "enhanced_prompt.txt").read_text()
    fields = {
        "{lens}": (PROMPTS / "lens.txt").read_text().strip(),
        "{task}": TASK_NOTE,
        "{codebook}": (PROMPTS / "codebook.md").read_text().strip(),
        "{speakers}": describe_speakers(observation, lines),
        "{transcript}": lines.to_csv(index=False).strip(),
    }
    for placeholder, value in fields.items():
        template = template.replace(placeholder, value)
    return template


def call_model(lesson, prompt):
    client = anthropic.Anthropic()
    content = [lesson, {"type": "text", "text": prompt}]
    with client.messages.stream(model=MODEL, max_tokens=MAX_TOKENS, output_config=OUTPUT_FORMAT,
                                messages=[{"role": "user", "content": content}]) as stream:
        response = stream.get_final_message()
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"The model stopped with stop_reason={response.stop_reason}.")
    return "".join(block.text for block in response.content if block.type == "text"), response.usage


def parse_codes(text, lines):
    if text.lstrip().startswith("{"):
        return check_codes(pd.DataFrame(json.loads(text)["rows"], columns=MODEL_COLUMNS), lines)
    start = text.find("row,speaker,turn")
    if start == -1:
        raise ValueError("The response has no CSV header.")
    csv_text = text[start:].split("```")[0]
    header, *records = [record for record in csv.reader(io.StringIO(csv_text)) if record]
    if header != MODEL_COLUMNS:
        raise ValueError(f"Unexpected columns: {header}")
    last = len(MODEL_COLUMNS) - 1
    rows = [record[:last] + [",".join(record[last:])] for record in records]
    if any(len(record) < len(MODEL_COLUMNS) for record in rows):
        raise ValueError("A coded row has too few fields.")
    return check_codes(pd.DataFrame(rows, columns=MODEL_COLUMNS), lines)


def check_codes(codes, lines):
    unknown = set(codes["whose"]) - ALLOWED_WHOSE
    if unknown:
        raise ValueError(f"Unexpected Whose values: {unknown}")
    if codes["row"].duplicated().any() or set(codes["row"]) != set(lines["row"]):
        raise ValueError("The coded rows do not match the transcript rows.")
    return codes.set_index("row").loc[list(lines["row"])].reset_index()


def save_codes(observation, text, lines):
    codes = parse_codes(text, lines)
    codes.insert(0, "observation", observation)
    file_name = f"llm_enhanced_{observation}.csv"
    codes[OUTPUT_COLUMNS].to_csv(PRIVATE_OUTPUT / file_name, index=False, quoting=csv.QUOTE_MINIMAL)
    codes.drop(columns="reason").to_csv(PUBLIC_OUTPUT / file_name, index=False)
    return codes


def run(observation, from_saved=False):
    lines = load_transcript(observation)
    PRIVATE_OUTPUT.mkdir(parents=True, exist_ok=True)
    PUBLIC_OUTPUT.mkdir(parents=True, exist_ok=True)
    response_file = PRIVATE_OUTPUT / f"response_{observation}.txt"
    if from_saved:
        codes = save_codes(observation, response_file.read_text(), lines)
        print(f"{observation}: {len(codes)} rows parsed from the saved response", flush=True)
        return

    prompt = build_prompt(observation, lines)
    (PRIVATE_OUTPUT / f"prompt_{observation}.txt").write_text(prompt)
    text, usage = call_model(lesson_pdf(observation), prompt)
    response_file.write_text(text)
    codes = save_codes(observation, text, lines)
    print(f"{observation}: {len(codes)} rows coded, {usage.input_tokens} input and {usage.output_tokens} output tokens", flush=True)


def run_safely(observation, from_saved=False):
    try:
        run(observation, from_saved)
    except Exception as error:
        print(f"{observation}: FAILED ({error})", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Code whole observations with the enhanced LLM prompt.")
    parser.add_argument("observations", nargs="+", help="Observation IDs, for example OBS_26-0498")
    parser.add_argument("--workers", type=int, default=4, help="Observations coded at the same time")
    parser.add_argument("--from-saved", action="store_true", help="Parse saved responses instead of calling the model")
    arguments = parser.parse_args()
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        list(pool.map(lambda observation: run_safely(observation, arguments.from_saved), arguments.observations))


if __name__ == "__main__":
    main()
