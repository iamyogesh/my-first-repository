class Parent:
    def __init__(self):
        pass
    
    def display(name, age):
        return "my %s is and %d age"%(name, age)
        
class Child():
    def display(name, age, sex):
        return "child method"
        

c = Child()
c.display("yogesh",26,"M")
c.display("yogesh",26)