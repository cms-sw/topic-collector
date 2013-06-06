# DEPLOYMENT

The CMS topic collector is to be deployed just like any other CERN WEB service.

## Creating the Web Area

The CMS Topic Collector is just a bunch of state-less cgi scripts, so you can
deploy them on any CGI enabled web server with SSO support. For the CMS
Official Instance you can simply rely on the CERN web service support.

First of all go to:

    https://webservices.web.cern.ch/webservices/

create a new AFS based web site. We reccomend using your AFS workspace for
doing so, make also sure you enable CGI support. In the case of the Official
Instace, we use the `cmsbuild` account and
`/afs/cern.ch/work/c/cmsbuild/www/cmsgit`.

Assuming your site is in:

    WORKDIR=/afs/cern.ch/work/c/cmsbuild
    CMSGIT_ROOT=$WORKDIR/www/cmsgit

you'll need to make sure the web server can read those files:

    fs sa -dir $WORKDIR -acl webserver:afs l
    fs sa -dir $WORKDIR/www -acl webserver:afs l
    fs sa -dir $CMSGIT_ROOT -acl webserver:afs rl
    fs sa -dir $CMSGIT_ROOT -acl system:anyuser none

you'll also want to create a parallel directory which contains data, but which
is not at all exposed to the web:

    mkdir -p $WORKDIR/cmsgit-data
    fs sa -dir $WORKDIR/cmsgit-data -acl webserver:afs rl
    fs sa -dir $WORKDIR/cmsgit-data -acl system:anyuser none

notice you will need to make sure the `webserver:afs` user can list (but not
read!) the parents of the directories you have picked up.

You then need to enable SSO, i.e. at CERN you'll need to do:

    cat << \EOF > $CMSGIT_ROOT/.htaccess
    ShibRequireAll On
    ShibRequireSession On
    ShibExportAssertion On
    SSLRequireSSL   # The modules only work using HTTPS
    AuthType Shibboleth
    Require adfs-group "User admin group ZH" "cms-zh"
    EOF

This will give you a working CGI area, accessible only by CMS users. To test that:

    cat << \EOF > $CMSGIT_ROOT/hello
    #!/usr/bin/env python
    from os import environ
    print "Status: 200 OK"
    print
    print "Hello %s!" % environ["ADFS_LOGIN"] 
    EOF
    chmod +x $CMSGIT_ROOT/hello

and then check the web page works correctly. In case of the Official Instance
simply go to:

    https://cern.ch/cmsgit/hello

If everything works correctly it should ask you to login and show:

    Hello <your-sso-login>!

Remove $CMSGIT_ROOT/hello, and go to next session.

## Checking out Topic Collector sources

Now it's time to populate the web area with the actual sources of the topic collector.

    cd $CMSGIT_ROOT
    git clone --bare eulisse@lxbuild167.cern.ch:www/cgi-bin/git-collector/.git .git
    git init
    git read-tree -mu HEAD

from now on you can update them by simply doing `git pull origin master`.

## Getting secrets for GitHub API and CMS Tag Collector

Given the Topic Collector is only a thin layer on top of the GitHub API, we
need to get github API secrets to make sure we can access the repository of our
choice.

If you are deploying the official CMS Topic Collector, you do not need to do
any of the following and you can skip to the next section.

First of all register [a new
application](https://github.com/settings/applications/new) and note down the
client ID and client secret we will refer to them as `CLIENT_ID` and
`CLIENT_SECRET`. *DO NOT SHARE THEM*.

If you want to use the Topic Collector API which proxies the old Tag Collector
API, copy your `userkey.pem` and `usercert.pem` to `$WORKDIR/cmsgit-data`.

    cp ~/.globus/usercert.pem <USERKEY_PATH>
    cp ~/.globus/userkey.pem <USERKEY_PATH>

Finally you need to get an "Personal API Access Token" from github for the user
which you consider administrator of your repository (cmsbuild, in the case of
the official instance). This can be done by going to
<https://github.com/settings/applications> and clicking on "Create new token".
    
Create a `secrets.py` file with the following contents:

    cat << EOF > $CMSGIT_ROOT/secrets.py
    github_secrets={"production":
                     {
                       "client_id": "CLIENT_ID",
                       "client_secret": "CLIENT_SECRETS",
                       "admin_auth_token": "ADMIN_TOKEN",
                     }
    }
    cern_secrets = {
                     "usercert": "USERPEM_PATH",
                     "userkey": "USERKEY_PATH",
                     "tokens_path": "TOKENS_PATH"
                     "cache": "CACHE_PATH",
    }
    EOF

In case of the Official Instance, you can simply copy your secrets from
cmsbuild private afs area:

    cp ~/private/secrets.py $CMSGIT_ROOT/secrets.py
    mkdir -p $WORKDIR/cmsgit-data/secrets
    cp ~/.globus/usercert.pem $WORKDIR/cmsgit-data/secrets/usercert.pem
    cp ~/.globus/userkey.pem $WORKDIR/cmsgit-data/secrets/userkey.pem

Make sure you cannot access the file from the web and make sure they cannot be
read by anyone but your user and the webserver.

Finally we need to create a couple of web writeable directories which will be used
to hold cached results (FIXME: use MEMCACHE / real DB).

    mkdir -p $WORKDIR/cmsgit-data/tokens
    mkdir -p $WORKDIR/cmsgit-data/cache
    fs sa -dir $WORKDIR/cmsgit-data/tokens -acl webserver:afs rlwikd
    fs sa -dir $WORKDIR/cmsgit-data/tokens -acl system:anyuser none
    fs sa -dir $WORKDIR/cmsgit-data/cache -acl webserver:afs rlwikd
    fs sa -dir $WORKDIR/cmsgit-data/cache -acl system:anyuser none

# API

## Schema

All API access is over HTTPS, and accessed from the
eulisse.web.cern.ch/eulisse/cgi-bin/git-collector domain. All data is sent and
received as JSON. You'll have to be authenticated via CERN SSO to get the data.

## Parameters 

Many API methods take optional parameters. For GET requests, any parameters not
specified as a segment in the path can be passed as an HTTP query string
parameter.

For POST requests, parameters not included in the URL should be encoded as JSON
with a Content-Type of ‘application/x-www-form-urlencoded’:

## Build Requests

### Get all build requests

    GET /buildrequests

Response:

    Status: 200 OK
    [
      {
        "status": "", 
        "author": "", 
        "buildMachine": "",
        "pid": "",
        "payload": "test", 
        "lastSeen": "", 
        "id": "1"
      }
    ]

Gets the list of  buildrequests.

### Get one specific build requests
  
    GET /buildrequests/:id

Response:

    {
      "id": "1", 
      "payload": ""
    }

### Create a new build request.

    POST /buildrequests

Arguments:

- `architecture`:
  The architecture of the build request.
- `release_name`:
  The release name to which the build belongs.
- `repository`:
  The name of the repository to use as a source.
- `PKGTOOLS`:
  PKGTOOLS tag or branch. Optional, will default to `IB/<release series>/<architecture>`.
- `CMSDIST`:
  CMSDIST tag or branch. Optional, will default to `IB/<release series>/<architecture>`.
- `ignoreErrors`:
  Whether or not ignore errors. Optional, will default to false.
- `package`:
  The package to build. Optional, defaults to cmssw-tool-conf.
- `continuations`:
  What to build next, in case of success. It takes a comman separated list of 
  <package>:<architecture> pairs. Optional, defaults to nothing.
- `syncBack`: 
  Wether to sync back to the parent repository. Optional, defaults to false.
- `debug`: 
  Debug mode. Optional will default to false.

Input:

  {
    "architecture": "slc5_amd64_gcc472",
    "release_name": "CMSSW_6_2_X_2013-04-08-0200",
    "repository": "cms",
    "PKGTOOLS": "ktf:my-branch",
    "CMSDIST": "ktf:another-branch",
    "ignoreErrors": true,
    "package": "cmssw-ib",
    "continuations": "cmssw-qa:slc5_amd64_gcc472",
    "syncBack": false,
    "debug": false
  }

Response:
    
    Status: 200
    To be written

### Update the status of the build request.

    PATCH /buildrequests/<id>

## Legacy tag collector API


### Get all the release queues

    GET /cvs-queue

Response:

    Status: 200 OK
    [
      {
        "name": "CMSSW_6_2_X"
      }
    ]

### Get a list of all externals queues

    GET /externals

where:

Example:

    GET /externals

Response:

    Status: 200 OK
    [
     {"ref": "CMSSW_5_3_X"}, 
     {"ref": "CMSSW_6_1_X"}, 
     {"ref": "CMSSW_6_2_X"}
    ]

### Get externals for a given queue

    GET /externals/<release-queue>

where:

* `<release-queue>` is the release queue for which you want to get all the
  externals.

Example:

    GET /externals/CMSSW_6_2_X

Response:

    Status: 200 OK
    [{
      "CMSDIST_TAG": "IB/CMSSW_6_2_X/stable",
      "PKGTOOLS_TAG": "V00-21-XX", 
      "SCRAM_ARCH": "slc5_amd64_gcc472"
    }]

### Get all tagsets relative to a given release

    GET /cvs-queue/<release-queue>

Response:

    Status: 200 OK
    {
      "131858": [["RecoMET/METFilters", "V00-00-15", "V00-00-11-03"]]
    }
