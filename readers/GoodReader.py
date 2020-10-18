#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import re, time

from calibre.gui2.dialogs.message_box import MessageBox
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct, Struct)
from calibre_plugins.annotations.reader_app_support import ExportingReader


class GoodReaderApp(ExportingReader):
    """
    GoodReader implementation
    """

    # Reader-specific characteristics
    app_name = 'GoodReader'
    import_fingerprint = False
    import_dialog_title = "Import {0} annotations".format(app_name)
    if True:
        import_help_text = ('''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <title>Exporting from GoodReader</title>
            <style type="text/css">
                body {
                font-family:Tahoma, Geneva, sans-serif;
                font-size:medium;
                }
                div.steps_with_header h3 {
                    margin:0;
                }
                div.steps_with_header ol, ul {
                    margin-top:0;
                }
                div.steps_with_header_indent p {
                    margin:0 0 0 1em;
                }
                div.steps_with_header_indent ol, ul {
                    margin-left:1em;
                    margin-top:0;
                }
                h2, h3 {
                    font-family:Tahoma, Geneva, sans-serif;
                    text-align: left;
                    font-weight: normal;
                }
            </style>
            </head>
            <body>
                <h3>Exporting annotations from GoodReader</h3>
                <div class="steps_with_header_indent">
                  <p><i>From within an open book:</i></p>
                  <ol>
                    <li>Tap the center of the screen so that the overlay controls are shown</li>
                    <li>Tap <b>Share</b> (arrow icon at bottom right)</li>
                    <li>Tap <b>E-Mail Summary</b>, then email the annotations file to yourself</li>
                  </ol>
                </div>
                <hr width="80%" />
                <h3>Importing GoodReader annotations to calibre</h3>
                <div class="steps_with_header_indent">
                  <p><i>After receiving the emailed annotations summary on your computer:</i></p>
                  <ol>
                    <li>Copy the contents of the annotations summary email</li>
                    <li>Paste the annotations to the <b>Import GoodReader annotations</b> window</li>
                    <li>Click <b>Import</b></li>
                  </ol>
                </div>
            </body>
            </html>''')

    initial_dialog_text = ''
    SUPPORTS_EXPORTING = True

    MONTHS = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    ANNOTATION_TYPES = ['Highlight', 'Note', 'Underline', 'Squiggly underline', 'Strikeout']
    SKIP_TYPES = ['Caret', 'Line', 'Arrow', 'Rectangle', 'Oval', 'Drawing']

    def parse_exported_highlights(self, raw, log_failure=True):
        """
        Extract highlights from pasted Annotation summary email
        Return True if no problems
        Return False if error
        """
        # Create the annotations, books table as needed
        self.annotations_db = "%s_imported_annotations" % self.app_name_
        self.create_annotations_table(self.annotations_db)
        self.books_db = "%s_imported_books" % self.app_name_
        self.create_books_table(self.books_db)

        self.annotated_book_list = []
        self.selected_books = None

        # Generate the book metadata from the selected book
        row = self.opts.gui.library_view.currentIndex()
        book_id = self.opts.gui.library_view.model().id(row)
        db = self.opts.gui.current_db
        mi = db.get_metadata(book_id, index_is_id=True)

        # Grab the title from the front of raw
        try:
            title = re.match(r'(?m)File: (?P<title>.*)$', raw).group('title')

            # Populate a BookStruct
            book_mi = BookStruct()
            book_mi.active = True
            book_mi.author = 'Unknown'
            book_mi.book_id = mi.id
            book_mi.title = title
            book_mi.uuid = None
            book_mi.last_update = time.mktime(time.localtime())
            book_mi.reader_app = self.app_name
            book_mi.cid = mi.id

            gr_annotations = raw.split('\n')
            num_lines = len(gr_annotations)
            highlights = {}

            # Find the first annotation
            i = 0
            line = gr_annotations[i]
            while not line.startswith('--- Page'):
                i += 1
                line = gr_annotations[i]

            while i < num_lines and not line.startswith('(report generated by GoodReader)'):
                # Extract the page number
                page_num = re.search('--- (Page \w+) ---', line)
                if page_num:
                    page_num = page_num.group(1)

                    # Extract the highlight
                    i += 1
                    line = gr_annotations[i]

                    prefix = None
                    while True:
                        prefix = re.search('^(?P<ann_type>{0})'.format('|'.join(self.ANNOTATION_TYPES + self.SKIP_TYPES)), line)
                        if prefix and prefix.group('ann_type') in self.SKIP_TYPES:
                            i += 1
                            line = gr_annotations[i]
                            while not re.search('^(?P<ann_type>{0})'.format('|'.join(self.ANNOTATION_TYPES)), line):
                                i += 1
                                line = gr_annotations[i]
                            continue
                        elif prefix:
                            break
                        else:
                            i += 1
                            line = gr_annotations[i]

                    annotation = self._extract_highlight(line, prefix.group('ann_type'))
                    annotation.page_num = page_num

                    # Get the annotation(s)
                    i += 1
                    line = gr_annotations[i]
                    ann = ''
                    while i < num_lines \
                        and not line.startswith('--- Page') \
                        and not line.startswith('(report generated by GoodReader)'):

                        if line:
                            prefix = re.search('^(?P<ann_type>{0})'.format('|'.join(self.ANNOTATION_TYPES + self.SKIP_TYPES)), line)
                            if prefix and prefix.group('ann_type') in self.SKIP_TYPES:
                                # Continue until next ann_type
                                i += 1
                                line = gr_annotations[i]
                                while not re.search('^(?P<ann_type>{0})'.format('|'.join(self.ANNOTATION_TYPES)), line):
                                    i += 1
                                    if i == num_lines:
                                        break
                                    line = gr_annotations[i]
                                continue
                            elif prefix:
                                # Additional highlight on the same page
                                # write current annotation, start new annotation
                                self._store_annotation(highlights, annotation)
                                annotation = self._extract_highlight(line, prefix.group('ann_type'))
                                annotation.page_num = page_num
                                annotation.ann_type = prefix.group('ann_type')
                                ann = ''
                                i += 1
                                line = gr_annotations[i]
                                continue

                            if not ann:
                                ann = line
                            else:
                                ann += '\n' + line
                        i += 1
                        line = gr_annotations[i]
                        annotation.ann = ann

                    # Back up so that the next line is '--- Page' or '(report generated'
                    i -= 1
                    self._store_annotation(highlights, annotation)

                i += 1
                if i == num_lines:
                    break
                line = gr_annotations[i]
        except:
            if log_failure:
                self._log(" unable to parse GoodReader Annotation summary")
                self._log("{:~^80}".format(" Imported Annotation summary "))
                self._log(raw)
                self._log("{:~^80}".format(" end imported Annotations summary "))
                import traceback
                traceback.print_exc()
                msg = ('Unable to parse Annotation summary from %s. ' % self.app_name +
                    'Paste entire contents of emailed summary.')
                MessageBox(MessageBox.WARNING,
                    'Error importing annotations',
                    msg,
                    show_copy_button=False,
                    parent=self.opts.gui).exec_()
                self._log_location("WARNING: %s" % msg)
            return False

        # Finalize book_mi
        book_mi.annotations = len(highlights)
        # Add book to books_db
        self.add_to_books_db(self.books_db, book_mi)
        self.annotated_book_list.append(book_mi)

        sorted_keys = sorted(list(highlights.keys()))
        for dt in sorted_keys:
            highlight_text = None
            if 'text' in highlights[dt]:
                highlight_text = highlights[dt]['text']
            note_text = None
            if 'note' in highlights[dt]:
                note_text = highlights[dt]['note']

            # Populate an AnnotationStruct
            a_mi = AnnotationStruct()
            a_mi.annotation_id = dt
            a_mi.book_id = book_mi['book_id']
            a_mi.highlight_color = highlights[dt]['color']
            a_mi.highlight_text = highlight_text
            a_mi.location = highlights[dt]['page']
            a_mi.last_modification = dt
            a_mi.note_text = note_text

            # Location sort
            page_literal = re.match(r'^Page (?P<page>[0-9ivx]+).*$', a_mi.location).group('page')
            if re.match('[IXVL]', page_literal.upper()):
                whole = 0
                decimal = self._roman_to_int(page_literal)
            else:
                whole = int(page_literal)
                decimal = 0
            a_mi.location_sort = "%05d.%05d" % (whole, decimal)

            # Add annotation
            self.add_to_annotations_db(self.annotations_db, a_mi)
            self.update_book_last_annotation(self.books_db, dt, book_mi['book_id'])

        # Update the timestamp
        self.update_timestamp(self.annotations_db)
        self.update_timestamp(self.books_db)
        self.commit()

        return True

    # Helpers
    def _extract_highlight(self, line, ann_type):
        # This search spec is tuned to a line like this:
        # Highlight (yellow), Jan 25, 2013, 5:17 AM:
        search_spec = ('%s \((?P<color>.+?)\), ' % ann_type +
                       '(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ' +
                       '(?P<day>\d+), (?P<year>\d{4}), ' +
                       '(?P<hour>\d{1,2}):(?P<minutes>\d{2}) ' +
                       '(?P<am_pm>AM|PM).*')

        ts = re.search(search_spec, line)
        if ts:
            annotation = Struct()
            annotation.ann_type = ann_type
            annotation.color = ts.group('color').title()
            annotation.year = int(ts.group('year'))
            annotation.month = self.MONTHS.index(ts.group('month'))
            annotation.day = int(ts.group('day'))
            annotation.hour = int(ts.group('hour'))
            if ts.group('am_pm') == 'PM':
                annotation.hour += 12
            annotation.minutes = int(ts.group('minutes'))
            timestamp = time.mktime((annotation.year, annotation.month, annotation.day, annotation.hour, annotation.minutes, 0, 0, 0, -1))
            annotation.ts_index = str(timestamp)
            return annotation
        else:
            self._log("could not parse line:\n%s" % line)
            return Struct()

    def _roman_to_int(self, input):
        '''
        '''
        input = input.upper()
        nums = ['M', 'D', 'C', 'L', 'X', 'V', 'I']
        ints = [1000, 500, 100, 50,  10,  5,   1]
        places = []
        for c in input:
            if not c in nums:
                raise ValueError("input is not a valid roman numeral: %s" % input)
        for i in range(len(input)):
            c = input[i]
            value = ints[nums.index(c)]
            # If the next place holds a larger number, this value is negative.
            try:
                nextvalue = ints[nums.index(input[i + 1])]
                if nextvalue > value:
                    value *= -1
            except IndexError:
                # there is no next place.
                pass
            places.append(value)
        sum = 0
        for n in places:
            sum += n
        return sum

    def _store_annotation(self, highlights, annotation):
        this_annotation = {
                           'page': annotation.page_num,
                           'ann_type': annotation.ann_type,
                           'color': annotation.color
                           }

        if annotation.ann_type in ['Note']:
            this_annotation['note'] = annotation.ann
            this_annotation['text'] = None
        else:
            this_annotation['text'] = annotation.ann
            this_annotation['note'] = None

        # Add the annotation(s) to indexed_annotations
        if annotation.ts_index in highlights:
            d = annotation.ts_index
            seconds = 0
            while d in highlights:
                seconds += 1
                d = time.mktime((annotation.year, annotation.month, annotation.day,
                                 annotation.hour, annotation.minutes, seconds,
                                 0, 0, -1))
            this_annotation['timestamp'] = d
            annotation.ts_index = d
        else:
            d = time.mktime((annotation.year, annotation.month, annotation.day,
                             annotation.hour, annotation.minutes, 1,
                             0, 0, -1))
            this_annotation['timestamp'] = d
        highlights[annotation.ts_index] = this_annotation
