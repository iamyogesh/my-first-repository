def countdown(n):
	print "stsrting count down from", n
	while n>0:
		yield n 
		n -= 1
	print "Done"

c = countdown(4)
for i in range(5):
	print next(c)