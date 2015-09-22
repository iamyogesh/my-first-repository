class C :
    def __init__(self):
        self._x = None
        
    def getx(self):
        return self._x
        
    def setx(self,x):
        self._x = x
        
    def delx(self):
        del self._x
        

    x = property(getx, setx,delx, 'x getter and setter property')

c = C()
c.x= 10

print c.x

