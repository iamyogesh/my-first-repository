class Person:
	def __init__(self, first_name):
		self.first_name = first_name

	@property
	def first_name(self):
		return self.first_name

	@first_name.setter
	def first_name(self, value):
		if not isinstance(value,str):
			print type(value)
			raise TypeError("expected an string")
		self.first_name = value

	@first_name.deleter
	def first_name(self):
		raise AttributeError('cant deete a property')

p = Person('yogesh')
#print p.first_name
p.first_name = 11
print p.first_name