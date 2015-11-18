from collections import Counter
msg = "most common syntax mistake when typing in the above sort of code, probably  since that's an additional thing to type vs. my C++/Java habits. Also, don't put the boolean test in parens -- that's a C/Java habit. If the code is short you can put the code on the same line after"
converted_list = msg.split() # convert string to list
word_counts = Counter(converted_list)
print word_counts.most_common(5)