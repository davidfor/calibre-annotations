# -*- coding: utf-8 -*-
assert '…' == '\xe2\x80\xa6', "file encoding error"

# Copyright 2018-2019, David Forrester <davidfor@internode.on.net>'
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.


import re
import datetime

# override this function if you need different error logging
global log
def log(level, message):
    assert level.upper() in ('INFO', 'WARNING', 'ERROR')
    print "%s: %s" % (level, message)

# all strings are utf-8 encoded
class NotesAnnotation:
    def __init__(self):
        # consecutive number
        self.ordernr = None
        # original human-readable book description line
        self.bookline = None
        # book title
        self.title = None
        # book author(s); may be None
        self.author = None
        # original human-readable location and date/time line
        self.statusline = None
        # language of annotation; None if language detection failed
        self.language = None
        # type of annotation; one of ['highlight', 'note', 'bookmark']
        self.kind = None
        # parsed creation time as a python datetime.datetime object; may be None
        self.time = None
        # start location as index into rawml divided by 150; may be None
        self.begin = None
        # end location as index into rawml divided by 150; may be None
        self.end = None
        # page number; may be None
        self.page = None
        # text of annotation; may contain newlines in case of multiline notes
        self.note_text = None
        # highlighted text; may contain newlines in case of multiline notes
        self.highlight_text = None
    def __repr__(self):
        show = ('ordernr', 'title', 'author', 'kind', 'time', 'begin', 'end', 'page', 'note_text', 'highlight_text')
        return "NotesAnnotation:\n%s" % '\n'.join(['%s=%r' % (name, vars(self)[name]) for name in show])

# Sample 

# Tolino uses a limited set of phrases, which we can use to detect language, annotation type, etc.;
# add more start phrases when they are reported
_LANG_AND_KIND_DETECT_BY_START_WORDS = {
    "Highlight on": ('en', 'highlight'),
    "Note on":      ('en', 'note'),
    "Bookmark on":  ('en', 'bookmark'),
    "Markierung auf": ('de', 'highlight'),
    "Notiz auf":      ('de', 'note'),
    "Ihr Lesezeichen": ('de', 'bookmark'),
    "Selección en la":  ('es', 'highlight'),
    "Marcadores en la": ('es', 'note'),
    "Mi marcador":      ('es', 'bookmark'),
    "Surlignement en": ('fr', 'highlight'),
    "Note en":         ('fr', 'note'),
    "Signet en":       ('fr', 'bookmark'),
    "Evidenziazione a": ('it', 'highlight'),
    "Nota a":           ('it', 'note'),
    "Segnalibro a":     ('it', 'bookmark'),
    "Markering op":     ('nl', 'highlight'),
    "Notitie op":       ('nl', 'note'),
    "Bladwijzer op":    ('nl', 'bookmark'),
    }
_MAX_NR_OF_START_WORDS = 3
    
_LOCATION_REGEX = {
    'en': (r"\spage\s*%s:",),
    'de': (r"\sPosition\s*%s",
           r"\sPos\.\s*%s"),
    'es': (r"\sPosición\s*%s"),
    'fr': (r"\sEmplacement\s*%s",),
    'it': (r"\sPosizione\s*%s"),
    'nl': (r"\spagina\s*%s",),
}

_PAGE_REGEX = {
    'en': (r"\spage\s*%s",),
    'de': (r"\sSeite\s*%s",),
    'es': (r"\spágina\s*%s",),
    'fr': (r"\spage\s*%s",),
    'it': (r"\spagina\s*%s",),
    'nl': (r"\spagina\s*%s",),
}

_ADDED_REGEX = {
    'en': (r"\sAdded on\s*%s",),
    'de': (r"\sHinzugefügt am\s*%s",),
    'es': (r"\sAgregado el\s*%s",),
    'fr': (r"\sAjouté le\s*%s",),
    'it': (r"\sAggiunto il\s*%s",),
    'nl': (r"\sToegevoegd op\s*%s",),
}

_DATE_FORMAT = {
    'en': ('%m/%d/%Y | %H:%M'),
    'de': ('%d.%m.%Y | %H:%M'),
    'es': ('%d.%m.%Y | %H:%M'),
    'fr': ('%d.%m.%Y | %H:%M'),
    'it': ('%d.%m.%Y | %H:%M'),
    'nl': ('%d/%m/%Y | %H:%M'),
}


def _detectLanguageAndType(status):
    for kind_key in _LANG_AND_KIND_DETECT_BY_START_WORDS.keys():
        if status.startswith(kind_key):
            return _LANG_AND_KIND_DETECT_BY_START_WORDS[kind_key]
    return (None, None)
    
def _getLocation(status, language):
    begin = end = page = None
    for regex in _LOCATION_REGEX[language]:
        regex = regex % r"([0-9][0-9,.-]*[0-9]|[0-9])"
        matches = re.findall(regex, status)
        if matches and len(matches) == 1:
            location = re.sub(r"[,.]", "", matches[0])
            if "-" in location:
                begin, end = re.match(r"([0-9]+)-([0-9]+)", location).groups()
                end = begin[:-len(end)] + end # e.g. Location 1024-25 => end=1025
            else:
                begin = end = location
            begin = int(begin)
            end = int(end)
            status = re.sub(regex, " ", status)
            break
    for regex in _PAGE_REGEX[language]:
        regex = regex % r"([0-9][0-9,.]*[0-9]|[0-9])"
        matches = re.findall(regex, status)
        if matches and len(matches) == 1:
            page = int( re.sub(r"[,.]", "", matches[0]) )
            status = re.sub(regex, " ", status)
            break
    # if only one number is missing and there is only one number left in status line, use it
    if not begin and page or begin and not page:
        numbers = re.findall(r"[0-9]+", status)
        if len(numbers) == 1:
            if not begin:
                begin = end = int(numbers[0])
            else:
                page = int(numbers[0])
    return begin, end, page
    
def _getDateTime(timestamp_str, language):
    import time

    log('DEBUG', "date format: %s" % (_DATE_FORMAT[language],))
    try:
        return time.strptime(timestamp_str, _DATE_FORMAT[language])
    except Exception as e:
        log('ERROR', "Error converting timestamp: %s" % (str(e),))
    return None

def _getTitleAndAuthor(line):
    # author is in parenthesis.
    # ambiguity: some books may have no author but a subtitle in parenthesis.
    # strategy: consider last block in parenthesis to be the author,
    # but if everything is in parentheses, line is the title;
    # if line does not end with closing parenthesis, line is the title;
    # also: take care of cases where authors contains perentheses (e.g. (Editor))
    title = author = None
    if line.endswith(')'):
        i = line.rindex('(')
        while i >= 0 and line[i:].count('(') != line[i:].count(')'):
            i = line.rindex('(', 0, i-1) if i > 0 else -1
        if i > 0:
            title = line[0:i].strip()
            author = line[i+1:-1].strip()
    if title is None:
        title = line
    return title, author

# read "notes.txt" and extract all annotations
def FromFileName(notesFilePath):
    log('INFO', "FromFileName: notesFilePath='%s'" % (notesFilePath,))
    try:
        with file( notesFilePath, 'rb' ) as f: # file is UTF-8 => read binary!
            return FromUtf8String( f.read() )
    except Exception as e:
        log('ERROR', "Error trying to read notes file: %s" % (str(e),))
        return []

def FromUtf8String(notesTxt):
    log('INFO', "FromUtf8String: len(notesTxt)=%d" % (len(notesTxt),))
    # Replace non-breaking space with normal space
    notesTxt = notesTxt.replace('\xc2\xa0', ' ')
    # normalize newlines
    notesTxt = notesTxt.replace('\r\n', '\n').replace('\r', '\n')
    if notesTxt.strip() == '':
        return
    if notesTxt[-1] != '\n':
        notesTxt += '\n'

    # split into records;
    # note that record separator may also be part of regular note or highlight text,
    # so whenever a record seriously fails to parse, we append it to the text of the previous record
    records = re.split(r"^-----------------------------------\n", notesTxt, flags=re.MULTILINE)
    if records[-1].strip() == '':
        records.pop()
    else:
        log('ERROR', "invalid end of notes file")

    annos = []
    for record in records:
        try:
            record = record.strip()
            log('DEBUG', "notes file entry: ---%s---" % (record,))
            # check basic record format:
            #    First line ends with "(author)"
            #    Second line is type of note, page number and either the note or selected text.
            #    The selected text may go over multiple lines
            #    Last line is when the note was created.
    #         match = re.match(r"\s*(\S[^\n]*)\n-\s+([^\n|]+\|[^\n]+)\n\s*\n(.*)\n$", record, re.DOTALL)
            match = re.match(r"\s*(.*\(.*\))\n(.*?)\s([\d-]+):\s*(.*)\n([^\n]+)$", record, re.DOTALL | re.UNICODE)
            if not match:
                # The author might be missing, so try without that.
                match = re.match(r"\s*(.*?)\n(.*?)\s([\d-]+):\s*(.*)\n([^\n]+)$", record, re.DOTALL | re.UNICODE)
            if not match: 
                if not annos:
                    log('ERROR', "invalid start of notes file")
                else:
                    log('INFO', "joining record '%s'" % record)
                    # join invalid record back to text of previous record
                    annos[-1].note_text = ''.join((annos[-1].text, "\n==========", record))
                continue
            try: # Make sure the debug messages don't cause a problem
                log('DEBUG', "match: ---%s---" % (match,))
                log('DEBUG', "match.groups(): ---%s---" % (match.groups(),))
            except Exception as e:
                log('ERROR', "Problem printing details of match. Skipping annotation. Exception=%s" % e)
                continue

            anno = NotesAnnotation()
            anno.ordernr = len(annos)
            anno.bookline, annotation_type, anno.page_str, anno.text, anno.statusline = match.groups()
            log('DEBUG', "anno.bookline: ---%s---" % (anno.bookline,))
            log('DEBUG', "annotation_type: ---%s---" % (annotation_type,))
            log('DEBUG', "anno.page_str: ---%s---" % (anno.page_str,))
            log('DEBUG', "anno.text: ---%s---" % (anno.text,))
            log('DEBUG', "anno.statusline: ---%s---" % (anno.statusline,))

            # evaluate book line
            anno.title, anno.author = _getTitleAndAuthor(anno.bookline.strip())
            log('DEBUG', "anno.author: ---%s---" % (anno.author,))
            log('DEBUG', "anno.title: ---%s---" % (anno.title,))
    
            # status line ends with a the date and time separated by a | or an emdash.
            statusline_match = re.match(r"^(.+)\s+(\S+)\s+\S\s+(\S+)$", anno.statusline)#, re.DOTALL | re.UNICODE)
            statusline_match = re.match(r"^(.+?)\s+([\d\/\.]+).+?([\d\:]+)$", anno.statusline)#, re.DOTALL | re.UNICODE)
            if not statusline_match:
                log('ERROR', "Status line didn't pass regex: '%s'" % (anno.statusline,))
                add_text = None
                date_str = time_str = ''
            else:
                add_text, date_str, time_str = statusline_match.groups()
            log('DEBUG', "add_text: ---%s---" % (add_text,))
            log('DEBUG', "date_str: ---%s---" % (date_str,))
            log('DEBUG', "time_str: ---%s---" % (time_str,))
            anno.language, anno.kind = _detectLanguageAndType(annotation_type)
            log('DEBUG', "anno.language: '%s'" % (anno.language,))
            log('DEBUG', "anno.kind: '%s'" % (anno.kind,))
            if not anno.kind:
                log('ERROR', "could not detect type of record '%s'" % anno.statusline)
                continue
            if not (anno.kind == 'bookmark'):
                text_match = re.match(r'^(.*?)\"(.*)\"', anno.text, re.DOTALL | re.UNICODE)
                try:
                    anno.note_text, anno.highlight_text = text_match.groups()
                except:
                    log('ERROR', 'Highlight or note but the text did not parse')

            try:
                anno.page = int(anno.page_str)
            except:
                log('ERROR', "Page number isn't an integer. Probably a range. anno.page_str: ---%s---" % (anno.page_str,))
                try:
                    anno.page = int(anno.page_str.split('-')[0])
                except:
                    log('ERROR', "Page number not parsed properly. Don't set.")
            log('DEBUG', "anno.page: '%s'" % (anno.page,))
            anno.begin = anno.end = None # The location isn't in the file.
            anno.time = _getDateTime(date_str +' | ' + time_str, anno.language)
            log('DEBUG', "anno.time: %s" % (anno.time,))

            log('DEBUG', "found annotation: %s" % (anno,))
            annos.append(anno)
        except Exception as e:
            log('ERROR', "Error trying to read notes file: %s" % (str(e),))
            import traceback
            traceback.print_exc()
            raise
            

    return annos

###################################################################################################
# tests and test helpers
###################################################################################################
if __debug__ and __name__ == '__main__':
    
    def _PrintMonthAndWeekDayNamesDict():
        # we must not use setlocale in product code, because it is not thread safe;
        # to make matters with setlocale worse, names differ between OS;
        # but we can use locale to compile a list of month names in test code;
        # to check for grammatical variations of the month name we generate
        # it for all days in a leap year.
        # However this still does not cover chinese and japanese (even when not using chinese calender)
        print "Getting names for months from locale"
        import locale
        #monthNames[(language, {name: number})
        names = {}
        # Windows locale names for languages
        localeNameTuples = [
                ('en', "english", "english-uk", "english-us", "australian", "canadian", "english-nz"),
                ('de', "german", "german-austrian", "german-swiss"),
                ('es', "spanish", "spanish-mexican", "spanish-modern"),
                ('fr', "french", "french-belgian", "french-canadian", "french-swiss"),
                ('it', "italian", "italian-swiss"),
                ('pt', "portuguese", "portuguese-brazilian"),
                #('ch', "chinese", "chinese-simplified", "chinese-traditional"),
                #('jp', "japanese")
                ]
        for localeNames in localeNameTuples:
            language = localeNames[0]
            names[language] = ({}, {}, {}, {}) # month long/short, week day long/short
            for localeName in localeNames[1:]:
                locale.setlocale(locale.LC_TIME, localeName)
                for month in xrange(1,12+1):
                    days = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                    for day in xrange(1,days[month-1]+1):
                        date = datetime.date(2012,month,day)
                        for idx, timeFormat in enumerate(["%B", "%b", "%A", "%a"]):
                            try:
                                name = date.strftime(timeFormat)
                                dic = names[language][idx]
                                if dic.has_key(name):
                                    if dic[name] is not None and dic[name] != month:
                                        dic[name] = None # ambiguous; not really a month or day name
                                else:
                                    dic[name] = month
                            except:
                                print "No name for", language, month, day, timeFormat
                                raise

        for longNames in (True, False):
            print "_MONTH_NAMES = {" if longNames else "_MONTH_NAMES_SHORT = {"
            for langs in localeNameTuples:
                lang = langs[0]
                if not names.has_key(lang):
                    continue
                line = "    '%s': {" % lang
                for value, key in sorted([(v,k) for k,v in names[lang][0 if longNames else 1].items()]):
                    if value > 6 and not '\n' in line:
                        line = re.sub(r"\s*$", "\n"+" "*11, line)
                    line += "'%s': %s, " % (key, value)
                print re.sub(r",\s*$", "},", line)
            print "}"

        locale.setlocale(locale.LC_TIME, 'C')
        print "END"
        
    def _testParse(clipText, expectedResult):
        def pformatAnno(anno):
            return (
             "ordernr = %r\n" % anno.ordernr +
             "language = %r\n" % anno.language +
             "kind = %r\n" % anno.kind +
             "title = %r\n" % anno.title +
             "author = %r\n" % anno.author +
             "begin = %r\n" % anno.begin +
             "end = %r\n" % anno.end +
             "page = %r\n" % anno.page +
             "time = %r\n" % anno.time +
             "text = %r\n" % anno.text)
        def pformatAnnos(annos):
            return '----------\n'.join([pformatAnno(a) for a in (annos if annos else [])])
            
        result = pformatAnnos( FromUtf8String(clipText) )
        if not expectedResult or expectedResult.strip() != result.strip():
            print "######################################"
            print "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
            print clipText
            print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
            print "######################################"
            print result
            print "######################################"
            if expectedResult and expectedResult.strip():
                import difflib
                from pprint import pprint
                pprint(list(difflib.Differ().compare(expectedResult.splitlines(1), result.splitlines(1))))
            assert False, "expectedResult differs"

    def _runTests():
        print "Test"
        
        # empty
        _testParse(
r"""""",
r"""
""")

        # basic English
        _testParse(
r"""User manual tolino eReader 11.0 (Rakuten Kobo Inc.)
Bookmark on page 3: "are a customer of two or more tolino booksellers, you can also display all your purchased eBooks together.

  Access your books any time—with your eReader, smartphone or PC
tolino offers multiple ways"
Added on 12/15/2017 | 21:31

-----------------------------------

My notes
Bookmark on page 1: "User manual tolino eReader 11.0 (Rakuten Kobo Inc.)
Bookmark on page 3: "are a customer of two or more tolino booksellers, you can also display all your purchased eBooks together.

  Access your books"
Added on 12/15/2017 | 21:48

-----------------------------------
""",
r"""
ordernr = 0
language = 'en'
kind = 'highlight'
title = 'Kindle-Benutzerhandbuch (German Edition)'
author = 'Amazon'
begin = 449
end = 449
page = None
time = datetime.datetime(2013, 4, 25, 23, 45, 11)
text = 'auszublenden. Seite aktualisieren:'
----------
ordernr = 1
language = 'en'
kind = 'note'
title = 'Willkommen Axel'
author = None
begin = 20
end = 20
page = None
time = datetime.datetime(2013, 4, 25, 23, 57, 54)
text = 'en us\nwhy did some books disappear after switching to en us?'
----------
ordernr = 2
language = 'en'
kind = 'bookmark'
title = 'Kindle-Benutzerhandbuch (German Edition)'
author = 'Amazon'
begin = 447
end = 447
page = None
time = datetime.datetime(2013, 4, 25, 23, 45)
text = ''
----------
ordernr = 3
language = 'en'
kind = 'note'
title = 'The Valley of the Moon'
author = 'Jack London'
begin = 6260
end = 6260
page = None
time = datetime.datetime(2011, 2, 6, 10, 3)
text = 'song'
""")

        # basic German
        _testParse(
r"""Mein Clipboard  
- Ihre Markierung Position 14-14 | Hinzugefügt am Freitag, 26. April 2013 um 00:49:32 Uhr

00:43:51
==========
The Café (Hans Glück)
- Ihr Lesezeichen auf Seite 222 | Position 3393 | Hinzugefügt am Montag, 17. Juni 2013 um 22:32:42 Uhr


==========
Kindle-Benutzerhandbuch (German Edition) (Amazon)
- Ihre Notiz Position 9 | Hinzugefügt am Donnerstag, 25. April 2013 um 23:40:04 Uhr

Notiz Zeile 1
Zeile 2
==========
""",
r"""
ordernr = 0
language = 'de'
kind = 'highlight'
title = 'Mein Clipboard'
author = None
begin = 14
end = 14
page = None
time = datetime.datetime(2013, 4, 26, 0, 49, 32)
text = '00:43:51'
----------
ordernr = 1
language = 'de'
kind = 'bookmark'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3393
end = 3393
page = 222
time = datetime.datetime(2013, 6, 17, 22, 32, 42)
text = ''
----------
ordernr = 2
language = 'de'
kind = 'note'
title = 'Kindle-Benutzerhandbuch (German Edition)'
author = 'Amazon'
begin = 9
end = 9
page = None
time = datetime.datetime(2013, 4, 25, 23, 40, 4)
text = 'Notiz Zeile 1\nZeile 2'
""")

        # basic Spanish
        _testParse(
r"""Willkommen Axel  
- Mi nota Posición 6 | Añadido el viernes 26 de abril de 2013, 0:04:34

note
==========
The Café (Hans Glück)
- Mi nota en la página 222 | Posición 3394 | Añadido el lunes 17 de junio de 2013, 20:13:12

es
==========
The Café (Hans Glück)
- Mi marcador en la página 222 | Posición 3393 | Añadido el lunes 17 de junio de 2013, 20:13:27


==========
""",
r"""
ordernr = 0
language = 'es'
kind = 'note'
title = 'Willkommen Axel'
author = None
begin = 6
end = 6
page = None
time = datetime.datetime(2013, 4, 26, 0, 4, 34)
text = 'note'
----------
ordernr = 1
language = 'es'
kind = 'note'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3394
end = 3394
page = 222
time = datetime.datetime(2013, 6, 17, 20, 13, 12)
text = 'es'
----------
ordernr = 2
language = 'es'
kind = 'bookmark'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3393
end = 3393
page = 222
time = datetime.datetime(2013, 6, 17, 20, 13, 27)
text = ''
""")

        # basic French
        _testParse(
r"""Willkommen Axel  
- Votre surlignement Emplacement 12-12 | Ajouté le vendredi 26 avril 2013 à 00:18:27

Lesen beginnen.
==========
Le Café (J. Garçon)
- Votre note sur la page 222 | Emplacement 3394 | Ajouté le lundi 17 juin 2013 à 20:19:15

fr note
==========
The Café (Hans Glück & J. Garçon)
- Votre signet sur la page 222 | Emplacement 3393 | Ajouté le lundi 17 juin 2013 à 20:19:40


==========""",
r"""
ordernr = 0
language = 'fr'
kind = 'highlight'
title = 'Willkommen Axel'
author = None
begin = 12
end = 12
page = None
time = datetime.datetime(2013, 4, 26, 0, 18, 27)
text = 'Lesen beginnen.'
----------
ordernr = 1
language = 'fr'
kind = 'note'
title = 'Le Caf\xc3\xa9'
author = 'J. Garc\xcc\xa7on'
begin = 3394
end = 3394
page = 222
time = datetime.datetime(2013, 6, 17, 20, 19, 15)
text = 'fr note'
----------
ordernr = 2
language = 'fr'
kind = 'bookmark'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck & J. Garc\xcc\xa7on'
begin = 3393
end = 3393
page = 222
time = datetime.datetime(2013, 6, 17, 20, 19, 40)
text = ''
""")

        # basic Italian
        _testParse(
r"""Willkommen Axel  
- La mia evidenziazione Posizione 22-22 | Aggiunto il venerdì 6 aprile 12, 00:25:08

Wir freuen uns
==========
The Café (Hans Glück)
- Le mie note a pagina 222 | Posizione 3395 | Aggiunto il lunedì 17 giugno 13, 20:23:44

it
==========
The Café (Hans Glück)
- Il mio segnalibro a pagina 222 | Posizione 3393 | Aggiunto il lunedì 17 giugno 13, 20:23:54


==========""",
r"""
ordernr = 0
language = 'it'
kind = 'highlight'
title = 'Willkommen Axel'
author = None
begin = 22
end = 22
page = None
time = datetime.datetime(2012, 4, 6, 0, 25, 8)
text = 'Wir freuen uns'
----------
ordernr = 1
language = 'it'
kind = 'note'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3395
end = 3395
page = 222
time = datetime.datetime(2013, 6, 17, 20, 23, 44)
text = 'it'
----------
ordernr = 2
language = 'it'
kind = 'bookmark'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3393
end = 3393
page = 222
time = datetime.datetime(2013, 6, 17, 20, 23, 54)
text = ''
""")

        # basic Japanese
        _testParse(
r"""The Café (Hans Glück)
- ハイライト ページ222 | 位置No. 3396-3396 | 追加日： 2013年6月17日 (月曜日) 20:31:09

CHAPTER
==========
マイクリッピング  
- メモ 位置No. 3 | 追加日： 2013年4月26日 (金曜日) 0:33:16

Japanese
==========
マイクリッピング  
- ブックマーク 位置No. 1 | 追加日： 2013年4月26日 (金曜日) 0:33:28


==========
""",
r"""
ordernr = 0
language = 'jp'
kind = 'highlight'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3396
end = 3396
page = 222
time = datetime.datetime(2013, 6, 17, 20, 31, 9)
text = 'CHAPTER'
----------
ordernr = 1
language = 'jp'
kind = 'note'
title = '\xe3\x83\x9e\xe3\x82\xa4\xe3\x82\xaf\xe3\x83\xaa\xe3\x83\x83\xe3\x83\x94\xe3\x83\xb3\xe3\x82\xb0'
author = None
begin = 3
end = 3
page = None
time = datetime.datetime(2013, 4, 26, 0, 33, 16)
text = 'Japanese'
----------
ordernr = 2
language = 'jp'
kind = 'bookmark'
title = '\xe3\x83\x9e\xe3\x82\xa4\xe3\x82\xaf\xe3\x83\xaa\xe3\x83\x83\xe3\x83\x94\xe3\x83\xb3\xe3\x82\xb0'
author = None
begin = 1
end = 1
page = None
time = datetime.datetime(2013, 4, 26, 0, 33, 28)
text = ''
""")

        # basic Brazilian
        _testParse(
r"""The Café (Hans Glück)
- Seu destaque na página 222 | Posição 3396-3396 | Adicionado na data segunda-feira, 17 de junho de 2013, 20:39:30

CHAPTER
==========
Meus recortes  
- Sua nota Posição 7 | Adicionado na data sexta-feira, 26 de abril de 2013, 00:38:04

po br note
==========
The Café (Hans Glück)
- Seu marcador de página na página 222 | Posição 3393 | Adicionado na data segunda-feira, 17 de junho de 2013, 20:40:09


==========
""",
r"""
ordernr = 0
language = 'pt'
kind = 'highlight'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3396
end = 3396
page = 222
time = datetime.datetime(2013, 6, 17, 20, 39, 30)
text = 'CHAPTER'
----------
ordernr = 1
language = 'pt'
kind = 'note'
title = 'Meus recortes'
author = None
begin = 7
end = 7
page = None
time = datetime.datetime(2013, 4, 26, 0, 38, 4)
text = 'po br note'
----------
ordernr = 2
language = 'pt'
kind = 'bookmark'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3393
end = 3393
page = 222
time = datetime.datetime(2013, 6, 17, 20, 40, 9)
text = ''
""")

        # basic Chinese
        _testParse(
r"""The Café (Hans Glück)
- 我的标注 第222页 | 位置3397-3397 | 已添加至 2013年6月17日 星期一 22:27:30

CHAPTER
==========
The Café (Hans Glück)
- 我的笔记 第222页 | 位置3397 | 已添加至 2013年6月17日 星期一 22:27:51

ch
==========
我的剪贴  
- 我的书签 位置8 | 已添加至 2013年4月26日 星期五 0:44:37


==========""",
r"""
ordernr = 0
language = 'ch'
kind = 'highlight'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3397
end = 3397
page = 222
time = datetime.datetime(2013, 6, 17, 22, 27, 30)
text = 'CHAPTER'
----------
ordernr = 1
language = 'ch'
kind = 'note'
title = 'The Caf\xc3\xa9'
author = 'Hans Gl\xc3\xbcck'
begin = 3397
end = 3397
page = 222
time = datetime.datetime(2013, 6, 17, 22, 27, 51)
text = 'ch'
----------
ordernr = 2
language = 'ch'
kind = 'bookmark'
title = '\xe6\x88\x91\xe7\x9a\x84\xe5\x89\xaa\xe8\xb4\xb4'
author = None
begin = 8
end = 8
page = None
time = datetime.datetime(2013, 4, 26, 0, 44, 37)
text = ''
""")

        # exotic English
        _testParse(
r"""EGC Spanish to English Dictionary V0.1 (Dave Slusher)
- Bookmark on Page 415 | Loc. 6353  | Added on Saturday, April 30, 2011, 08:37 AM


==========
Life Every Day Jul-Aug 2012 (Jeff Lucas)
- Highlight Loc. 143-46  | Added on Friday, 6 July 12 07:37:42 GMT+01:00

Without wanting to resort to slogans and clichés
==========
L'Echappee belle  (Anna Gavalda) 
- Bookmark Page 87  | Added on Wednesday, October 20, 2010, 09:24 PM


==========
""",
r"""
ordernr = 0
language = 'en'
kind = 'bookmark'
title = 'EGC Spanish to English Dictionary V0.1'
author = 'Dave Slusher'
begin = 6353
end = 6353
page = 415
time = datetime.datetime(2011, 4, 30, 8, 37)
text = ''
----------
ordernr = 1
language = 'en'
kind = 'highlight'
title = 'Life Every Day Jul-Aug 2012'
author = 'Jeff Lucas'
begin = 143
end = 146
page = None
time = datetime.datetime(2012, 7, 6, 7, 37, 42)
text = 'Without wanting to resort to slogans and clich\xc3\xa9s'
----------
ordernr = 2
language = 'en'
kind = 'bookmark'
title = "L'Echappee belle"
author = 'Anna Gavalda'
begin = None
end = None
page = 87
time = datetime.datetime(2010, 10, 20, 21, 24)
text = ''
""")

        # exotic/synthetic cases, German
        _testParse(
r"""Kindle-Benutzerhandbuch (German Edition) (Amazon)
- Ihre Markierung Position 5-6 | Hinzugefügt am Donnerstag, 25. April 2013 um 23:38:23.1 Uhr

Aktionen am Bildschirm Statusanzeigen
==========
Kindle-Benutzerhandbuch (German Edition) (Amazon (Editors))
- Ihre Notiz Position 9 | Hinzugefügt am Donnerstag, 25. April 2013 um 23:40:04 Uhr

Notiz Zeile 1
Zeile 2
==========
==========

==========
==========
(Kindle-Benutzerhandbuch (German Edition) (Amazon))
- Ihre Markierung Position 9-9 | Hinzugefügt am Donnerstag, 25. April 2013 um 23:40:04 Uhr

Inhalte Kapitel 2
==========
""",
r"""
ordernr = 0
language = 'de'
kind = 'highlight'
title = 'Kindle-Benutzerhandbuch (German Edition)'
author = 'Amazon'
begin = 5
end = 6
page = None
time = datetime.datetime(2013, 4, 25, 23, 38, 23, 100000)
text = 'Aktionen am Bildschirm Statusanzeigen'
----------
ordernr = 1
language = 'de'
kind = 'note'
title = 'Kindle-Benutzerhandbuch (German Edition)'
author = 'Amazon (Editors)'
begin = 9
end = 9
page = None
time = datetime.datetime(2013, 4, 25, 23, 40, 4)
text = 'Notiz Zeile 1\nZeile 2\n==========\n==========\n\n=========='
----------
ordernr = 2
language = 'de'
kind = 'highlight'
title = '(Kindle-Benutzerhandbuch (German Edition) (Amazon))'
author = None
begin = 9
end = 9
page = None
time = datetime.datetime(2013, 4, 25, 23, 40, 4)
text = 'Inhalte Kapitel 2'
""")

        print "OK"

if __debug__ and __name__ == '__main__':
    #_PrintMonthAndWeekDayNamesDict()
    def testLog(level, message):
        if level.upper() != 'INFO':
            print "%s: %s" % (level, message)
        assert level.lower().upper() != 'ERROR', message
    log = testLog
    _runTests()

