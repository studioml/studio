import urllib2

try:
    response = urllib2.urlopen(urllib2.Request('http://169.254.169.254/latest/meta-data/ami-id')).read()

    print 'On AWS'

except Exception as nometa:
    print 'Not on AWS'

try:
    response = urllib2.urlopen(urllib2.Request('http://169.254.169.254/metadata')).read()

    print 'On Azure'

except Exception as nometa:
    print 'Not on Azure'

