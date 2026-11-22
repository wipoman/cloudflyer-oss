"""Exercise the real MITMAddon methods with in-memory HTTP flows."""
import ast
import logging
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import unittest
from urllib.parse import urlparse


class Response:
    @staticmethod
    def make(status, content, headers):
        return SimpleNamespace(status_code=status, content=content, headers=headers)


source = (Path(__file__).resolve().parents[1] / 'cloudflyer/instance.py').read_text()
addon = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'MITMAddon')
namespace = dict(HTTPFlow=object, Response=Response, Event=Event, urlparse=urlparse,
                 logger=logging.getLogger(__name__))
exec(compile(ast.Module(body=[addon], type_ignores=[]), '<MITMAddon>', 'exec'), namespace)
MITMAddon = namespace['MITMAddon']


def flow(mime='text/html', host='challenges.cloudflare.com', size=128):
    return SimpleNamespace(request=SimpleNamespace(
        host=host, port=443, authority=host, pretty_host=host,
        pretty_url='https://' + host + '/turnstile/v0/test', headers={'Host': host}),
        response=Response.make(200, b'fresh challenge', {'Content-Type': mime, 'Content-Length': str(size)}))


class ResponsePolicyTests(unittest.TestCase):
    def test_official_host_and_authority_preserved(self):
        obj = MITMAddon()
        f = flow()
        f.response = None
        handler = getattr(obj, 'http_connect', None)
        if handler:
            handler(f)
        obj.request(f)
        self.assertEqual(f.request.host, 'challenges.cloudflare.com')
        self.assertEqual(f.request.authority, 'challenges.cloudflare.com')
        self.assertEqual(f.request.headers['Host'], 'challenges.cloudflare.com')
        self.assertIsNone(f.response)

    def test_turnstile_response_not_replayed_in_same_or_next_task(self):
        obj = MITMAddon()
        first = flow()
        obj.response(first)
        for reset in (False, True):
            if reset:
                obj.reset()
            following = flow()
            following.response = None
            obj.request(following)
            self.assertIsNone(following.response)

    def test_page_resources_allowed(self):
        obj = MITMAddon()
        for mime in ('text/css', 'image/png', 'font/woff2', 'application/font-woff', 'application/javascript'):
            with self.subTest(mime=mime):
                f = flow(mime)
                obj.responseheaders(f)
                self.assertEqual(f.response.status_code, 200)

    def test_media_and_large_responses_still_blocked(self):
        obj = MITMAddon()
        for mime, size in (('audio/mpeg', 128), ('video/mp4', 128), ('image/png', 30*1024*1024+1)):
            with self.subTest(mime=mime, size=size):
                f = flow(mime, size=size)
                obj.responseheaders(f)
                self.assertEqual(f.response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
