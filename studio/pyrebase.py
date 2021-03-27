import requests
from requests import Session
from requests.exceptions import HTTPError

try:
    from urllib.parse import urlencode, quote
except BaseException:
    from urllib import urlencode, quote
import json
import math
from random import uniform
import time
from collections import OrderedDict
from sseclient import SSEClient
import threading
import socket
from oauth2client.service_account import ServiceAccountCredentials
from requests.packages.urllib3.contrib.appengine import is_appengine_sandbox
from requests_toolbelt.adapters import appengine
import certifi

try:
    import python_jwt as jwt
except ImportError:
    jwt = None

try:
    from Crypto.PublicKey import RSA
except BaseException:
    RSA = None
import datetime
from .util import retry

NUM_RETRIES = 3
POOL_SIZE = 100


def initialize_app(config):
    if 'projectId' in config.keys():
        projectId = config['projectId']

        if 'authDomain' in config.keys():
            config['authDomain'] = config['authDomain'].format(projectId)
        if 'databaseURL' in config.keys():
            config['databaseURL'] = config['databaseURL'].format(projectId)
        if 'storageBucket' in config.keys():
            config['storageBucket'] = config['storageBucket'].format(projectId)

    return Firebase(config)


class Firebase:
    """ Firebase Interface """

    def __init__(self, config):
        self.api_key = config.get("apiKey")
        self.auth_domain = config.get("authDomain")
        self.database_url = config.get("databaseURL")
        self.storage_bucket = config.get("storageBucket")
        self.credentials = None
        self.requests = requests.Session()
        if config.get("serviceAccount"):
            scopes = [
                'https://www.googleapis.com/auth/firebase.database',
                'https://www.googleapis.com/auth/userinfo.email',
                "https://www.googleapis.com/auth/cloud-platform"
            ]
            service_account_type = type(config["serviceAccount"])
            if service_account_type is str:
                self.credentials = ServiceAccountCredentials\
                    .from_json_keyfile_name(
                        config["serviceAccount"], scopes)

            if service_account_type is dict:
                self.credentials = ServiceAccountCredentials \
                    .from_json_keyfile_dict(
                        config["serviceAccount"], scopes)

        if is_appengine_sandbox():
            # Fix error in standard GAE environment
            # is releated to
            # https://github.com/kennethreitz/requests/issues/3187
            # ProtocolError('Connection aborted.',
            #               error(13, 'Permission denied'))
            adapter = appengine.AppEngineAdapter(
                pool_connections=POOL_SIZE,
                pool_maxsize=POOL_SIZE,
                max_retries=NUM_RETRIES)
        else:
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=POOL_SIZE,
                pool_maxsize=POOL_SIZE,
                max_retries=NUM_RETRIES)

        for scheme in ('http://', 'https://'):
            self.requests.mount(scheme, adapter)

    def auth(self):
        return Auth(self.api_key, self.requests, self.credentials)

    def database(self):
        return Database(
            self.credentials,
            self.api_key,
            self.database_url,
            self.requests)

    def storage(self):
        return Storage(self.credentials, self.storage_bucket, self.requests)


class Auth:
    """ Authentication Service """

    def __init__(self, api_key, requests, credentials):
        self.api_key = api_key
        self.current_user = None
        self.requests = requests
        self.credentials = credentials

    def sign_in_with_email_and_password(self, email, password):
        request_ref = ("https://www.googleapis.com/identitytoolkit" +
                       "/v3/relyingparty/verifyPassword?key={0}").format(
            self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps(
            {"email": email, "password": password, "returnSecureToken": True})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        self.current_user = request_object.json()
        return request_object.json()

    def create_custom_token(self, uid, additional_claims=None):
        service_account_email = self.credentials.service_account_email
        private_key = RSA.importKey(self.credentials._private_key_pkcs8_pem)
        payload = {
            "iss": service_account_email,
            "sub": service_account_email,
            "aud": "https://identitytoolkit.googleapis.com/" +
                   "google.identity.identitytoolkit.v1.IdentityToolkit",
            "uid": uid}
        if additional_claims:
            payload["claims"] = additional_claims
        exp = datetime.timedelta(minutes=60)
        return jwt.generate_jwt(payload, private_key, "RS256", exp)

    def sign_in_with_custom_token(self, token):
        request_ref = ("https://www.googleapis.com/identitytoolkit" +
                       "/v3/relyingparty/verifyCustomToken?key={0}").format(
            self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"returnSecureToken": True, "token": token})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        return request_object.json()

    def refresh(self, refresh_token):
        request_ref = "https://securetoken.googleapis.com/v1/token?key={0}" \
            .format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"grantType": "refresh_token",
                           "refreshToken": refresh_token})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        request_object_json = request_object.json()
        # handle weirdly formatted response
        user = {
            "userId": request_object_json["user_id"],
            "idToken": request_object_json["id_token"],
            "refreshToken": request_object_json["refresh_token"]
        }
        return user

    def get_account_info(self, id_token):
        request_ref = ("https://www.googleapis.com/identitytoolkit/" +
                       "v3/relyingparty/getAccountInfo?key={0}") \
            .format(self.api_key)

        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"idToken": id_token})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        return request_object.json()

    def send_email_verification(self, id_token):
        request_ref = "https://www.googleapis.com/identitytoolkit/" +  \
                      "v3/relyingparty/getOobConfirmationCode?key={0}" \
            .format(self.api_key)

        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"requestType": "VERIFY_EMAIL", "idToken": id_token})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        return request_object.json()

    def send_password_reset_email(self, email):
        request_ref = "https://www.googleapis.com/identitytoolkit/" + \
                      "v3/relyingparty/getOobConfirmationCode?key={0}" \
                      .format(self.api_key)

        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"requestType": "PASSWORD_RESET", "email": email})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        return request_object.json()

    def verify_password_reset_code(self, reset_code, new_password):
        request_ref = "https://www.googleapis.com/identitytoolkit" + \
                      "/v3/relyingparty/resetPassword?key={0}" \
                      .format(self.api_key)

        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"oobCode": reset_code, "newPassword": new_password})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        return request_object.json()

    def create_user_with_email_and_password(self, email, password):
        request_ref = "https://www.googleapis.com/identitytoolkit/" + \
                      "v3/relyingparty/signupNewUser?key={0}" \
                      .format(self.api_key)

        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps(
            {"email": email, "password": password, "returnSecureToken": True})
        request_object = requests.post(
            request_ref,
            headers=headers,
            data=data,
            verify=certifi.old_where())
        raise_detailed_error(request_object)
        return request_object.json()


class Database:
    """ Database Service """

    def __init__(self, credentials, api_key, database_url, requests):

        if not database_url.endswith('/'):
            url = ''.join([database_url, '/'])
        else:
            url = database_url

        self.credentials = credentials
        self.api_key = api_key
        self.database_url = url
        self.requests = requests

        self.path = ""
        self.build_query = {}
        self.last_push_time = 0
        self.last_rand_chars = []

    def order_by_key(self):
        self.build_query["orderBy"] = "$key"
        return self

    def order_by_value(self):
        self.build_query["orderBy"] = "$value"
        return self

    def order_by_child(self, order):
        self.build_query["orderBy"] = order
        return self

    def start_at(self, start):
        self.build_query["startAt"] = start
        return self

    def end_at(self, end):
        self.build_query["endAt"] = end
        return self

    def equal_to(self, equal):
        self.build_query["equalTo"] = equal
        return self

    def limit_to_first(self, limit_first):
        self.build_query["limitToFirst"] = limit_first
        return self

    def limit_to_last(self, limit_last):
        self.build_query["limitToLast"] = limit_last
        return self

    def shallow(self):
        self.build_query["shallow"] = True
        return self

    def child(self, *args):
        new_path = "/".join([str(arg) for arg in args])
        if self.path:
            self.path += "/{}".format(new_path)
        else:
            if new_path.startswith("/"):
                new_path = new_path[1:]
            self.path = new_path
        return self

    def build_request_url(self, token, shallow=False):
        parameters = {}
        if token:
            parameters['auth'] = token
        if shallow:
            parameters['shallow'] = 'true'

        for param in list(self.build_query):
            if isinstance(self.build_query[param], str):
                parameters[param] = quote('"' + self.build_query[param] + '"')
            elif isinstance(self.build_query[param], bool):
                parameters[param] = "true" if self.build_query[param] \
                                    else "false"
            else:
                parameters[param] = self.build_query[param]
        # reset path and build_query for next query
        request_ref = '{0}{1}.json?{2}'.format(
            self.database_url, self.path, urlencode(parameters))
        self.path = ""
        self.build_query = {}
        return request_ref

    def build_headers(self, token=None):
        headers = {"content-type": "application/json; charset=UTF-8"}
        if not token and self.credentials:
            access_token = self.credentials.get_access_token().access_token
            headers['Authorization'] = 'Bearer ' + access_token
        return headers

    def get(self, token=None, json_kwargs={}, shallow=False):
        build_query = self.build_query
        query_key = self.path.split("/")[-1]
        request_ref = self.build_request_url(token, shallow=shallow)
        # headers
        headers = self.build_headers(token)
        # do request
        request_object = self.requests.get(request_ref, headers=headers)
        raise_detailed_error(request_object)
        request_dict = request_object.json(**json_kwargs)

        # if primitive or simple query return
        if isinstance(request_dict, list):
            return PyreResponse(convert_list_to_pyre(request_dict), query_key)
        if not isinstance(request_dict, dict):
            return PyreResponse(request_dict, query_key)
        if not build_query:
            return PyreResponse(
                convert_to_pyre(
                    request_dict.items()),
                query_key)
        # return keys if shallow
        if build_query.get("shallow"):
            return PyreResponse(request_dict.keys(), query_key)
        # otherwise sort
        sorted_response = None
        if build_query.get("orderBy"):
            if build_query["orderBy"] == "$key":
                sorted_response = sorted(
                    request_dict.items(), key=lambda item: item[0])
            elif build_query["orderBy"] == "$value":
                sorted_response = sorted(
                    request_dict.items(), key=lambda item: item[1])
            else:
                sorted_response = sorted(
                    request_dict.items(),
                    key=lambda item: item[1][build_query["orderBy"]])
        return PyreResponse(convert_to_pyre(sorted_response), query_key)

    def push(self, data, token=None, json_kwargs={}):
        request_ref = self.check_token(self.database_url, self.path, token)
        self.path = ""
        headers = self.build_headers(token)
        request_object = self.requests.post(
            request_ref, headers=headers, data=json.dumps(
                data, **json_kwargs).encode("utf-8"))
        raise_detailed_error(request_object)
        return request_object.json()

    def set(self, data, token=None, json_kwargs={}):
        request_ref = self.check_token(self.database_url, self.path, token)
        self.path = ""
        headers = self.build_headers(token)
        request_object = self.requests.put(
            request_ref, headers=headers, data=json.dumps(
                data, **json_kwargs).encode("utf-8"))
        raise_detailed_error(request_object)
        return request_object.json()

    def update(self, data, token=None, json_kwargs={}):
        request_ref = self.check_token(self.database_url, self.path, token)
        self.path = ""
        headers = self.build_headers(token)
        request_object = self.requests.patch(
            request_ref, headers=headers, data=json.dumps(
                data, **json_kwargs).encode("utf-8"))
        raise_detailed_error(request_object)
        return request_object.json()

    def remove(self, token=None):
        request_ref = self.check_token(self.database_url, self.path, token)
        self.path = ""
        headers = self.build_headers(token)
        request_object = self.requests.delete(request_ref, headers=headers)
        raise_detailed_error(request_object)
        return request_object.json()

    def stream(self, stream_handler, token=None, stream_id=None):
        request_ref = self.build_request_url(token)
        return Stream(
            request_ref,
            stream_handler,
            self.build_headers,
            stream_id)

    def check_token(self, database_url, path, token):
        if token:
            return '{0}{1}.json?auth={2}'.format(database_url, path, token)
        else:
            return '{0}{1}.json'.format(database_url, path)

    def generate_key(self):
        push_chars = '-0123456789' + \
                     'ABCDEFGHIJKLMNOPQRSTUVWXYZ_' + \
                     'abcdefghijklmnopqrstuvwxyz'

        now = int(time.time() * 1000)
        duplicate_time = now == self.last_push_time
        self.last_push_time = now
        time_stamp_chars = [0] * 8
        for i in reversed(range(0, 8)):
            time_stamp_chars[i] = push_chars[now % 64]
            now = int(math.floor(now / 64))
        new_id = "".join(time_stamp_chars)
        if not duplicate_time:
            for i in range(0, 12):
                self.last_rand_chars.append(
                    int(math.floor(uniform(0, 1) * 64)))
        else:
            for i in range(0, 11):
                if self.last_rand_chars[i] == 63:
                    self.last_rand_chars[i] = 0
                self.last_rand_chars[i] += 1
        for i in range(0, 12):
            new_id += push_chars[self.last_rand_chars[i]]
        return new_id

    def sort(self, origin, by_key):
        # unpack pyre objects
        pyres = origin.each()
        new_list = []
        for pyre in pyres:
            new_list.append(pyre.item)
        # sort
        data = sorted(dict(new_list).items(), key=lambda item: item[1][by_key])
        return PyreResponse(convert_to_pyre(data), origin.key())


class Storage:
    """ Storage Service """

    def __init__(self, credentials, storage_bucket, requests):
        from google.cloud import storage
        self.storage_bucket = \
            "https://firebasestorage.googleapis.com/v0/b/" + storage_bucket

        self.credentials = credentials
        self.requests = requests
        self.path = ""
        if credentials:
            client = storage.Client(
                credentials=credentials,
                project=storage_bucket)
            self.bucket = client.get_bucket(storage_bucket)

    def child(self, *args):
        new_path = "/".join(args)
        if self.path:
            self.path += "/{}".format(new_path)
        else:
            if new_path.startswith("/"):
                new_path = new_path[1:]
            self.path = new_path
        return self

    def put(self, file, token=None, userid='guest'):
        # reset path
        path = self.path
        self.path = None
        if isinstance(file, str):
            with open(file, 'rb') as file_object:
                return self._put_file(path, file_object, token, userid)
        else:
            return self._put_file(path, file, path, token, userid)

    def _put_file(self, path, file_object, token, userid):
        request_ref = self.storage_bucket + "/o?name={0}".format(path)

        def post_file(**kwargs):
            def _post_file():
                request_object = self.requests.post(
                    request_ref, data=file_object, **kwargs)
                raise_detailed_error(request_object)
                return request_object

            return retry(
                _post_file,
                no_retries=10,
                sleep_time=5,
                exception_class=HTTPServerError)

        if token:
            headers = {"Authorization": "Firebase " + token}

            request_object = post_file(headers=headers)
            if userid:
                headers['Content-Type'] = 'application/json'

                def patch_owner():
                    patch_request = self.requests.patch(
                        request_ref,
                        headers=headers,
                        data=json.dumps({'metadata': {'owner': userid}})
                    )

                    raise_detailed_error(patch_request)
                    return patch_request

                retry(
                    patch_owner,
                    no_retries=10,
                    sleep_time=5,
                    exception_class=HTTPServerError)

            return request_object.json()
        elif self.credentials:
            blob = self.bucket.blob(path)
            if isinstance(file_object, str):
                return blob.upload_from_filename(filename=file_object)
            else:
                return blob.upload_from_file(file_obj=file_object)
        else:
            return post_file().json()

    def delete(self, name):
        self.bucket.delete_blob(name)

    def download(self, filename, token=None):
        # remove leading backlash
        path = self.path
        url = self.get_url(token)
        self.path = None
        if path.startswith('/'):
            path = path[1:]
        if self.credentials:
            blob = self.bucket.get_blob(path)
            blob.download_to_filename(filename)
        else:
            def _download_internal():
                r = requests.get(url, stream=True)
                raise_detailed_error(r)
                if r.status_code == 200:
                    with open(filename, 'wb') as f:
                        for chunk in r:
                            f.write(chunk)
                elif r.status_code >= 500:
                    raise HTTPServerError(r.status_code, r.text)

            retry(
                _download_internal,
                no_retries=10,
                sleep_time=5,
                exception_class=HTTPServerError)

    def get_url(self, token):
        path = self.path
        self.path = None
        if path.startswith('/'):
            path = path[1:]
        if token:
            return "{0}/o/{1}?alt=media&token={2}".format(
                self.storage_bucket, quote(path, safe=''), token)
        return "{0}/o/{1}?alt=media".format(self.storage_bucket,
                                            quote(path, safe=''))

    def list_files(self):
        return self.bucket.list_blobs()


class HTTPServerError(Exception):
    def __init__(self, statuscode, message):
        self.msg = message
        self.statuscode = statuscode


def raise_detailed_error(request_object):
    try:
        status = request_object.status_code
        if status >= 500:
            raise HTTPServerError(status, request_object.text)
        request_object.raise_for_status()
    except HTTPError as e:
        # raise detailed error message
        # TODO: Check if we get a { "error" : "Permission denied." } and handle
        # automatically
        raise HTTPError(e, request_object.text)


def convert_to_pyre(items):
    pyre_list = []
    for item in items:
        pyre_list.append(Pyre(item))
    return pyre_list


def convert_list_to_pyre(items):
    pyre_list = []
    for item in items:
        pyre_list.append(Pyre([items.index(item), item]))
    return pyre_list


class PyreResponse:
    def __init__(self, pyres, query_key):
        self.pyres = pyres
        self.query_key = query_key

    def val(self):
        if isinstance(self.pyres, list):
            # unpack pyres into OrderedDict
            pyre_list = []
            # if firebase response was a list
            if isinstance(self.pyres[0].key(), int):
                for pyre in self.pyres:
                    pyre_list.append(pyre.val())
                return pyre_list
            # if firebase response was a dict with keys
            for pyre in self.pyres:
                pyre_list.append((pyre.key(), pyre.val()))
            return OrderedDict(pyre_list)
        else:
            # return primitive or simple query results
            return self.pyres

    def key(self):
        return self.query_key

    def each(self):
        if isinstance(self.pyres, list):
            return self.pyres


class Pyre:
    def __init__(self, item):
        self.item = item

    def val(self):
        return self.item[1]

    def key(self):
        return self.item[0]


class KeepAuthSession(Session):
    """
    A session that doesn't drop Authentication on redirects between domains.
    """

    def rebuild_auth(self, prepared_request, response):
        pass


class ClosableSSEClient(SSEClient):
    def __init__(self, *args, **kwargs):
        self.should_connect = True
        super(ClosableSSEClient, self).__init__(*args, **kwargs)

    def _connect(self):
        if self.should_connect:
            super(ClosableSSEClient, self)._connect()
        else:
            raise StopIteration()

    def close(self):
        self.should_connect = False
        self.retry = 0
        self.resp.raw._fp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        self.resp.raw._fp.fp.raw._sock.close()


class Stream:
    def __init__(self, url, stream_handler, build_headers, stream_id):
        self.build_headers = build_headers
        self.url = url
        self.stream_handler = stream_handler
        self.stream_id = stream_id
        self.sse = None
        self.thread = None
        self.start()

    def make_session(self):
        """
        Return a custom session object to be passed to the ClosableSSEClient.
        """
        session = KeepAuthSession()
        return session

    def start(self):
        self.thread = threading.Thread(target=self.start_stream)
        self.thread.start()
        return self

    def start_stream(self):
        self.sse = ClosableSSEClient(
            self.url,
            session=self.make_session(),
            build_headers=self.build_headers)
        for msg in self.sse:
            if msg:
                msg_data = json.loads(msg.data)
                msg_data["event"] = msg.event
                if self.stream_id:
                    msg_data["stream_id"] = self.stream_id
                self.stream_handler(msg_data)

    def close(self):
        while not self.sse and not hasattr(self.sse, 'resp'):
            time.sleep(0.001)
        self.sse.running = False
        self.sse.close()
        self.thread.join()
        return self
