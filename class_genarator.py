class Countdown:
	def __init__(self, start):
		self.start = start


	def iter(self):
		n = self.start
		while n >0 :
			yield n
			n -=1

	def __reversed__(self):
		n = 1
		while n <= self.start:
			yield n
			n += 1

c = Countdown(4)
for i in range(4):
	print c.iter.__self__