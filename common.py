#!/usr/bin/env python26
#
# A smallish toolkit for web requests.
import os
import re
import cgi
import urllib2
import urllib
import random
import shutil
import sys

try:
  from hashlib import sha1
except:
  from sha import new as sha1

from secrets import github_secrets, cern_secrets
from sys import exit
from time import mktime, strptime, strftime, gmtime, time
from os.path import join, basename
from glob import glob
from commands import getstatusoutput

try:
  from json import dumps as encode
  from json import loads as decode
except ImportError:
  from cjson import encode
  from cjson import decode 

# Helper method which acutually does the sqlite query.
# Notice that on slc4 (i.e. lxplus), there is no sqlite available, so we rely
# on my personal copy of it.
def doQuery(query, database):
  if os.path.exists("/usr/bin/sqlite3"):
    sqlite="/usr/bin/sqlite3"
  else:
    sqlite="/afs/cern.ch/user/e/eulisse/www/bin/sqlite"
  return getstatusoutput("echo '%s' | %s -separator @@@ %s" % (query, sqlite, database))

def format(s, **kwds):
  return s % kwds

def call(api, access_token=None, trace=False):
  # If an access token is provided, use it, otherwise use the OAuth2 Key/Secret
  # pair for cms-sw auth.
  if access_token:
    auth="access_token=" + access_token
  else:
    auth=format("client_id=%(client_id)s&client_secret=%(client_secret)s",
                client_id=github_secrets["production"]["client_id"],
                client_secret=github_secrets["production"]["client_secret"])
  url = format('https://api.github.com%(api)s?%(auth)s', api=api, auth=auth)
  if trace:
    debug(url)
  return url

class NotModifiedHandler(urllib2.HTTPSHandler):
  def http_error_304(self, req, fp, code, message, headers):
    addinfourl = urllib2.addinfourl(fp, headers, req.get_full_url())
    addinfourl.code = code
    return addinfourl

class CreatedHandler(urllib2.HTTPSHandler):
  def http_error_201(self, req, fp, code, message, headers):
    addinfourl = urllib2.addinfourl(fp, headers, req.get_full_url())
    addinfourl.code = code
    return addinfourl

def patchRequest(api, authToken=None, **kwds):
  opener = urllib2.build_opener(CreatedHandler)
  data=encode(kwds)
  request = urllib2.Request(call(api, authToken))
  request.add_data(data)
  request.get_method = lambda: 'PATCH'
  request.add_header("Content-Type", "application/x-www-form-urlencoded")
  request.add_header("Content-Length", str(len(data)))
  response = opener.open(request)
  return decode(response.read())

def postRequest(api, authToken=None, **kwds):
  opener = urllib2.build_opener(CreatedHandler)
  data=encode(kwds)
  request = urllib2.Request(call(api, authToken))
  request.add_data(data)
  request.get_method = lambda: 'POST'
  request.add_header("Content-Type", "application/x-www-form-urlencoded")
  request.add_header("Content-Length", str(len(data)))
  response = opener.open(request)
  return decode(response.read())

def postRequestJSON(api, **kwds):
  data = urllib.urlencode(kwds)
  response = urllib2.urlopen(call(api), data)
  return decode(response.read())

# Explot github 304 answers for faster result.
# Get the most recent response and check if still ok.
# - Return the cached version if yes.
# - Save it and return the response if not. 
# 
# Can pass a transformation function which can be used to process the response
# before saving it and a transformation id, which can be used to uniquely
# identify the transformed data.
def getRequestCached(api, access_token=None, transformation=None, transformation_id="", **kwds):
  args=""
  if kwds:
    args = "&" + urllib.urlencode(kwds)
  url = call(api, access_token)+args
  hash = sha1(url).hexdigest()
  objDir = join(cern_secrets["cache"], hash[0:2], hash[2:])
  cached = glob(join(objDir, "*"))
  etag = None
  seconds = None
  cachedResponse = None
  if cached:
    cachedResponse = cached.pop()
    id = basename(cachedResponse)
    seconds, etag = id.split("-", 1)

  opener = urllib2.build_opener(NotModifiedHandler())
  request = urllib2.Request(call(api, access_token)+args)
  if etag:
    request.add_header("If-None-Match", '"' + etag + '"')
  if seconds:
    request.add_header("If-Modified-Since", strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(int(seconds))))
  response = opener.open(request)
  headers = response.info()
  # If there is no transformation to do and the server says that our cached
  # copy is still valid, return the cached copy.
  if not transformation and hasattr(response, 'code') and response.code == 304:
    return open(cachedResponse).read()
  # If the server replied that everything is unchanged, lets verify we have
  # done the transformation after the last modified date.
  transformedHash = sha1(url + transformation_id).hexdigest()
  transformedObjDir = join(cern_secrets["cache"], transformedHash[0:2], transformedHash[2:])
  cachedResponseTxt = None
  if hasattr(response, 'code') and response.code == 304:
    processed = glob(join(transformedObjDir, "*"))
    processedResponse = None
    processedEtag = None
    processedSeconds = None
    if processed:
      processedResponse = processed.pop()
      processedId = basename(processedResponse)
      processedSeconds, processedEtag = processedId.split("-")
    # If the transformed document is more recent than the cached source, return
    # it.  If not calculate a new one and save it.
    if processedSeconds and float(processedSeconds) > float(seconds):
      return open(processedResponse).read()
    cachedResponseTxt = open(cachedResponse).read()
    
  # If we end up here, it means we need to do all the work.
  # First save the API call.
  etag = headers.getheader("ETag").strip('"')
  seconds = "0"
  last_modified = headers.getheader("Last-Modified") 
  if last_modified:
    seconds = str(int(mktime(strptime(last_modified, "%a, %d %b %Y %H:%M:%S GMT"))))
  try:
    os.makedirs(objDir)
  except Exception, e:
    pass
  txt = cachedResponseTxt or response.read()
  open(join(objDir, seconds + "-" + etag), "w").write(txt)
  # If there is no transformation, return what we received.
  if not transformation:
    return txt
  # Now calculate the transformation.
  transformedTxt = transformation(txt)
  try:
    os.makedirs(transformedObjDir)
  except Exception, e:
    pass
  processedEtag = sha1(transformedTxt).hexdigest()
  processedSeconds = str(mktime(gmtime()))
  open(join(transformedObjDir, processedSeconds + "-" + processedEtag), "w").write(transformedTxt)
  return transformedTxt

def getRequestTxt(api, **kwds):
  args=""
  if kwds:
    args = "&" + urllib.urlencode(kwds)
  response = urllib2.urlopen(call(api)+args)
  return response.read()

def getRequest(api,**kwds):
  return decode(getRequestTxt(api,**kwds))
  
def debug(s):
  print 'Status: 200 OK';
  print "Content-type: application/json\r\n\r\n";
  print "DEBUG"
  print s
  exit(0)
  
def jsonReply(s):
  print 'Status: 200 OK';
  print "Content-type: application/json\r\n";
  if type(s) == str:
    print s
  else:
    print encode(s)
  exit(0)

def httpReply(contentType, etag, *elements):
  results = ""
  for s in elements:
    if type(s) == str:
      results += s
    elif type(s) == file:
      results += s.read()
    elif callable(s):
      results += s()
  h = sha1(results).hexdigest()
  #debug(etag)
  if etag.strip("\"") == h:
    print 'Status: 304 Not Modified\r\n\r\n';
    exit(0)
  
  print 'Status: 200 OK';
  print 'Cache-Control: max-age=0, must-revalidate'
  print 'Connection: close';
  print "Date: %s" % strftime('%a, %d %b %Y %H:%M:%S GMT', gmtime())
  print "Last-Modified: %s" % strftime('%a, %d %b %Y %H:%M:%S GMT', gmtime())
  print "ETag: \"%s\"" % h
  print "Content-type: %s" % contentType
  print
  print results
  exit(0)

def status(code, status):
  print "Status: %s %s" % (code, status)
  print

# Serve a file without having to read it all in memory first.
def serveFile(filename, code=None, mimetype=None):
  if not code:
    code = 200
  code_map = {200: "OK"}
  print "Status: %s %s" % (code, code_map.get(code, "Unknown"))
  if mimetype:
    print "Content-type: %s" % mimetype
  print
  shutil.copyfileobj(open(filename), sys.stdout)
  exit(0)

# Return 304 (Not modified) if the version cached by the 
# browser is still valid.
#
# @a url is the url of the resource that got requested.
# @a retriever is a function which serves the 
# @a etag is the etag of the resource 
#def serveCached(url, retriever, etag=None, last):
#  urlHash = sha1(url)
#  cachePath = os.path.join("static_cache", urlHash[0:2], urlHash[2:])
#  cachedObjs = glob(cachePath+ "/*")
#  if not etag:
#    result = retriever()
#    etag = sha1(result)
#  # Look in all the cached objects and check if any matches
#  for obj in cachedObjs:
#    if obj.endswith(etag):
#      print "Status: 304 Not Modified\r\n"
#      exit(0)
#  makedirs(cachePath)

def error(code, s):
  status(code, s)
  exit(0)

def validateInputs(data, requiredFields):
  if len(data) != len(requiredFields):
    badRequest()
  for k in data:
    if not k in requiredFields:
      badRequest()
  return data

badRequest = lambda : error(400, "Bad Request")

# An helper to invoke API calls in the form:
#
# /api/<type>/<id>/<method>
#
# @a pathInfo the PATH_INFO from apache
# @a klass the type indicating a group of methods
# @a api a dict with the actual method implementation. All method must take
#    the id
#
# Notice that you can define a special "__all" method for the case the PATH_INFO
# is just:
#
# /api/<type>
#
# No trailing "/". and a special method "__info" for the case the PATH_INFO is
#
# /api/<type>/<id>
def invoke(pathInfo, klass, api):
  if pathInfo == "/api/" + klass:
    jsonReply(api["__all"]())
  args = pathInfo.replace("/api/%s/" % klass, "").strip("/").split("/")
  if len(args) == 1:
    args += ["__info"]
  if len(args) != 2:
    error("404", "Not Found")
  objId, method = args
  if not re.match("[0-9a-zA-Z_-]+", objId):
    error("404", "Not Found")
  if not method in api:
    error("404", "Not Found")
  result = api[method](objId)
  if type(result) == dict:
    result = encode(result)
  jsonReply(result)
