"""Runs the Ada test program on every word of ipa-uk/sample and compares
the result with ipa_uk.ipa."""
import csv, subprocess, sys, time
import ipa_uk

rows = csv.DictReader(open("/home/claude/ipa-uk/sample/ipa_with_accents_random_10000_comparison.csv",
                           encoding="utf-8"))
words = sorted({word for row in rows for word in row["form"].split()})
started = time.time()
result = subprocess.run(["ada/obj/transcribe_words"], input="\n".join(words) + "\n",
                        capture_output=True, text=True, check=True)
elapsed = time.time() - started
outputs = result.stdout.split("\n")[:-1]
assert len(outputs) == len(words), (len(outputs), len(words))
different = [(word, ipa_uk.ipa(word), output) for word, output in zip(words, outputs)
             if ipa_uk.ipa(word) != output]
for word, expected, actual in different[:10]:
    print(word, expected, actual)
print(f"{len(words)} words in {elapsed:.2f} s, {len(different)} differ")
