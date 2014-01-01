#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import hashlib, re

from datetime import datetime
from xml.sax.saxutils import escape

from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag
from calibre_plugins.annotations.common_utils import Logger
from calibre_plugins.annotations.config import plugin_prefs

COLOR_MAP = {
                  'Blue': {'bg': '#b1ccf3', 'fg': 'black'},
               'Default': {'bg': 'transparent', 'fg': 'black'},
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


class Annotations(Annotation, Logger):
    '''
    A collection of Annotation objects
    annotations: [{title:, path:, timestamp:, genre:, highlightcolor:, text:} ...]
    Inherits Annotation solely to share style characteristics for agroups
    '''
    @dynamic_property
    def annotations(self):
        def fget(self):
            return self.__annotations
        return property(fget=fget)

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

        if self.annotations:
            soup = BeautifulSoup(ANNOTATIONS_HEADER)
            dtc = 0

            # Add the annotations
            for i, agroup in enumerate(sorted(self.annotations, key=self._annotation_sorter)):
                location = agroup.location
                if location is None:
                    location = ''

                friendly_timestamp = self._timestamp_to_datestr(agroup.timestamp)

                text = ''
                if agroup.text:
                    for agt in agroup.text:
                        text += '<p class="highlight" style="{0}">{1}</p>'.format(text_style, agt)

                note = ''
                if agroup.note:
                    for agn in agroup.note:
                        note += '<p class="note" style="{0}">{1}</p>'.format(note_style, agn)

                try:
                    dt_bgcolor = COLOR_MAP[agroup.highlightcolor]['bg']
                    dt_fgcolor = COLOR_MAP[agroup.highlightcolor]['fg']
                except:
                    if agroup.highlightcolor is None:
                        msg = "No highlight color specified, using Default"
                    else:
                        msg = "Unknown color '%s' specified" % agroup.highlightcolor
                    self._log_location(msg)
                    dt_bgcolor = COLOR_MAP['Default']['bg']
                    dt_fgcolor = COLOR_MAP['Default']['fg']

                if agroup.hash is not None:
                    # Use existing hash when re-rendering
                    hash = agroup.hash
                else:
                    m = hashlib.md5()
                    m.update(text)
                    m.update(note)
                    hash = m.hexdigest()

                divTag = Tag(BeautifulSoup(), 'div')
                content_args = {
                            'color': agroup.highlightcolor,
                            'friendly_timestamp': friendly_timestamp,
                            'location': location,
                            'note': note,
                            'text': text,
                            'ts_style': datetime_style.format(dt_bgcolor, dt_fgcolor),
                            'unix_timestamp': agroup.timestamp,
                            }
                divTag.insert(0, comments_body.format(**content_args))
                divTag['class'] = "annotation"
                divTag['genre'] = ''
                if agroup.genre:
                    divTag['genre'] = escape(agroup.genre)
                divTag['hash'] = hash
                divTag['location_sort'] = agroup.location_sort
                divTag['reader'] = agroup.reader_app
                divTag['style'] = ANNOTATION_DIV_STYLE
                soup.div.insert(dtc, divTag)
                dtc += 1
                if i < len(self.annotations) - 1 and \
                    plugin_prefs.get('appearance_hr_checkbox', False):
                    soup.div.insert(dtc, plugin_prefs.get('HORIZONTAL_RULE', '<hr width="80%" />'))
                    dtc += 1

        else:
            soup = BeautifulSoup(ANNOTATIONS_HEADER)
        return unicode(soup.renderContents())


def merge_annotations(parent, cid, old_soup, new_soup):
    '''
    old_soup, new_soup: BeautifulSoup()
    Need to strip <hr>, re-sort based on location, build new merged_soup
    with optional interleaved <hr> elements.
    '''
    TRANSIENT_DB = 'transient'

    # Fetch preferred merge index technique
    merge_index = getattr(parent.reader_app_class, 'MERGE_INDEX', 'hash')

    if merge_index == 'hash':
        # Get the hashes of any existing annotations
        oiuas = old_soup.findAll('div', 'annotation')
        old_hashes = set([ua['hash'] for ua in oiuas])

        # Extract old user_annotations
        ouas = old_soup.find('div', 'user_annotations')
        if ouas:
            ouas.extract()

            # Capture existing annotations
            parent.opts.db.capture_content(ouas, cid, TRANSIENT_DB)

            # Regurgitate old_soup with current CSS
            regurgitated_soup = BeautifulSoup(parent.opts.db.rerender_to_html(TRANSIENT_DB, cid))

        # Find new annotations
        uas = new_soup.findAll('div', 'annotation')
        new_hashes = set([ua['hash'] for ua in uas])

        updates = list(new_hashes.difference(old_hashes))
        if len(updates) and ouas is not None:
            # Append new to regurgitated
            dtc = len(regurgitated_soup.div)
            for new_annotation_id in updates:
                new_annotation = new_soup.find('div', {'hash': new_annotation_id})
                regurgitated_soup.div.insert(dtc, new_annotation)
                dtc += 1
            if old_soup:
                merged_soup = unicode(old_soup) + unicode(sort_merged_annotations(regurgitated_soup))
            else:
                merged_soup = unicode(sort_merged_annotations(regurgitated_soup))
        else:
            if old_soup:
                merged_soup = unicode(old_soup) + unicode(new_soup)
            else:
                merged_soup = unicode(new_soup)
        return merged_soup

    elif merge_index == 'timestamp':
        timestamps = {}
        # Get the timestamps and hashes of the stored annotations
        suas = old_soup.findAll('div', 'annotation')
        for sua in suas:
            #print("sua: %s" % sua.prettify())
            timestamp = sua.find('td', 'timestamp')['uts']
            timestamps[timestamp] = {'stored_hash': sua['hash']}

        # Rerender stored annotations
        ouas = old_soup.find('div', 'user_annotations')
        if ouas:
            ouas.extract()

            # Capture existing annotations
            parent.opts.db.capture_content(ouas, cid, TRANSIENT_DB)

            # Regurgitate old_soup with current CSS
            regurgitated_soup = BeautifulSoup(parent.opts.db.rerender_to_html(TRANSIENT_DB, cid))

        # Add device annotation timestamps and hashes
        duas = new_soup.findAll('div', 'annotation')
        for dua in duas:
            timestamp = dua.find('td', 'timestamp')['uts']
            if timestamp in timestamps:
                timestamps[timestamp]['device_hash'] = dua['hash']
            else:
                timestamps[timestamp] = {'device_hash': dua['hash']}

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
            sorted_soup.div.insert(dtc, plugin_prefs.get('HORIZONTAL_RULE', '<hr width="80%" />'))
            dtc += 1

    return sorted_soup
