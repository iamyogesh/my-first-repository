#add = lambda x,y :x + y

#print add("hello", "world")

names = ['yogesh ramachandra', 'pooja sk', 'shwetha bhaskara','madhura kodiya']
print sorted(names, key = lambda name: name.split()[-1])
