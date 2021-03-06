#!/usr/bin/env python
#
# Copyright (c) 2012-2013 SEOmoz, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

'''This is a module for dealing with urls. In particular, sanitizing them.'''

import re
import sys
if sys.version_info[0] == 3:
    from urllib.parse import quote as urlquote
    from urllib.parse import unquote as urlunquote
    from urllib.parse import urlparse, urlunparse, urljoin
    byte_string = bytes
    string_type = (str, bytes)
    unicode_text = str
else:
    from urllib import quote as urlquote
    from urllib import unquote as urlunquote
    from urlparse import urlparse, urlunparse, urljoin
    byte_string = str
    string_type = basestring
    unicode_text = unicode
from unicodedata import normalize as unicodenormalize

# For publicsuffix utilities
from publicsuffix import PublicSuffixList
psl = PublicSuffixList()

# The default ports associated with each scheme
PORTS = {
    'http': 80,
    'https': 443
}


def parse(url, encoding='utf-8'):
    '''Parse the provided url string and return an URL object'''
    return URL.parse(url, encoding)


class URL(object):
    '''
    For more information on how and what we parse / sanitize:
        http://tools.ietf.org/html/rfc1808.html
    The more up-to-date RFC is this one:
        http://www.ietf.org/rfc/rfc3986.txt
    '''

    # Via http://www.ietf.org/rfc/rfc3986.txt
    GEN_DELIMS = ":/?#[]@"
    SUB_DELIMS = "!$&'()*+,;="
    ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    DIGIT = "0123456789"
    UNRESERVED = ALPHA + DIGIT + "-._~"
    RESERVED = GEN_DELIMS + SUB_DELIMS
    PCHAR = UNRESERVED + SUB_DELIMS + ":@"
    PATH = PCHAR + "/"
    QUERY = PCHAR + "/?"
    FRAGMENT = PCHAR + "/?"
    USERINFO = UNRESERVED + SUB_DELIMS + ":"

    PERCENT_ESCAPING_RE = re.compile('(%([a-fA-F0-9]{2})|.)', re.S)

    @classmethod
    def parse(cls, url, encoding):
        '''Parse the provided url, and return a URL instance'''
        if isinstance(url, byte_string):
            url = url.decode(encoding)
        url = unicodenormalize('NFC', url)
        if sys.version_info[0] == 2:
            url = url.encode('utf-8')

        parsed = urlparse(url)

        try:
            port = parsed.port
        except ValueError:
            port = None

        userinfo = parsed.username
        if userinfo and parsed.password:
            userinfo += ':%s' % parsed.password

        return cls(parsed.scheme, parsed.hostname, port,
            parsed.path, parsed.params, parsed.query, parsed.fragment, userinfo)

    def __init__(self, scheme, host, port, path, params, query, fragment, userinfo=None):
        if sys.version_info[0] == 3:
            if isinstance(scheme, byte_string):
                scheme = scheme.decode('utf-8')
            if isinstance(host, byte_string):
                host = host.decode('utf-8')
            if isinstance(path, byte_string):
                path = path.decode('utf-8')
            if isinstance(params, byte_string):
                params = params.decode('utf-8')
            if isinstance(query, byte_string):
                query = query.decode('utf-8')
            if isinstance(fragment, byte_string):
                fragment = fragment.decode('utf-8')
            if isinstance(userinfo, byte_string):
                userinfo = userinfo.decode('utf-8')
        else:
            if isinstance(scheme, unicode_text):
                scheme = scheme.encode('utf-8')
            if isinstance(host, unicode_text):
                host = host.encode('utf-8')
            if isinstance(path, unicode_text):
                path = path.encode('utf-8')
            if isinstance(params, unicode_text):
                params = params.encode('utf-8')
            if isinstance(query, unicode_text):
                query = query.encode('utf-8')
            if isinstance(fragment, unicode_text):
                fragment = fragment.encode('utf-8')
            if isinstance(userinfo, unicode_text):
                userinfo = userinfo.encode('utf-8')
        self._scheme = scheme
        self._host = host
        self._port = port
        self._path = path or '/'
        self._params = re.sub(r'^;+', '', params)
        self._params = re.sub(r'^;|;$', '', re.sub(r';{2,}', ';', self._params))
        # Strip off extra leading ?'s
        self._query = re.sub(r'^\?+', '', query)
        self._query = re.sub(r'^&|&$', '', re.sub(r'&{2,}', '&', self._query))
        self._fragment = fragment
        self._userinfo = userinfo

    def equiv(self, other):
        '''Return true if this url is equivalent to another'''
        if isinstance(other, string_type):
            _other = self.parse(other, 'utf-8')
        else:
            _other = self.parse(str(other), 'utf-8')

        _self = self.parse(str(self), 'utf-8')
        _self.canonical().defrag().abspath().escape().punycode()
        _other.canonical().defrag().abspath().escape().punycode()

        result = (
            _self._scheme   == _other._scheme   and
            _self._host     == _other._host     and
            _self._path     == _other._path     and
            _self._params   == _other._params   and
            _self._query    == _other._query)

        if result:
            if _self._port and not _other._port:
                # Make sure _self._port is the default for the scheme
                return _self._port == PORTS.get(_self._scheme, None)
            elif _other._port and not _self._port:
                # Make sure _other._port is the default for the scheme
                return _other._port == PORTS.get(_other._scheme, None)
            else:
                return _self._port == _other._port
        else:
            return False

    def __eq__(self, other):
        '''Return true if this url is /exactly/ equal to another'''
        if isinstance(other, string_type):
            return self.__eq__(self.parse(other, 'utf-8'))
        return (
            self._scheme   == other._scheme   and
            self._host     == other._host     and
            self._path     == other._path     and
            self._port     == other._port     and
            self._params   == other._params   and
            self._query    == other._query    and
            self._fragment == other._fragment and
            self._userinfo == other._userinfo)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        netloc = self._host or ''
        if self._port:
            netloc += (':' + str(self._port))

        if self._userinfo is not None:
            netloc = '%s@%s' % (self._userinfo, netloc)

        result = urlunparse((self._scheme, netloc, self._path, self._params,
                            self._query, self._fragment))
        return result

    def __repr__(self):
        return '<url.URL object "%s" >' % str(self)

    def canonical(self):
        '''Canonicalize this url. This includes reordering parameters and args
        to have a consistent ordering'''
        self._query = '&'.join(sorted([q for q in self._query.split('&')]))
        self._params = ';'.join(sorted([q for q in self._params.split(';')]))
        return self

    def defrag(self):
        '''Remove the fragment from this url'''
        self._fragment = None
        return self

    def deparam(self, params):
        '''Strip any of the provided parameters out of the url'''
        lowered = set([p.lower() for p in params])
        def function(name, _):
            return name.lower() in lowered
        return self.filter_params(function)

    def filter_params(self, function):
        '''Remove parameters if function(name, value)'''
        def keep(query):
            name, _, value = query.partition('=')
            return not function(name, value)
        self._query = '&'.join(q for q in self._query.split('&') if q and keep(q))
        self._params = ';'.join(q for q in self._params.split(';') if q and keep(q))
        return self

    def deuserinfo(self):
        '''Remove any userinfo'''
        self._userinfo = None
        return self

    def abspath(self):
        '''Clear out any '..' and excessive slashes from the path'''
        # Remove double forward-slashes from the path
        path = re.sub(r'\/{2,}', '/', self._path)
        # With that done, go through and remove all the relative references
        unsplit = []
        directory = False
        for part in path.split('/'):
            # If we encounter the parent directory, and there's
            # a segment to pop off, then we should pop it off.
            if part == '..' and (not unsplit or unsplit.pop() != None):
                directory = True
            elif part != '.':
                unsplit.append(part)
                directory = False
            else:
                directory = True

        # With all these pieces, assemble!
        if directory:
            # If the path ends with a period, then it refers to a directory,
            # not a file path
            self._path = '/'.join(unsplit) + '/'
        else:
            self._path = '/'.join(unsplit)
        return self

    def sanitize(self):
        '''A shortcut to abspath and escape'''
        return self.abspath().escape()

    @staticmethod
    def percent_encode(raw, safe):
        def replacement(match):
            string = match.group(1)
            if len(string) == 1:
                if string in safe:
                    return string
                else:
                    if sys.version_info[0] == 3:
                        e = ['%%%02X' % b for b in string.encode('utf-8')]
                        return ''.join(e)
                    else:
                        return '%%%02X' % ord(string)
            else:
                # Replace any escaped entities with their equivalent if needed.
                character = chr(int(match.group(2), 16))
                if (character in safe) and not (character in URL.RESERVED):
                    return character
                return string.upper()

        return URL.PERCENT_ESCAPING_RE.sub(replacement, raw)

    def escape(self, strict=False):
        '''Make sure that the path is correctly escaped'''
        if strict:
            self._path = self.percent_encode(self._path, URL.PATH)
            self._query = self.percent_encode(self._query, URL.QUERY)
            self._params = self.percent_encode(self._params, URL.QUERY)
            if self._userinfo:
                self._userinfo = self.percent_encode(self._userinfo, URL.USERINFO)
            return self
        else:
            self._path = urlquote(urlunquote(self._path), safe=URL.PATH)
            # Safe characters taken from:
            #    http://tools.ietf.org/html/rfc3986#page-50
            self._query = urlquote(urlunquote(self._query), safe=URL.QUERY)
            # The safe characters for URL parameters seemed a little more vague.
            # They are interpreted here as *pchar despite this page, since the
            # updated RFC seems to offer no replacement
            #    http://tools.ietf.org/html/rfc3986#page-54
            self._params = urlquote(urlunquote(self._params), safe=URL.QUERY)
            if self._userinfo:
                self._userinfo = urlquote(urlunquote(self._userinfo),
                    safe=URL.USERINFO)
            return self

    def unescape(self):
        '''Unescape the path'''
        self._path = urlunquote(self._path)
        return self

    def encode(self, encoding):
        '''Return the url in an arbitrary encoding'''
        if sys.version_info[0] == 3:
            return str(self).encode(encoding)
        else:
            return str(self).decode('utf-8').encode(encoding)

    def relative(self, path, encoding='utf-8'):
        '''Evaluate the new path relative to the current url'''
        if isinstance(path, byte_string):
            path = path.decode(encoding)
        path = unicodenormalize('NFC', path)
        if sys.version_info[0] == 3:
            newurl = urljoin(self.unicode(), path)
        else:
            newurl = urljoin(self.utf8(), path.encode('utf-8'))

        return URL.parse(newurl, 'utf-8')

    def punycode(self):
        '''Convert to punycode hostname'''
        if self._host:
            if sys.version_info[0] == 2:
                self._host = self._host.decode('utf-8')
            self._host = self._host.encode('idna')
            if sys.version_info[0] == 3:
                self._host = self._host.decode('utf-8')
            return self
        raise TypeError('Cannot punycode a relative url (%s)' % repr(self))

    def unpunycode(self):
        '''Convert to an unpunycoded hostname'''
        if self._host:
            if sys.version_info[0] == 3:
                self._host = self._host.encode('utf-8').decode('idna')
            else:
                self._host = self._host.decode('utf-8').decode('idna').encode('utf-8')
            return self
        raise TypeError('Cannot unpunycode a relative url (%s)' % repr(self))

    ###########################################################################
    # Information about the domain
    ###########################################################################
    def pld(self):
        '''Return the 'pay-level domain' of the url
            (http://moz.com/blog/what-the-heck-should-we-call-domaincom)'''
        if self._host:
            result = psl.get_public_suffix(self._host)
            if sys.version_info[0] == 2:
                resunt = result.encode('utf-8')
            return result
        return ''

    def tld(self):
        '''Return the top-level domain of a url'''
        if self._host:
            return '.'.join(self.pld().split('.')[1:])
        return ''

    ###########################################################################
    # Information about the type of url it is
    ###########################################################################
    def absolute(self):
        '''Return True if this is a fully-qualified URL with a hostname and
        everything'''
        return bool(self._host)

    ###########################################################################
    # Get a string representation. These methods can't be chained, as they
    # return strings
    ###########################################################################
    def unicode(self):
        '''Return a unicode version of this url'''
        if sys.version_info[0] == 3:
            return str(self)
        else:
            return str(self).decode('utf-8')

    def utf8(self):
        '''Return a utf-8 version of this url'''
        if sys.version_info[0] == 3:
            return str(self).encode('utf-8')
        else:
            return str(self)
