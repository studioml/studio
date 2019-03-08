import platform as pf

print 'Normal :', pf.platform()
print 'Aliased:', pf.platform(aliased=True)
print 'Terse:', pf.platform(terse=True)

print 'uname:', pf.uname()

print 'interpreter:', pf.architecture()

print 'build:' , pf.python_build()

print 'machine:', pf.machine()

print 'node:', pf.node()

print 'processor:', pf.processor()

print 'system:', pf.system()

print 'release:', pf.release()

