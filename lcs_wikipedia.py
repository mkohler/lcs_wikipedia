#! /usr/bin/env python2.6
# Copyright (c) 2010 Mark Kohler
"""Find the longest common substring in two random Wikipedia articles."""

import collections
import optparse
import re
import sys
import unittest
import urllib2
import xml.etree.ElementTree as etree


def main():
    """Download two articles and compute their longest common substring.

    To find more interesting substrings, filter out as much of the Wikipedia
    boilerplate as possible.
    """
    usage = (
    '''%prog [-h|-t]''')

    parser = optparse.OptionParser(usage, description=__doc__)
    parser.add_option('-t', '--test', action='store_true', default=False,
                      help='''Test this program''')
    (options, args) = parser.parse_args()

    if options.test:
        # Remove the options flag and run the tests.
        sys.argv = sys.argv[0:1]
        return unittest.main()

    print "Requesting two random Wikipedia articles..."
    try:
        articles = [get_random_article() for index in range(2)]
    except urllib2.URLError, error:
        print >> sys.stderr, ("\nError: Unable to retrieve articles, %s" %
                            error.reason[1])
        sys.exit(1)

    for article in articles:
        print "  Title: %s" % article.title

    print "Computing longest common sequence(s) in articles..."

    for seq in LCS(articles[0].get_text(), articles[1].get_text()):
        print 'sequence: %r' % seq


def get_random_article():
    """Download random article and extract the title.

    The Wikipedia random URL redirects one to a random Wikipedia article.
    After the redirection, one can retrieve the article title from the
    end of the URL.

    The export_url returns the article with less of the boilerplate
    that usually surrounds a Wikipedia article.
    """
    random_url = 'http://en.wikipedia.org/wiki/Special:Random/'
    export_url = 'http://en.wikipedia.org/wiki/Special:Export/'

    # Build a custom opener as Wikipedia rejects the default urllib2
    # user-agent in order to discourage crawlers.
    wiki_opener = urllib2.build_opener()
    wiki_opener.addheaders = [('User-agent', 'coincidence/0.1')]

    redirect_response = wiki_opener.open(random_url)
    title = redirect_response.geturl().split('/')[-1]
    response = wiki_opener.open('%s%s' % (export_url, title))

    return Article(title, response)


class Article(object):

    def __init__(self, title, response):
        self.title = title
        self.response = response

    def get_text(self):
        """Parse and filter the page to get just the article text."""
        return strip_markup(get_markup_text(self.response))


def get_markup_text(response):
    """Parse HTML, and find an element named something_that_ends_with_text.

    Return that element's text attribute.
    """
    tree = etree.ElementTree()
    tree.parse(response)
    for elem in tree.getiterator():
        if elem.tag.endswith('text'):
            return elem.text


def strip_markup(text):
    """Remove markup e.g. [this], [[that]], {{those}}, ==the other==

    The contents within these brackets is often boilerplate and as such, it
    makes the longest common subsequence less interesting.
    """
    brackets = r'\[[^\[\]]*\]'
    dbl_brackets = r'\[\[[^\[\]]*\]\]'
    dbl_braces = r'\{\{[^{}]*\}\}'
    equal_signs = r'==[^=]*=='

    patterns = [brackets, dbl_brackets, dbl_braces, equal_signs]
    markup_rx = re.compile('|'.join(patterns))
    return markup_rx.sub('', text)


# This routine uses a dynamic programming algorithm, checking each character of
# one string against each character of the other. Its runtime performance is
# O(len(str1) * len(str2)).
#
# To save memory, this implemention only saves the non-zero values of the
# current and previous rows of the dynamic programming matrix. Thus, in the
# worst case, where the strings of similar length and have a long common
# substring, the memory use will be roughly twice the combined length of the
# strings.
#
# Much greater performance can be achieved by using a generalized suffix tree
# instead of dynamic programming: O(len(str1) + len(str2)), but at the cost of
# much higher memory usage and a more complicated algorithm. See Gusfield 1999.


def longest_common_substring(str1, str2):
    """Compute LCS using dynamic programming algorithm."""

    # To save memory, use the shorter string as the "horizontal" or inner loop.
    if len(str1) < len(str2):
        h_str = str1
        v_str = str2
    else:
        h_str = str2
        v_str = str1

    # Initialize state variables. Use defaultdicts so that we don't have
    # to store all of the zero values in the dynamic programming matrix.
    prev_row = collections.defaultdict(int)
    row = collections.defaultdict(int)
    longest_strings = set()
    max_length_seen = 0

    # Compare each vertical character, with each character in the horizontal
    # string, and then go to the next vertical character.
    for v_char in v_str:
        for i, h_char in enumerate(h_str):

            # If the characters don't match, do nothing.
            # If they do, update the state variables.
            if h_char == v_char:

                # If there's a match, then look back to the previous
                # row and column to see how many previous characters
                # matched. Add one to get the value for this location.
                common_str_len = prev_row[i-1] + 1
                row[i] = common_str_len

                # If this common substring isn't one of the longest
                # we've seen, continue.
                if common_str_len < max_length_seen:
                    continue

                # Extact the common substring from the original string
                # by looking back from our current location, i, by the
                # length of the string.
                common_substr = h_str[i - common_str_len + 1:(i + 1)]

                # Either add this string to the set of equal-length strings,
                # or if this one breaks the record, start a new set.
                if common_str_len == max_length_seen:
                    longest_strings.add(common_substr)
                elif row[i] >= max_length_seen:
                    max_length_seen = common_str_len
                    longest_strings = set([common_substr])

        # After processing each row, discard the oldest row.
        prev_row = row
        row = collections.defaultdict(int)

    return list(longest_strings)


LCS = longest_common_substring


class TestParseAndFilter(unittest.TestCase):

    def test_parse(self):
        """Test the parsing mechanism, but don't recreate Wikipedia XML."""
        import StringIO
        orig_str = '<blah><foo><some_text>the article</some_text></foo></blah>'
        response = StringIO.StringIO(orig_str)

        self.assertEqual('the article', get_markup_text(response))

    def test_strip_markup_self(self):
        self.assertEqual('some text', strip_markup('[[blah]]some text[blah]'))
        self.assertEqual('some text',
                         strip_markup('==blah==some text{{blah}}'))


class TestLCS(unittest.TestCase):

    def test_some_strings(self):
        self.assertEqual(['dxy'], LCS('xydxyaa', 'abcdxyz'))
        self.assertEqual(['substring'],
                         LCS('aaaaaasubstringxxxxxx',
                                           'absubstringzzz'))

        self.assertEqual(['shorter'],
                         LCS('shorter', 'shorterlonger'))
        self.assertEqual(['shorter'],
                         LCS('shorter', 'longershorter'))

    def test_multiple_same_length(self):
        substrs = LCS('xxx123yyyy456zzz', '789zzz012xxx345yyy')
        self.assertEqual(3, len(substrs))
        self.assert_('xxx' in substrs)
        self.assert_('yyy' in substrs)
        self.assert_('zzz' in substrs)

    def test_no_common_substrings(self):
        self.assertEqual([], LCS('123456', 'abcdef'))

    def test_empty_string(self):
        self.assertEqual([], LCS('somestring', ''))


if __name__ == '__main__':
    sys.exit(main())
