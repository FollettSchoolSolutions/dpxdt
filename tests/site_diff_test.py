#!/usr/bin/env python
# Copyright 2013 Brett Slatkin
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the site_diff utility."""

import BaseHTTPServer
import logging
import os
import socket
import sys
import tempfile
import threading
import unittest

# Local libraries
import gflags
FLAGS = gflags.FLAGS

# Local modules
from dpxdt import runserver
from dpxdt import runworker
from dpxdt import server
from dpxdt.client import capture_worker
from dpxdt.client import workers
from dpxdt.server import db
from dpxdt.server import models
from dpxdt.tools import site_diff


# For convenience
exists = os.path.exists
join = os.path.join



def get_free_port():
    sock = socket.socket()
    sock.bind(('', 0))
    return sock.getsockname()[1]


# Will be set by one-time setUp
server_thread = None
build_id = None


def setUpModule():
    """Sets up the environment for testing."""
    global server_thread, build_id

    FLAGS.fetch_frequency = 100
    FLAGS.polltime = 0.01
    FLAGS.ignore_auth = True
    FLAGS.port = get_free_port()
    FLAGS.queue_server_prefix = (
        'http://localhost:%d/api/work_queue' % FLAGS.port)
    FLAGS.release_server_prefix = 'http://localhost:%d/api' % FLAGS.port

    db.drop_all()
    db.create_all()

    runworker.run_workers()
    server_thread = threading.Thread(target=runserver.run_server)
    server_thread.setDaemon(True)
    server_thread.start()


def create_build():
    """Creates a new build and returns its ID."""
    build = models.Build(name='My build')
    db.session.add(build)
    db.session.commit()
    return build.id


class HtmlRewritingTest(unittest.TestCase):
    """Tests the HTML rewriting functions."""

    def testAll(self):
        """Tests all the variations."""
        base_url = 'http://www.example.com/my-url/here'
        def test(test_url):
            data = '<a href="%s">my link here</a>' % test_url
            result = site_diff.extract_urls(base_url, data)
            if not result:
                return None
            return list(result)[0]

        self.assertEquals('http://www.example.com/my-url/dummy_page2.html',
                          test('dummy_page2.html'))

        self.assertEquals('http://www.example.com/',
                          test('/'))

        self.assertEquals('http://www.example.com/mypath-here',
                          test('/mypath-here'))

        self.assertEquals(None, test('#fragment-only'))

        self.assertEquals('http://www.example.com/my/path/over/here.html',
                          test('/my/path/01/13/../../over/here.html'))

        self.assertEquals('http://www.example.com/my/path/01/over/here.html',
                          test('/my/path/01/13/./../over/here.html'))

        self.assertEquals('http://www.example.com/my-url/same-directory.html',
                          test('same-directory.html'))

        self.assertEquals('http://www.example.com/relative-but-no/child',
                          test('../../relative-but-no/child'))

        self.assertEquals('http://www.example.com/too/many/relative/paths',
                          test('../../../../too/many/relative/paths'))

        self.assertEquals(
            'http://www.example.com/this/is/scheme-relative.html',
            test('//www.example.com/this/is/scheme-relative.html'))

        self.assertEquals(
            'http://www.example.com/okay-then',    # Scheme changed
            test('https://www.example.com/okay-then#blah'))

        self.assertEquals('http://www.example.com/another-one',
                          test('http://www.example.com/another-one'))

        self.assertEquals('http://www.example.com/this-has/a',
                          test('/this-has/a?query=string'))

        self.assertEquals(
            'http://www.example.com/this-also-has/a/',
            test('/this-also-has/a/?query=string&but=more-complex'))

        self.assertEquals(
            'http://www.example.com/relative-with/some-(parenthesis%20here)',
            test('/relative-with/some-(parenthesis%20here)'))

        self.assertEquals(
            'http://www.example.com/relative-with/some-(parenthesis%20here)',
            test('//www.example.com/relative-with/some-(parenthesis%20here)'))

        self.assertEquals(
            'http://www.example.com/relative-with/some-(parenthesis%20here)',
            test('http://www.example.com/relative-with/some-'
                 '(parenthesis%20here)'))


def webserver(func):
    """Runs the given function as a webserver.

    Function should take one argument, the path of the request. Should
    return tuple (status, content_type, content) or Nothing if there is no
    response.
    """
    class HandlerClass(BaseHTTPServer.BaseHTTPRequestHandler):
        def do_GET(self):
            output = func(self.path)
            if output:
                code, content_type, result = output
            else:
                code, content_type, result = 404, 'text/plain', 'Not found!'

            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            if result:
                self.wfile.write(result)

    server = BaseHTTPServer.HTTPServer(('', 0), HandlerClass)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server


class SiteDiffTest(unittest.TestCase):
    """Tests for the SiteDiff workflow."""

    def setUp(self):
        """Sets up the test harness."""
        self.coordinator = workers.get_coordinator()
        self.build_id = create_build()

    def output_readlines(self, path):
        """Reads the lines of an output file, stripping newlines."""
        return [
            x.strip() for x in open(join(self.output_dir, path)).xreadlines()]

    def testFirstSnapshot(self):
        """Tests taking the very first snapshot."""
        @webserver
        def test(path):
            if path == '/':
                return 200, 'text/html', 'Hello world!'

        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            upload_build_id=self.build_id)
        test.shutdown()

        # Wait for all tasks to finish.

        self.assertTrue(exists(join(self.output_dir, '__run.log')))
        self.assertTrue(exists(join(self.output_dir, '__run.png')))
        self.assertTrue(exists(join(self.output_dir, '__config.js')))
        self.assertTrue(exists(join(self.output_dir, 'url_paths.txt')))

        self.assertEquals(
            ['/'],
            self.output_readlines('url_paths.txt'))

    def testNoDifferences(self):
        """Tests crawling the site end-to-end."""
        @webserver
        def test(path):
            if path == '/':
                return 200, 'text/html', 'Hello world!'

        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            output_dir=self.reference_dir,
            coordinator=self.coordinator)

        self.coordinator = workers.get_coordinator()
        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            output_dir=self.output_dir,
            reference_dir=self.reference_dir,
            coordinator=self.coordinator)
        test.shutdown()

        self.assertTrue(exists(join(self.reference_dir, '__run.log')))
        self.assertTrue(exists(join(self.reference_dir, '__run.png')))
        self.assertTrue(exists(join(self.reference_dir, '__config.js')))
        self.assertTrue(exists(join(self.reference_dir, 'url_paths.txt')))

        self.assertTrue(exists(join(self.output_dir, '__run.log')))
        self.assertTrue(exists(join(self.output_dir, '__run.png')))
        self.assertTrue(exists(join(self.output_dir, '__ref.log')))
        self.assertTrue(exists(join(self.output_dir, '__ref.png')))
        self.assertFalse(exists(join(self.output_dir, '__diff.png'))) # No diff
        self.assertTrue(exists(join(self.output_dir, '__diff.log')))
        self.assertTrue(exists(join(self.output_dir, '__config.js')))
        self.assertTrue(exists(join(self.output_dir, 'url_paths.txt')))

    def testOneDifference(self):
        """Tests when there is one found difference."""
        @webserver
        def test(path):
            if path == '/':
                return 200, 'text/html', 'Hello world!'

        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            output_dir=self.reference_dir,
            coordinator=self.coordinator)
        test.shutdown()

        @webserver
        def test(path):
            if path == '/':
                return 200, 'text/html', 'Hello world a little different!'

        self.coordinator = workers.get_coordinator()
        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            output_dir=self.output_dir,
            reference_dir=self.reference_dir,
            coordinator=self.coordinator)
        test.shutdown()

        self.assertTrue(exists(join(self.reference_dir, '__run.log')))
        self.assertTrue(exists(join(self.reference_dir, '__run.png')))
        self.assertTrue(exists(join(self.reference_dir, '__config.js')))
        self.assertTrue(exists(join(self.reference_dir, 'url_paths.txt')))

        self.assertTrue(exists(join(self.output_dir, '__run.log')))
        self.assertTrue(exists(join(self.output_dir, '__run.png')))
        self.assertTrue(exists(join(self.output_dir, '__ref.log')))
        self.assertTrue(exists(join(self.output_dir, '__ref.png')))
        self.assertTrue(exists(join(self.output_dir, '__diff.png'))) # Diff!!
        self.assertTrue(exists(join(self.output_dir, '__diff.log')))
        self.assertTrue(exists(join(self.output_dir, '__config.js')))
        self.assertTrue(exists(join(self.output_dir, 'url_paths.txt')))

    def testCrawler(self):
        """Tests that the crawler behaves well.

        Specifically:
            - Finds new links in HTML data
            - Avoids non-HTML pages
            - Respects ignore patterns specified on flags
        """
        @webserver
        def test(path):
            if path == '/':
                return 200, 'text/html', (
                    'Hello world! <a href="/stuff">x</a> '
                    '<a href="/ignore">y</a>')
            elif path == '/stuff':
                return 200, 'text/html', 'Stuff page <a href="/avoid">x</a>'
            elif path == '/avoid':
                return 200, 'text/plain', 'Ignore me!'

        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            ignore_prefixes=['/ignore'],
            coordinator=self.coordinator)
        test.shutdown()

        self.assertTrue(exists(join(self.output_dir, '__run.log')))
        self.assertTrue(exists(join(self.output_dir, '__run.png')))
        self.assertTrue(exists(join(self.output_dir, '__config.js')))
        self.assertTrue(exists(join(self.output_dir, 'url_paths.txt')))
        self.assertFalse(exists(join(self.output_dir, '_ignore_run.log')))
        self.assertFalse(exists(join(self.output_dir, '_ignore_run.png')))
        self.assertFalse(exists(join(self.output_dir, '_ignore_config.js')))

        self.assertEquals(
            ['/', '/stuff'],
            self.output_readlines('url_paths.txt'))

    def testNotFound(self):
        """Tests when a URL in the crawl is not found."""
        @webserver
        def test(path):
            if path == '/':
                return 200, 'text/html', (
                    'Hello world! <a href="/missing">x</a>')
            elif path == '/missing':
                return 404, 'text/plain', 'Nope'

        site_diff.real_main(
            start_url='http://%s:%d/' % test.server_address,
            ignore_prefixes=['/ignore'],
            output_dir=self.output_dir,
            coordinator=self.coordinator)
        test.shutdown()

        self.assertTrue(exists(join(self.output_dir, '__run.log')))
        self.assertTrue(exists(join(self.output_dir, '__run.png')))
        self.assertTrue(exists(join(self.output_dir, '__config.js')))
        self.assertTrue(exists(join(self.output_dir, 'url_paths.txt')))

        self.assertEquals(
            ['/'],
            self.output_readlines('url_paths.txt'))

        self.fail()

    def testDiffNotLinkedUrlsFound(self):
        """Tests when a URL in the old set exists but is not linked."""
        self.fail()

    def testDiffNotFound(self):
        """Tests when a URL in the old set is a 404 in the new set."""
        self.fail()

    def testSuccessAfterRetry(self):
        """Tests that URLs that return errors will be retried."""
        self.fail()

    def testFailureAfterRetry(self):
        """Tests when repeated retries of a URL fail."""
        self.fail()


def main(argv):
    gflags.MarkFlagAsRequired('phantomjs_binary')
    gflags.MarkFlagAsRequired('phantomjs_script')

    try:
        argv = FLAGS(argv)
    except gflags.FlagsError, e:
        print '%s\nUsage: %s ARGS\n%s' % (e, sys.argv[0], FLAGS)
        sys.exit(1)

    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main(argv=argv)


if __name__ == '__main__':
    main(sys.argv)
