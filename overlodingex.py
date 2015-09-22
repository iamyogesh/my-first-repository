class Parent:
    def __init__(self):
        pass
    
    def display(self,name,age):
        print "my %s is and %d age"%(name, age)
        
    def shout(self):
        print "yavvvv"
        
class Child(Parent):
    def display(self,name, age, sex):
        print"my %s is and %d age is %s" %(name, age, sex)
        

c = Child()
c.display("yogesh",26)

