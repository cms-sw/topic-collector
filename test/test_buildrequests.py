#!/usr/bin/env python

from urllib2 import urlopen, Request
import urllib
import json
TEST_SERVER_URL="https://localhost:8443/cgi-bin/buildrequests"

# Get all requests.
print urlopen(TEST_SERVER_URL).read()
# Create a request.
request = {
    "architecture": "slc5_amd64_gcc472",
    "release": "CMSSW_6_2_X_2013-04-08-0200",
    "repository": "cms",
    "PKGTOOLS": "ktf:my-branch",
    "CMSDIST": "ktf:another-branch",
    "ignoreErrors": True,
    "package": "cmssw-ib",
    "continuations": "cmssw-qa:slc5_amd64_gcc472",
    "syncBack": False,
    "debug": False,
    "hostnameFilter": ".*",
  }
result = urlopen(TEST_SERVER_URL, json.dumps(request)).read()
print result
result = json.loads(result)
assert(result["hostnameFilter"] == ".*")
# Update the lastModiied timestamp.
update = {
  "state": "Stopped", 
  "pid": "100",
  "url": "http://www.foo.bar",
}
req = Request(url=TEST_SERVER_URL + "/" + result["id"],
              data=json.dumps(update))
req.get_method = lambda : "PATCH"
print "update"
result = json.loads(urlopen(req).read())
assert(result["pid"] == "100")
assert(result["state"] == "Stopped")
assert(result["url"] == "http://www.foo.bar")
# Delete the request just created.
exit(0)
print "delete"
req = Request(url=TEST_SERVER_URL + "/" + str(int(result["id"])-1) + "," + result["id"])
req.get_method = lambda : "DELETE"
print urlopen(req).read()
