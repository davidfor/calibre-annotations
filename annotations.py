#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2014-2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import hashlib, re

# calibre Python 3 compatibility.
import six
from six import text_type as unicode

from datetime import datetime
from xml.sax.saxutils import escape

from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag
from calibre_plugins.annotations.common_utils import Logger
from calibre_plugins.annotations.config import plugin_prefs

try:
    from PyQt5.QtGui import QColor
except ImportError:
    from PyQt4.QtGui import QColor

COLOR_MAP = {
                  'Blue': {'bg': '#b1ccf3', 'fg': 'black'},
                  'Gray': {'bg': 'LightGray', 'fg': 'black'},
                 'Green': {'bg': '#c8eb7b', 'fg': 'black'},
                  'Pink': {'bg': '#f4b0d2', 'fg': 'black'},
                'Purple': {'bg': '#d8b0ef', 'fg': 'black'},
                   'Red': {'bg': 'red', 'fg': 'black'},
             'Underline': {'bg': 'transparent', 'fg': 'blue'},
                'Yellow': {'bg': '#f4e681', 'fg': 'black'},
            }

ANNOTATION_DIV_STYLE = "margin:0 0 0.5em 0"
ANNOTATIONS_HEADER = '''<div class="user_annotations" style="margin:0"></div>'''


class Annotation(object):
    """
    A single instance of an annotation
    """
    div_style = "margin-bottom:1em"

    all_fields = [
                    'description',
                    'genre',
                    'hash',
                    'highlightcolor',
                    'location',
                    'location_sort',
                    'note',
                    'reader_app',
                    'text',
                    'timestamp',
                    ]

    def __init__(self, annotation):
        for p in self.all_fields:
            setattr(self, p, annotation.get(p))

    def __str__(self):
        return '\n'.join(["%s: %s" % (field, getattr(self, field, None)) for field in self.all_fields])

class Annotations(Annotation, Logger):
    '''
    A collection of Annotation objects
    annotations: [{title:, path:, timestamp:, genre:, highlightcolor:, text:} ...]
    Inherits Annotation solely to share style characteristics for agroups
    '''
    @property
    def annotations(self):
        return self.__annotations

    def __init__(self, opts, title=None, annotations=None, cid=None, genre=None):

        self.opts = opts
        self.cid = cid
        self.title = title
        self.genre = genre
        self.__annotations = []
        if annotations:
            self.annotations = annotations

    def _annotation_sorter(self, annotation):
        '''
        Input: [01 Feb 2003 12:34:56 ...
        Output (conforming): 2003-02-01-12:34:56
        Output (non-conforming): 0
        '''
        if False:
            key = self._timestamp_to_datestr(annotation.timestamp)
            MONTHS = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            if not re.match('\d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2}', key):
                return "!%s" % key
            sts_elems = key[1:-1].split(' ')
            year = sts_elems[2]
            month = "%02d" % MONTHS.index(sts_elems[1])
            day = sts_elems[0]
            time = sts_elems[3]
            return "%s-%s-%s-%s" % (year, month, day, time)
        else:
            return annotation.location_sort

    def _timestamp_to_datestr(self, timestamp):
        '''
        Convert timestamp to
        01 Jan 2011 12:34:56
        '''
        from calibre_plugins.annotations.appearance import default_timestamp
        d = datetime.fromtimestamp(float(timestamp))
        friendly_timestamp_format = plugin_prefs.get('appearance_timestamp_format', default_timestamp)
        try:
            friendly_timestamp = d.strftime(friendly_timestamp_format)
        except:
            friendly_timestamp = d.strftime(default_timestamp)
        return friendly_timestamp

    def to_HTML(self, header=''):
        '''
        Generate HTML with user-specified CSS, element order
        '''
        # Retrieve CSS prefs
        from calibre_plugins.annotations.appearance import default_elements
        stored_css = plugin_prefs.get('appearance_css', default_elements)

        elements = []
        for element in stored_css:
            elements.append(element['name'])
            if element['name'] == 'Note':
                note_style = re.sub('\n', '', element['css'])
            elif element['name'] == 'Text':
                text_style = re.sub('\n', '', element['css'])
            elif element['name'] == 'Timestamp':
                ts_style = re.sub('\n', '', element['css'])

        # Additional CSS for timestamp color and bg to be formatted
        datetime_style = ("background-color:{0};color:{1};" + ts_style)

        # Order the elements according to stored preferences
        comments_body = ''
        for element in elements:
            if element == 'Text':
                comments_body += '{text}'
            elif element == 'Note':
                comments_body += '{note}'
            elif element == 'Timestamp':
                ts_css = '''<table cellpadding="0" width="100%" style="{ts_style}" color="{color}">
                                <tr>
                                    <td class="location" style="text-align:left">{location}</td>
                                    <td class="timestamp" uts="{unix_timestamp}" style="text-align:right">{friendly_timestamp}</td>
                                </tr>
                            </table>'''
                comments_body += re.sub(r'>\s+<', r'><', ts_css)
#         self._log_location("comments_body='%s'" % comments_body)

        if self.annotations:
            html_color_pattern = re.compile("^#(?:[0-9a-fA-F]{3,4}){1,2}$")
            soup = BeautifulSoup(ANNOTATIONS_HEADER)
            dtc = 0

            # Add the annotations
            for i, agroup in enumerate(sorted(self.annotations, key=self._annotation_sorter)):
#                 self._log_location("agroup='%s'" % agroup)
                location = agroup.location
                if location is None:
                    location = ''

                friendly_timestamp = self._timestamp_to_datestr(agroup.timestamp)

                text = ''
                if agroup.text:
#                     self._log_location("agroup.text='%s'" % agroup.text)
                    for agt in agroup.text:
#                         self._log_location("agt='%s'" % agt)
                        text += '<p class="highlight" style="{0}">{1}</p>'.format(text_style, agt)

                note = ''
                if agroup.note:
#                     self._log_location("agroup.note='%s'" % agroup.note)
                    for agn in agroup.note:
#                         self._log_location("agn='%s'" % agn)
                        note += '<p class="note" style="{0}">{1}</p>'.format(note_style, agn)

                if agroup.highlightcolor and html_color_pattern.match(agroup.highlightcolor):
                   msg = "Found valid HTML color '%s', using" % agroup.highlightcolor
                   dt_bgcolor = agroup.highlightcolor

                   # Currently annotations only store the foreground color. If it's not a known color, then
                   # we should pick the background color as black or white based on the overall lightness of
                   # the color.
                   color = QColor(dt_bgcolor)
                   if color.lightness() >= 128:
                       dt_fgcolor = "#000000"
                   else:
                       dt_fgcolor = "#FFFFFF"
                   self._log_location(f"HTML color lightness is {color.lightness()}, using {dt_bgcolor}")
                elif agroup.highlightcolor in COLOR_MAP:
                    msg = "Found match for %s in known colors" % agroup.highlightcolor
                    dt_bgcolor = COLOR_MAP[agroup.highlightcolor]['bg']
                    dt_fgcolor = COLOR_MAP[agroup.highlightcolor]['fg']
                else:
                    msg = "Unknown color '%s' specified, using default" % agroup.highlightcolor
                    dt_bgcolor = plugin_prefs.get('appearance_highlight_bg')
                    dt_fgcolor = plugin_prefs.get('appearance_highlight_fg')

                self._log_location(msg)

                if agroup.hash is not None:
                    # Use existing hash when re-rendering
                    annotation_hash = agroup.hash
                else:
                    m = hashlib.md5()
                    m.update(text.encode('utf-8'))
                    m.update(note.encode('utf-8'))
                    annotation_hash = m.hexdigest()

                try:
                    ka_soup = BeautifulSoup()
                    divTag = ka_soup.new_tag('div')
#                     self._log_location("Used ka_soup.new_tag to create tag: %s" % divTag)
                except:
                    divTag = Tag(BeautifulSoup(), 'div')
#                     self._log_location("Used Tag(BeautifulSoup() to create tag: %s" % divTag)

                content_args = {
                            'color': agroup.highlightcolor,
                            'friendly_timestamp': friendly_timestamp,
                            'location': location,
                            'note': note,
                            'text': text,
                            'ts_style': datetime_style.format(dt_bgcolor, dt_fgcolor),
                            'unix_timestamp': agroup.timestamp,
                            }
#                 self._log_location("Generated comment soup: %s" % BeautifulSoup(comments_body.format(**content_args)))
                comments_body_soup = BeautifulSoup(comments_body.format(**content_args))
#                 self._log_location("Generated comment soup: comments_body_soup=%s" % comments_body_soup)
#                 self._log_location("Generated comment soup: comments_body_soup.body=%s" % comments_body_soup.body)
#                 self._log_location("Generated comment soup: comments_body_soup.body.children=%s" % comments_body_soup.body.children)
#                 self._log_location("Generated comment soup: comments_body_soup.body.contents=%s" % comments_body_soup.body.contents)
#                 self._log_location("Generated comment soup: len(comments_body_soup.body.contents)=%s" % len(comments_body_soup.body.contents))
#                 for i in range(0, len(comments_body_soup.body.contents)):
#                     self._log_location("i=%s" % i)
#                     self._log_location("comment_body_tag=%s" % comments_body_soup.body.contents[i])
                try: #
                    while len(comments_body_soup.body.contents) > 0:
                        # self._log_location("comment_body_tag=%s" % comments_body_soup.body.contents[0])
                        divTag.append(comments_body_soup.body.contents[0])
                except Exception as e:
                    self._log_location("Problem with comments_body_soup - Exception=%s, comments_body='%s', content_args=%s" % (e, comments_body_soup, content_args))

                divTag['class'] = "annotation"
                divTag['genre'] = ''
                if agroup.genre:
                    divTag['genre'] = escape(agroup.genre)
                divTag['hash'] = annotation_hash
                divTag['location_sort'] = agroup.location_sort
                divTag['reader'] = agroup.reader_app
                divTag['style'] = ANNOTATION_DIV_STYLE
#                 self._log_location("An annotation - divTag=%s" % divTag)
                soup.div.insert(dtc, divTag)
#                 self._log_location("Full soup after adding annotation - soup=%s" % soup)
                dtc += 1
                if i < len(self.annotations) - 1 and \
                    plugin_prefs.get('appearance_hr_checkbox', False):
                    soup.div.insert(dtc, BeautifulSoup(plugin_prefs.get('HORIZONTAL_RULE', '<hr width="80%" />')))
                    dtc += 1

        else:
            soup = BeautifulSoup(ANNOTATIONS_HEADER)
        return unicode(soup)


def merge_annotations(parent, cid, old_soup, new_soup):
    '''
    old_soup, new_soup: BeautifulSoup()
    Need to strip <hr>, re-sort based on location, build new merged_soup
    with optional interleaved <hr> elements.
    '''
    TRANSIENT_DB = 'transient'
    debug_print("merge_annotations - cid=", cid)
    debug_print("merge_annotations - old_soup=", old_soup)
    debug_print("merge_annotations - new_soup=", new_soup)

    # Fetch preferred merge index technique
    merge_index = getattr(parent.reader_app_class, 'MERGE_INDEX', 'hash')

    if merge_index == 'hash':
        # Get the hashes of any existing annotations
        oiuas = old_soup.findAll('div', 'annotation')
        old_hashes = set([ua['hash'] for ua in oiuas])
        debug_print("old hashes=", old_hashes)

        # Extract old user_annotations
        ouas = old_soup.find('div', 'user_annotations')
        if ouas:
            debug_print("Getting old annotations - count=", len(ouas))
            debug_print("Getting old annotations - old_soup=", old_soup)
            debug_print("Getting old annotations - ouas=", ouas)
            ouas.extract()
            debug_print("Getting old annotations - ouas after extract=", ouas)
            debug_print("Getting old annotations - old_soup after extract=", old_soup)

            # Capture existing annotations
            annotation_list = parent.opts.db.capture_content(ouas, cid, TRANSIENT_DB)

            # Regurgitate old_soup with current CSS
            regurgitated_soup = BeautifulSoup(parent.opts.db.rerender_to_html_from_list(annotation_list))
            debug_print("Getting old annotations - regurgitated_soup=", regurgitated_soup)
        else:
            regurgitated_soup = BeautifulSoup()

        # Find new annotations
        uas = new_soup.findAll('div', 'annotation')
        new_hashes = set([ua['hash'] for ua in uas])
        debug_print("new_hashes=", sorted(new_hashes))
        debug_print("old hashes=", sorted(old_hashes))
        debug_print("new_hashes.difference(old_hashes)=", new_hashes.difference(old_hashes))

        updates = list(new_hashes.difference(old_hashes))
        debug_print("differences between old and new hashs - updates=", updates)
        if ouas is not None:
            if len(updates):
                debug_print("have updates and ouas")
                # Append new to regurgitated
                dtc = len(regurgitated_soup.div)
                debug_print("length regurgitated_soup - dtc=", dtc)
                for new_annotation_id in updates:
                    debug_print("extending regurgitated_soup - new_annotation_id=", new_annotation_id)
                    new_annotation = new_soup.find('div', {'hash': new_annotation_id})
                    regurgitated_soup.div.insert(dtc, new_annotation)
                    dtc += 1
            merged_soup = unicode(sort_merged_annotations(regurgitated_soup))
        else:
            debug_print("have updates and ouas")
            if not regurgitated_soup == BeautifulSoup():
                debug_print("adding old_soup and new_soup")
                debug_print("unicode(regurgitated_soup)=", unicode(regurgitated_soup))
                debug_print("unicode(new_soup)=", unicode(new_soup))
                merged_soup = unicode(regurgitated_soup) + unicode(new_soup)
            else:
                debug_print("just new_soup")
                merged_soup = unicode(new_soup)
        debug_print("merged_soup=", merged_soup)
        return merged_soup

    elif merge_index == 'timestamp':
        timestamps = {}
        # Get the timestamps and hashes of the stored annotations
        suas = old_soup.findAll('div', 'annotation')
        for sua in suas:
            try:
                timestamp = sua.find('td', 'timestamp')['uts']
                timestamps[timestamp] = {'stored_hash': sua['hash']}
            except:
                continue

        # Rerender stored annotations
        ouas = old_soup.find('div', 'user_annotations')
        if ouas:
            ouas.extract()

            # Capture existing annotations
            annotation_list = parent.opts.db.capture_content(ouas, cid, TRANSIENT_DB)

            # Regurgitate old_soup with current CSS
            regurgitated_soup = BeautifulSoup(parent.opts.db.rerender_to_html_from_list(annotation_list))

        # Add device annotation timestamps and hashes
        duas = new_soup.findAll('div', 'annotation')
        for dua in duas:
            try:
                timestamp = dua.find('td', 'timestamp')['uts']
                if timestamp in timestamps:
                    timestamps[timestamp]['device_hash'] = dua['hash']
                else:
                    timestamps[timestamp] = {'device_hash': dua['hash']}
            except:
                print("ERROR: malformed timestamp in device annotation")
                print(dua.prettify())

        merged_soup = BeautifulSoup(ANNOTATIONS_HEADER)

        for ts in sorted(timestamps):
            if 'stored_hash' in timestamps[ts] and not 'device_hash' in timestamps[ts]:
                # Stored only - add from regurgitated_soup
                annotation = regurgitated_soup.find('div', {'hash': timestamps[ts]['stored_hash']})

            elif not 'stored_hash' in timestamps[ts] and 'device_hash' in timestamps[ts]:
                # Device only - add from new_soup
                annotation = new_soup.find('div', {'hash': timestamps[ts]['device_hash']})

            elif timestamps[ts]['stored_hash'] == timestamps[ts]['device_hash']:
                # Stored matches device - add from regurgitated_soup, as user may have modified
                annotation = regurgitated_soup.find('div', {'hash': timestamps[ts]['stored_hash']})

            elif timestamps[ts]['stored_hash'] != timestamps[ts]['device_hash']:
                # Device has been updated since initial capture - add from new_soup
                annotation = new_soup.find('div', {'hash': timestamps[ts]['device_hash']})

            else:
                continue

            merged_soup.div.append(annotation)

        return unicode(sort_merged_annotations(merged_soup))


def merge_annotations_with_comments(parent, cid, comments_soup, new_soup):
    '''
    comments_soup: comments potentially with user_annotations
    '''

    # Prepare a new COMMENTS_DIVIDER
    comments_divider = '<div class="comments_divider"><p style="text-align:center;margin:1em 0 1em 0">{0}</p></div>'.format(
        plugin_prefs.get('COMMENTS_DIVIDER', '&middot;  &middot;  &bull;  &middot;  &#x2726;  &middot;  &bull;  &middot; &middot;'))

    # Remove the old comments_divider
    cds = comments_soup.find('div', 'comments_divider')
    if cds:
        cds.extract()

    # Existing annotations?
    uas = comments_soup.find('div', 'user_annotations')
    if uas:
        # Save the existing annotations to old_soup
        old_soup = BeautifulSoup(unicode(uas))

        # Remove any hrs from old_soup
        hrs = old_soup.findAll('hr')
        if hrs:
            for hr in hrs:
                hr.extract()

        # Remove the existing annotations from comments_soup
        uas.extract()

        # Merge old_soup with new_soup
        merged_soup = unicode(comments_soup) + \
                      unicode(comments_divider) + \
                      unicode(merge_annotations(parent, cid, old_soup, new_soup))
    else:
        # No existing, just merge comments_soup with already sorted new_soup
        merged_soup = unicode(comments_soup) + \
                      unicode(comments_divider) + \
                      unicode(new_soup)

    return merged_soup


def sort_merged_annotations(merged_soup):
    '''
    Input: a combined group of user annotations
    Output: sorted by location
    '''
    include_hr = plugin_prefs.get('appearance_hr_checkbox', False)
    locations = merged_soup.findAll(location_sort=True)
    locs = [loc['location_sort'] for loc in locations]
    locs.sort()

    sorted_soup = BeautifulSoup(ANNOTATIONS_HEADER)
    dtc = 0
    for i, loc in enumerate(locs):
        next_div = merged_soup.find(attrs={'location_sort': loc})
        sorted_soup.div.insert(dtc, next_div)
        dtc += 1
        if include_hr and i < len(locs) - 1:
            sorted_soup.div.insert(dtc, BeautifulSoup(plugin_prefs.get('HORIZONTAL_RULE', '<hr width="80%" />')))
            dtc += 1

    return sorted_soup
