import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from apps.courses.mcq_importer import parse_mcq_text

sample_bengali_text = """
১। ‘সোনার তরী’ কবিতার বর্ণনামতে বর্ষা কখন এল?
ক. ধান কাটা শুরু হলে    খ. ধান কাটতে কাটতে    গ. ধান কাটা শেষ হলে    ঘ. নৌকায় ধান তুলে দিলে    খ

২। ‘ওগো তুমি কোথা যাও কোন বিদেশে’- ‘সোনার তরী’ কবিতায় এখানে ‘তুমি’ কে?
ক. কৃষক  খ. তরী  গ. মাঝি  ঘ. কবি   গ

৩। “চারি দিকে বাঁকা জল করিছে খেলা”- এখানে ‘বাঁকা জল’ বলতে কবি কী বোঝাতে চেয়েছেন?
ক. স্রোতের বক্রতা  খ. জলের কল্লোল  গ. পরিস্থিতির ভয়াবহতা  ঘ. অনন্ত কালস্রোত   ঘ

৪। রবীন্দ্রনাথ ঠাকুর তাঁর পিতা-মাতার কততম সন্তান?
ক. দ্বিতীয়  খ. ষষ্ঠ  গ. দশম  ঘ. চতুর্দশ  ঘ

৫। ‘সোনার তরী’ কবিতায় ‘সোনার ধান’ কিসের প্রতীক?
ক. মহাকাল  খ. সমকাল  গ. সৃষ্টিকর্ম  ঘ. কালস্রোত  গ

১৫। ‘সোনার তরী’ কবিতায় ‘আমি’ বলতে যাকে বোঝায়-
i. নৌকার মাঝি
ii. সাধারণ অর্থে কৃষক
iii. প্রতীকী অর্থে কবি নিজে
নিচের কোনটি সঠিক?
ক. i  খ. i ও ii  গ. i ও iii  ঘ. ii ও iii  ঘ

১৬। ‘সোনার তরী’ কবিতায় ‘বিদেশ’ শব্দটি কী অর্থে ব্যবহৃত হয়েছে?
ক. পরলোক
খ. অচেনা জগৎ
গ. চিরায়ত শিল্পলোক
ঘ. মহাকাল
উত্তর: গ
ব্যাখ্যা: রবীন্দ্রনাথ ঠাকুরের সোনার তরী কবিতায় বিদেশ শব্দটি চিরায়ত শিল্পলোক বোঝাতে ব্যবহৃত হয়েছে।
"""

parsed = parse_mcq_text(sample_bengali_text)
print(f"Total parsed questions: {len(parsed)}")
for idx, q in enumerate(parsed, 1):
    print(f"\n--- Q{idx} ---")
    print(f"Text: {q['question_text']}")
    print(f"A: {q['option_a']}")
    print(f"B: {q['option_b']}")
    print(f"C: {q['option_c']}")
    print(f"D: {q['option_d']}")
    print(f"Correct: {q['correct_option']}")
    if q['explanation']:
        print(f"Explanation: {q['explanation']}")
