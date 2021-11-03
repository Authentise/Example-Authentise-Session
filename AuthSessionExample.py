import argparse
import asyncio
import copy
import requests
import sys
import json
import time

from requests.auth import HTTPBasicAuth

# pip3 install argparse


class AuthentiseSession:
    # '''
    # Example class to create an API sesssion to a nautilus server for admin use
    # '''

    def __init__(self, host, verify_ssl=True):
        """
        Create an Authentise Session using a persistant API key
        :param verify_ssl : True/False veirfy SSL Keys to CA's
        :param: host: the site to connect to. For example 'authentise.com' or stage-auth.com' for most customer testing
        """
        self.host = host
        self.session_cookie = None  #
        self.api_auth = None
        self.verify_ssl = verify_ssl
        self.default_header = {}
        # for event-stream portion of the session
        self.stream_obj = None
        self.stream_encoding = "utf-8"

    @staticmethod
    def _parse_session_cookie(cookie):
        parts = cookie.split(";")
        return parts[0]

    def _init_session(self, username, password):
        """
        Creates a connection to the system via username/password to get a cookie
        """
        data = {"username": username, "password": password}

        headers = {"content-type": "application/json"}

        response = requests.post("https://data.{}/sessions/".format(self.host), json=data, headers=headers)
        response.raise_for_status()

        cookie_header = response.headers.get("Set-Cookie", None)
        self.default_header["Set-Cookie"] = cookie_header
        self.session_cookie = self._parse_session_cookie(cookie_header)

    def _get_api_key(self):
        """
        Exaple of fetching the long-term API Key from our api_tokens service.
        Cookie is used to get an API Key (longer term access key)
        """
        data = {"name": "create-bureau"}

        headers = {"content-type": "application/json", "cookie": self.session_cookie}

        response = requests.post("https://users.{}/api_tokens/".format(self.host), json=data, headers=headers, verify=self.verify_ssl,)

        if response.ok:
            self.api_auth = response.json()
            print(" We have received an API key we can re-use")
        else:
            print(" No API key matched.")
            sys.exit(1)  # hard fail

    def init_api(self, username, password):
        """
        Creates a connection to the system.
        Username / Password to get a Cookie (temporary, expiring key)
        Cookie is used to get an API Key (longer term access key)
        """
        self._init_session(username, password)
        self._get_api_key()
        return True

    def list(self, url, filters=None):
        auth = HTTPBasicAuth(self.api_auth["uuid"], self.api_auth["secret"])
        list_response = requests.get(url.format(self.host), auth=auth, data=filters, verify=self.verify_ssl)
        if not list_response.ok:
            return {}
        return list_response.json()

    def post(self, url, data, format_=None):
        "Example of calling the API using the API Key to request data from an endpoint"
        headers = None
        auth = HTTPBasicAuth(self.api_auth["uuid"], self.api_auth["secret"])
        if format_ == "json":
            headers = {"Content-Type": "application/json"}
            return requests.post(url.format(self.host), auth=auth, json=data, verify=self.verify_ssl, headers=headers,)

        return requests.post(url.format(self.host), auth=auth, data=data, verify=self.verify_ssl, headers=headers,)

    def get_by_url(self, resource_uri, max_time_s=None):
        """
        @param  a raw URL, gets the dict of the resource at that location.
        @param datetime float of we max time we expect a response in
        Dict on success, None on error"""
        auth = HTTPBasicAuth(self.api_auth["uuid"], self.api_auth["secret"])

        start = time.time()
        ret = requests.get(resource_uri, auth=auth, verify=self.verify_ssl)
        roundtrip = time.time() - start

        if ret.status_code != 200:
            print(f"error getting data on {resource_uri}, got response {ret.text}")
            return None

        if max_time_s:
            if roundtrip > max_time_s:
                raise Exception(f"Needed response time of {max_time_s}, got response of {roundtrip}")

        return ret.json()

    def update(self, resource_uri, update_dict):
        return self.put_(resource_uri, update_dict)

    def put_(self, resource_uri, update_dict):
        auth = HTTPBasicAuth(self.api_auth["uuid"], self.api_auth["secret"])
        ret = requests.put(resource_uri, auth=auth, json=update_dict, verify=self.verify_ssl)
        if not ret.ok:
            print(f"failed to update resource {resource_uri} due to error {ret.text}")
            return False
        return True

    def post_and_upload(self, url, data, file_obj):
        """does a post to create a resource at 'URL'.
        If an X-Upload-Location is replied in the heade, the data from file_obj is pushed to that location
        as per the Authentise standard
        """
        auth = HTTPBasicAuth(self.api_auth["uuid"], self.api_auth["secret"])
        ret = requests.post(url.format(self.host), auth=auth, data=data, verify=self.verify_ssl)
        if ret.status_code != 201:
            print(f"error posting and upload to {url.format}, got response {ret.text}")
            return None

        # we made the DB resource, upload our data
        resource_url = ret.headers.get("Location")
        upload_url = ret.headers.get("X-Upload-Location")
        if not upload_url:
            print(f"Error posting backing-data to to {url.format}, no upload URL in {ret.headers}")
            return None

        # load STL data  from out file , and send to the data service
        raw_data = file_obj.read()  # can take a lot of disk-spcae.
        backing_ret = requests.put(upload_url, auth=auth, data=raw_data, headers={"Content-Type": "application/octet-stream"},)
        if backing_ret.status_code != 204:
            print(f"error uploading backing data for {url.format}, got response {ret.text}")
            return None

        # backing data uploaded . Party
        return resource_url

    def make_delete_request(self, url, uuid):
        "Example of calling the API using the API Key to delete data from an endpoint"
        auth = HTTPBasicAuth(self.api_auth["uuid"], self.api_auth["secret"])
        return requests.delete(url.format(self.host, uuid), auth=auth)

    def get_bureau_uri(self):
        bureau_listicle = self.list("https://data.{}/bureau/")
        # Odd. No match
        if not bureau_listicle.get("resources"):
            print("error, no listing of bureau")
            sys.exit(0)

        # we should have only one match in current releases
        bureau_entry = bureau_listicle.get("resources")[0]
        if not bureau_entry:
            print("error, no details in bureau")
            sys.exit(0)
        return bureau_entry.get("uri")

    def get_any_material_uri(self):
        material_listicle = self.list("https://data.{}/material/")
        if not material_listicle.get("resources"):
            print("error, no listing of material")
            sys.exit(0)
        # we should have only one match in current releases
        material_entry = material_listicle.get("resources")[0]
        if not material_entry:
            print("error, no material in bureau")
            sys.exit(0)
        # returns just our first material we find
        return material_entry.get("uri")

    def get_any_shipping_uri(self):
        listicle = self.list("https://data.{}/shipping/")
        if not listicle.get("resources"):
            print("error, no listing of shipping")
            sys.exit(0)
        # we should have only one match in current releases
        entry = listicle.get("resources")[0]
        if not entry:
            print("error, no shipping in bureau")
            sys.exit(0)
        # returns just our first material we find
        return entry.get("uri")

    def make_request(self, url, data):
        return self.post(url, data)

    def streaming_request(self, url, encoding="utf-8"):
        """
        Creates/opens a streaming request object.
        returns streaming request object
        """
        headers = copy.deepcopy(self.default_header)
        headers["Accept"] = "text/event-stream"
        stream_response = requests.get(url, stream=True, headers=headers)

        # returns an open stream to the url, peridocially messages
        # will get sent back
        self.stream_encoding = encoding
        self.stream_obj = stream_response

        return stream_response

    async def streaming_events_main(self):
        """run until closed"""
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.get_event_loop)
        finally:
            loop.close()

    async def get_event_loop(self,):
        for event in self.events():
            # loop here forever
            print(json.loads(event.data))

    def _read(self):
        """Read the incoming event source stream and yield event chunks.
        Unfortunately it is possible for some servers to decide to break an
        event into multiple HTTP chunks in the response. It is thus necessary
        to correctly stitch together consecutive response chunks and find the
        SSE delimiter (empty new line) to yield full, correct event chunks."""
        data = b""
        for chunk in self.stream_obj:
            for line in chunk.splitlines(True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    yield data
                    data = b""
        if data:
            yield data

    def events(self):
        _FIELD_SEPARATOR = "#"
        # this will loop forever on the self._read until self._stream_obj is closed?
        for chunk in self._read():
            event = Event()
            # Split before decoding so splitlines() only uses \r and \n
            for line in chunk.splitlines():
                # Decode the line.
                line = line.decode(self.stream_encoding)

                # Lines starting with a separator are comments and are to be
                # ignored.
                if not line.strip() or line.startswith(_FIELD_SEPARATOR):
                    continue

                data = line.split(_FIELD_SEPARATOR, 1)
                field = data[0]

                # Ignore unknown fields.
                if field not in event.__dict__:
                    print(f"Saw invalid field {field} while parsing Server Side Event")
                    continue

                if len(data) > 1:
                    # From the spec:
                    # "If value starts with a single U+0020 SPACE character,
                    # remove it from value."
                    if data[1].startswith(" "):
                        value = data[1][1:]
                    else:
                        value = data[1]
                else:
                    # If no value is present after the separator,
                    # assume an empty value.
                    value = ""

                # The data field may come over multiple lines and their values
                # are concatenated with each other.
                if field == "data":
                    event.__dict__[field] += value + "\n"
                else:
                    event.__dict__[field] = value

            # Events with no data are not dispatched.
            if not event.data:
                continue

            # If the data field ends with a newline, remove it.
            if event.data.endswith("\n"):
                event.data = event.data[0:-1]

            # Empty event names default to 'message'
            event.event = event.event or "message"

            # Dispatch the event
            print("Dispatching %s...", event)
            yield event

    def close(self):
        """Manually close the event source stream."""
        self.stream_obj.close()


class Event:  # pylint: disable=too-few-public-methods
    """Representation of an event from the event stream."""

    def __init__(self, id_=None, event="message", data="", retry=None):
        self.id = id_
        self.event = event
        self.data = data
        self.retry = retry

    def __str__(self):
        s = "{0} event".format(self.event)
        if self.id:
            s += " #{0}".format(self.id)
        if self.data:
            s += ", {0} byte{1}".format(len(self.data), "s" if self.data else "")
        else:
            s += ", no data"
        if self.retry:
            s += ", retry in {0}ms".format(self.retry)
        return s


if __name__ == "__main__":
    print("Running Example AuthSessionExample at the command line")

    parser = argparse.ArgumentParser(description="Example of a session to Authentise API.")
    parser.add_argument("username", help="username to log-in via")
    parser.add_argument("password", help="password to log-in via")

    args = parser.parse_args()
    if "username" in args and "password" in args:
        # print(args)
        sesh = AuthentiseSession(host="authentise.com", verify_ssl=True)
        sesh.init_api(args.username, args.password)
    # ags should print there error, no else case needed
