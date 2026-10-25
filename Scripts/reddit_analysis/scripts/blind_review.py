"""
blind_review.py
===============
ComputerVision_Sentinel | Check both review files by hand, blind, then record who decided

PURPOSE
-------
Two review files in manual_review/ feed the Reddit analysis:

  env_cue_validation_heldout.csv   150 cue matches, 30 per cue: does the matched word
                                   really describe that environmental cue? (gives the
                                   cue precision in 05_audits/)
  location_other_city_review.csv   144 place matches whose text also names another
                                   city: is the place the Saskatoon one (keep) or the
                                   other city's (exclude)?

Every row needs a judgment made by a person who has not seen the earlier answer.
"make" writes both lists without the earlier answers. "apply" checks the filled
lists and writes the answers, the reviewer's name and the date into the two review
files, in place of what was there.

HOW TO JUDGE
------------
env_cue_blind.csv, column correct_1_or_0:
  1   the matched word describes the cue for the place being talked about
  0   it means something else (car lights, candles, a colour, catching a cold, ...)
      lighting      how lit or dark a place is (street lights, darkness)
      noise         sound in the surroundings (loud, quiet, yelling)
      weather       weather or ground conditions (snow, ice, cold, rain)
      time_of_day   night or late-night timing
      people        how busy or empty a place is, or who is around it
other_city_blind.csv, column decision_keep_or_exclude:
  keep      the matched place is the Saskatoon one
  exclude   it is the same-named place in another city (e.g. downtown Regina)
The note / reason columns are optional; whatever is written there is kept.

OUTPUT
------
  make    manual_review/blind/env_cue_blind.csv
          manual_review/blind/other_city_blind.csv
  apply   manual_review/env_cue_validation_heldout.csv  (judged_correct, judge_note, judge, judge_date)
          manual_review/location_other_city_review.csv  (decision, reason, reviewer, review_date)

USAGE
-----
  python blind_review.py make
  python blind_review.py apply --reviewer "Full Name" [--date YYYY-MM-DD]
Then rebuild both datasets with run_all.sh (scratch first, then --publish): the cue
precision and the area counts are computed from these two files.
"""

# Command-line options, today's date, and the exit code
import argparse
import sys
from datetime import date

# Tables
import pandas as pd

# Shared paths (where manual_review/ is)
import common as c

# The two review files the analysis reads, the folder for the blind lists, and the two lists
CUE_PATH = c.MANUAL_REVIEW_DIR / "env_cue_validation_heldout.csv"
CITY_PATH = c.MANUAL_REVIEW_DIR / "location_other_city_review.csv"
BLIND_DIR = c.MANUAL_REVIEW_DIR / "blind"
CUE_BLIND = BLIND_DIR / "env_cue_blind.csv"
CITY_BLIND = BLIND_DIR / "other_city_blind.csv"

# For each list: the columns the reviewer sees, the columns that identify a row,
# and the empty columns the reviewer fills in
CUE_SHOWN = ["cue", "sample_no", "comment_id", "matched_term", "excerpt"]
CUE_KEY = ["cue", "sample_no", "comment_id"]
CUE_ANSWER = ["correct_1_or_0", "note"]
CITY_SHOWN = ["record_type", "record_id", "neighbourhood", "other_cities_mentioned", "location_excerpt"]
CITY_KEY = ["record_type", "record_id", "neighbourhood"]
CITY_ANSWER = ["decision_keep_or_exclude", "reason"]


def read(path):
    """Read a CSV with every value as text and blanks kept as "" (so it writes back unchanged).

    :param path: CSV file to read
    :return: the table
    """
    # Read everything as text so nothing is turned into numbers or NaN; utf-8-sig also
    # reads a list that Excel saved as "CSV UTF-8" (it adds a marker before the header)
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def has_answers(path, answer_cols):
    """Whether a blind list already has anything typed into its answer columns.

    :param path: the blind list
    :param answer_cols: its answer columns
    :return: True if any answer cell is filled
    """
    # Read the list as it is now
    sheet = read(path)
    # True if any answer cell holds more than spaces
    return bool((sheet[answer_cols].apply(lambda col: col.str.strip()) != "").any().any())


def make(force):
    """Write both blind lists: the rows to judge, without the earlier answers.

    :param force: start a list again even if it already has answers
    :return: exit code (0 = written, 1 = refused)
    """
    # Create the blind folder if it isn't there yet
    BLIND_DIR.mkdir(parents=True, exist_ok=True)
    # Each review file with its blind list, the columns to show and the answer columns
    jobs = [(CUE_PATH, CUE_BLIND, CUE_SHOWN, CUE_ANSWER),
            (CITY_PATH, CITY_BLIND, CITY_SHOWN, CITY_ANSWER)]
    # Check both lists first, so neither is written if one would wipe answers
    for _, target, _, answer in jobs:
        # Refuse to overwrite answers someone has already typed in
        if target.exists() and not force and has_answers(target, answer):
            print(f"{target} already has answers; use --force to start it again")
            return 1
    # Write each list
    for source, target, shown, answer in jobs:
        # Keep only the columns the reviewer may see
        sheet = read(source)[shown].copy()
        # Add each answer column
        for col in answer:
            # Empty, for the reviewer to fill in
            sheet[col] = ""
        # Save the list
        sheet.to_csv(target, index=False)
        print(f"wrote {target} ({len(sheet)} rows)")
    # Show how to judge
    print(__doc__.split("HOW TO JUDGE")[1].split("OUTPUT")[0])
    return 0


def check_sheet(sheet, record, key, answer_col, allowed, name):
    """Check that a filled list matches its review file row for row and that every answer is valid.

    :param sheet: the filled blind list
    :param record: the review file it belongs to
    :param key: the columns that identify a row
    :param answer_col: the column holding the answer
    :param allowed: the answers that are accepted
    :param name: the list's file name, for messages
    :return: a list of problems (empty = fine)
    """
    # Problems found so far
    problems = []
    # The same rows must be in the same order in both files
    if len(sheet) != len(record) or not (sheet[key].values == record[key].values).all():
        problems.append(f"{name}: its rows don't match {record.attrs['file']} (run make again?)")
        return problems
    # Answers in lower case without spaces, so " Keep" counts as "keep"
    answers = sheet[answer_col].str.strip().str.lower()
    # Spreadsheet row numbers (row 1 is the header) of answers that are blank or not allowed
    bad_rows = [str(i + 2) for i in range(len(answers)) if answers.iloc[i] not in allowed]
    # Report them if there are any
    if bad_rows:
        # The first 15 row numbers, and "..." if there are more
        shown = ", ".join(bad_rows[:15]) + (" ..." if len(bad_rows) > 15 else "")
        problems.append(f"{name}: {len(bad_rows)} row(s) with no valid {answer_col} "
                        f"({' / '.join(sorted(allowed))}), rows {shown}")
    return problems


def apply(reviewer, day):
    """Write the filled blind lists into the two review files, with the reviewer's name and the date.

    :param reviewer: the name recorded for every judgment
    :param day: the date recorded for every judgment (YYYY-MM-DD)
    :return: exit code (0 = written, 1 = nothing written)
    """
    # The two review files and the two filled lists
    cue = read(CUE_PATH)
    city = read(CITY_PATH)
    cue_sheet = read(CUE_BLIND)
    city_sheet = read(CITY_BLIND)
    # File names for the messages
    cue.attrs["file"] = CUE_PATH.name
    city.attrs["file"] = CITY_PATH.name

    # Check both lists before changing anything
    problems = (check_sheet(cue_sheet, cue, CUE_KEY, "correct_1_or_0", {"1", "0"}, CUE_BLIND.name)
                + check_sheet(city_sheet, city, CITY_KEY, "decision_keep_or_exclude", {"keep", "exclude"},
                              CITY_BLIND.name))
    # Stop, writing nothing, if anything is missing or invalid
    if problems:
        print("Nothing written:")
        print("\n".join("  " + p for p in problems))
        return 1

    # The new answers for both lists
    new_correct = cue_sheet["correct_1_or_0"].str.strip()
    new_decision = city_sheet["decision_keep_or_exclude"].str.strip().str.lower()
    # How many answers differ from what the files held before
    cue_changed = int((new_correct != cue["judged_correct"]).sum())
    city_changed = int((new_decision != city["decision"]).sum())

    # Cue file: your answer, your note, your name and the date on every row
    cue["judged_correct"] = new_correct
    cue["judge_note"] = cue_sheet["note"].str.strip()
    cue["judge"] = reviewer
    cue["judge_date"] = day
    # Other-city file: your decision, your reason, your name and the date on every row
    city["decision"] = new_decision
    city["reason"] = city_sheet["reason"].str.strip()
    city["reviewer"] = reviewer
    city["review_date"] = day
    # Save both review files
    cue.to_csv(CUE_PATH, index=False)
    city.to_csv(CITY_PATH, index=False)

    # Precision of each cue under the new answers
    print(f"{CUE_PATH.name}: {len(cue)} rows written, {cue_changed} answer(s) differ from before")
    # Go through the cues one at a time
    for name, rows in cue.groupby("cue"):
        # Matches judged correct, out of all judged
        k = int((rows["judged_correct"] == "1").sum())
        print(f"  {name:12s} {k} of {len(rows)} correct ({100 * k / len(rows):.0f}%)")
    print(f"{CITY_PATH.name}: {len(city)} rows written, {city_changed} decision(s) differ from before; "
          f"{int((city['decision'] == 'exclude').sum())} exclude, {int((city['decision'] == 'keep').sum())} keep")
    print("Next: rebuild both datasets with run_all.sh (scratch, then --publish).")
    return 0


def main():
    """Read the command and run make or apply.

    :return: exit code
    """
    # The command line has two commands
    parser = argparse.ArgumentParser(description="Blind hand review of the two manual_review files.")
    sub = parser.add_subparsers(dest="command", required=True)
    # "make", which can be forced to start the lists again
    make_cmd = sub.add_parser("make", help="write the blind lists to manual_review/blind/")
    make_cmd.add_argument("--force", action="store_true", help="start a list again even if it has answers")
    # "apply", with the reviewer's name and an optional date
    apply_cmd = sub.add_parser("apply", help="write the filled lists into the review files")
    apply_cmd.add_argument("--reviewer", required=True, help="name recorded for every judgment")
    apply_cmd.add_argument("--date", default=date.today().isoformat(), help="date recorded (default: today)")
    # Read what was typed
    args = parser.parse_args()

    # Run the command that was asked for
    if args.command == "make":
        return make(args.force)
    # Check the date is a real YYYY-MM-DD date before writing it into the files
    try:
        date.fromisoformat(args.date)
    except ValueError:
        print(f"--date must be YYYY-MM-DD, got {args.date!r}")
        return 1
    # A name is needed for the review files
    if not args.reviewer.strip():
        print("--reviewer must not be empty")
        return 1
    return apply(args.reviewer.strip(), args.date)


# Run main() only when this file is run directly, and pass its exit code on
if __name__ == "__main__":
    sys.exit(main())
