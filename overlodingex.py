class Parent:
    def __init__(self):
        pass
    
    def display(self,name,age):
        print "my %s is and %d age"%(name, age)
        
    def shout(self):
        print "yavvvv"
        
class Child(Parent):
    def display(self,name, age, sex='F'):
        print"my %s is and %d age is %s" %(name, age, sex)
        

c = Child()
#c.shout()
c.display("yogesh",26)
#p = Parent()
#p.display('yogesh', 25)