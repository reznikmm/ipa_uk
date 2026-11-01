"""Compares the pipeline with ipa_uk.ipa on every word of ipa-uk/sample."""
import csv, importlib, pickle, re, sys
import build_pipeline
import ipa_uk
importlib.reload(ipa_uk)  # the real "re" again

import __main__; __main__.Stage = build_pipeline.Stage
stages = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "pipeline.pickle", "rb"))
rows = csv.DictReader(open("/home/claude/ipa-uk/sample/ipa_with_accents_random_10000_comparison.csv",
                           encoding="utf-8"))
words = sorted({word.lower() for row in rows for word in row["form"].split()})
mismatches = 0
for word in words:
    expected = ipa_uk.ipa(word)
    try:
        actual = build_pipeline.apply_pipeline(stages, word)
    except KeyError as error:
        actual = f"<{error}>"
    if actual != expected:
        mismatches += 1
        if mismatches <= 10:
            print(word, expected, actual)
print(f"{len(words)} words, {mismatches} mismatches")
