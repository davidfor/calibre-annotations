# -*- coding: utf-8 -*-
assert '…' == '\xe2\x80\xa6', "file encoding error"

# Copyright 2013 Axel Walthelm
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

# If you update/fix this file for other formats found in any Kindle MyClippings.txt
# please keep the module interface unchanged as is and publish your improvements.
# Consider to update the unit tests at the end of this file; check all tests run OK.

import re
import datetime

# override this function if you need different error logging
global log
def log(level, message):
    assert level.upper() in ('INFO', 'WARNING', 'ERROR')
    print "%s: %s" % (level, message)

# all strings are utf-8 encoded
class MyClippingsAnnotation:
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
        # language of annotion; None if language detection failed
        self.language = None
        # type of annotion; one of ['highlight', 'note', 'bookmark']
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
        self.text = None
    def __repr__(self):
        show = ('ordernr', 'title', 'author', 'kind', 'time', 'begin', 'end', 'page', 'text')
        return "MyClippingsAnnotation(%s)" % ', '.join(['%s=%r' % (name, vars(self)[name]) for name in show])

# Kindle uses a limited set of phrases, which we can use to detect language, annotation type, etc.;
# add more start phrases when they are reported
_LANG_AND_KIND_DETECT_BY_START_WORDS = {
    "Your Highlight": ('en', 'highlight'),
    "Your Note":      ('en', 'note'),
    "Your Bookmark":  ('en', 'bookmark'),
    "Highlight": ('en', 'highlight'),
    "Note":      ('en', 'note'),
    "Bookmark":  ('en', 'bookmark'),
    "Ihre Markierung": ('de', 'highlight'),
    "Ihre Notiz":      ('de', 'note'),
    "Ihr Lesezeichen": ('de', 'bookmark'),
    "Mi subrayado": ('es', 'highlight'),
    "Mi nota":      ('es', 'note'),
    "Mi marcador":  ('es', 'bookmark'),
    "Votre surlignement": ('fr', 'highlight'),
    "Votre note":         ('fr', 'note'),
    "Votre signet":       ('fr', 'bookmark'),
    "La mia evidenziazione": ('it', 'highlight'),
    "Le mie note":           ('it', 'note'),
    "Il mio segnalibro":     ('it', 'bookmark'),
    "ハイライト":  ('jp', 'highlight'),
    "メモ":      ('jp', 'note'),
    "ブックマーク": ('jp', 'bookmark'),
    "Seu destaque": ('pt', 'highlight'),
    "Sua nota":     ('pt', 'note'),
    "Seu marcador": ('pt', 'bookmark'),
    "我的标注": ('ch', 'highlight'),
    "我的笔记": ('ch', 'note'),
    "我的书签": ('ch', 'bookmark'),
    }
_MAX_NR_OF_START_WORDS = 3
    
_LOCATION_REGEX = {
    'en': (r"\sLocation\s*%s",
           r"\sLoc\.\s*%s",),
    'de': (r"\sPosition\s*%s",),
    'es': (r"\sPosición\s*%s",),
    'fr': (r"\sEmplacement\s*%s",),
    'it': (r"\sPosizione\s*%s",),
    'jp': (r"\s位置No.\s*%s",),
    'pt': (r"\sPosição\s*%s",),
    'ch': (r"\s位置\s*%s",),
}

_PAGE_REGEX = {
    'en': (r"\sPage\s*%s",),
    'de': (r"\sSeite\s*%s",),
    'es': (r"\spágina\s*%s",),
    'fr': (r"\spage\s*%s",),
    'it': (r"\spagina\s*%s",),
    'jp': (r"\sジ\s*%s",),
    'pt': (r"\spágina\s*%s",),
    'ch': (r"\s第\s*%s\s*页",),
}

_MONTH_NAMES = {
    'en': {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
           'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12},
    'de': {'Januar': 1, 'Jänner': 1, 'Februar': 2, 'März': 3, 'April': 4, 'Mai': 5, 'Juni': 6,
           'Juli': 7, 'August': 8, 'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12},
    'es': {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
           'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12},
    'fr': {'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
           'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12},
    'it': {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
           'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12},
    'pt': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6,
           'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12},
}

_MONTH_NAMES_SHORT = {
    'en': {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
           'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12},
    'de': {'Jan': 1, 'Jän': 1, 'Feb': 2, 'Mrz': 3, 'Mär': 3, 'Apr': 4, 'Mai': 5, 'Jun': 6,
           'Jul': 7, 'Aug': 8, 'Sep': 9, 'Okt': 10, 'Nov': 11, 'Dez': 12},
    'es': {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
           'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12},
    'fr': {'janv.': 1, 'févr.': 2, 'mars': 3, 'avr.': 4, 'mai': 5, 'juin': 6,
           'juil.': 7, 'août': 8, 'sept.': 9, 'oct.': 10, 'nov.': 11, 'déc.': 12},
    'it': {'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
           'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12},
    'pt': {'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
           'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12},
}

def _detectLanguageAndType(status):
    words = status.split(None, _MAX_NR_OF_START_WORDS)
    for nrWords in xrange(0, _MAX_NR_OF_START_WORDS):
        key = ' '.join(words[:nrWords+1])
        if _LANG_AND_KIND_DETECT_BY_START_WORDS.has_key(key):
            return _LANG_AND_KIND_DETECT_BY_START_WORDS[key]
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
    
def _getDateTime(status, language):
    year = month = day = hour = minute = second = micro = 0
    
    # time is handled relatively consistent among all used languages
    date_time_re = r'([0-2]?[0-9]):([0-5][0-9])(?::([0-5][0-9])(?:\.([0-9]+))?)?\s*([AP]\.?M)?\s*(?:[A-Z]{3}?([+-][0-2]?[0-9](?::[0-5][0-9])?))?'
    match = re.search(date_time_re, status, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if match.lastindex >= 3 and match.group(3):
            second = int(match.group(3))
            if match.lastindex >= 4 and match.group(4):
                micro = int( 1000000.0*float("0."+match.group(4)) )
        if match.lastindex >= 5 and match.group(5) and match.group(5).upper().replace('.', '') == 'PM' and hour < 12:
            hour += 12
        # time zone information is quite unusual in Kindle annotations; we better ignore it even if there is some
        status = re.sub(date_time_re, ' ', status)
        
    if language in ('jp', 'ch'):
        # japanese and chinese formats simply use numbers with following day/month/year character
        match = re.search(r'([0-9]+)\s?日', status)
        if match:
            day = int( match.group(1) )
        match = re.search(r'([0-9]+)\s?月', status)
        if match:
            month = int( match.group(1) )
        match = re.search(r'([0-9]+)\s?年', status)
        if match:
            year = int( match.group(1) )
    else:
        # for european languages Kindle uses named month
        # (so we don't have to guess if 5 4 is 5.April of 4.May)
        # and two numbers, one for the day and one for the year.
        # If one number is larger than 31, it is the year.
        # Otherwise the last number is the year (and 2000 should be added).
        words = re.split(r"[,;]?\s", status)
        for word in words:
            if _MONTH_NAMES[language].has_key(word):
                month = _MONTH_NAMES[language][word]
                break
        if not month:
            for word in words:
                if _MONTH_NAMES_SHORT[language].has_key(word):
                    month = _MONTH_NAMES_SHORT[language][word]
                    break
        if month:
            # now there should be only two numbers left
            numbers = re.findall(r"[0-9]+", status)
            if len(numbers) == 2:
                numbers = [int(n) for n in numbers]
                if min(numbers) <= 31:
                    if numbers[0] > 31:
                        day = numbers[1]
                        year = numbers[0]
                    else:
                        day = numbers[0]
                        year = numbers[1]
                    if year < 100:
                        year += 2000 # Kindle was first released 2007

    if day and month and year:
        return datetime.datetime(year, month, day, hour, minute, second, micro)
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

# read "My Clippings.txt" and extract all annotations
def FromFileName(myClippingsFilePath):
    try:
        with file( myClippingsFilePath, 'rb' ) as f: # file is UTF-8 => read binary!
            return FromUtf8String( f.read() )
    except Exception as e:
        log('ERROR', "Error trying to read clippings file: %s" % (str(e),))
        return []

def FromUtf8String(myClippingsTxt):
    # remove BOM(s) a.k.a. zero width space
    myClippingsTxt = myClippingsTxt.replace('\xef\xbb\xbf', '')
    # normalize newlines
    myClippingsTxt = myClippingsTxt.replace('\r\n', '\n').replace('\r', '\n')
    if myClippingsTxt.strip() == '':
        return
    if myClippingsTxt[-1] != '\n':
        myClippingsTxt += '\n'

    # split into records;
    # note that record separator may also be part of regular note or highlight text,
    # so whenever a record seriously fails to parse, we append it to the text of the previous record
    records = re.split(r"^==========\n", myClippingsTxt, flags=re.MULTILINE)
    if records[-1].strip() == '':
        records.pop()
    else:
        log('ERROR', "invalid end of clippings file")

    annos = []
    for record in records:
        # check basic record format:
        # first line is not empty
        # second line starts with "- " and contains "|"
        # third line is empty
        match = re.match(r"\s*(\S[^\n]*)\n-\s+([^\n|]+\|[^\n]+)\n\s*\n(.*)\n$", record, re.DOTALL)
        if not match:
            if not annos:
                log('ERROR', "invalid start of clippings file")
            else:
                log('INFO', "joining record '%s'" % record)
                # join invalid record back to text of previous record
                annos[-1].text = ''.join((annos[-1].text, "\n==========", record))
            continue
        anno = MyClippingsAnnotation()
        anno.ordernr = len(annos)
        anno.bookline, anno.statusline, anno.text = match.groups()
        
        # evaluate book line
        anno.title, anno.author = _getTitleAndAuthor(anno.bookline.strip())

        # status line ends with a date part after the last |
        split_idx = anno.statusline.rindex('|') # we already checked that | does exist
        anno.language, anno.kind = _detectLanguageAndType(anno.statusline[:split_idx])
        if not anno.kind:
            log('ERROR', "could not detect type of record '%s'" % anno.statusline)
            continue
        anno.begin, anno.end, anno.page = _getLocation(anno.statusline[:split_idx], anno.language)
        anno.time = _getDateTime(anno.statusline[split_idx+1:], anno.language)
        
        annos.append(anno)

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
r"""Kindle-Benutzerhandbuch (German Edition) (Amazon)
- Your Highlight Location 449-449 | Added on Thursday, 25 April 13 23:45:11

auszublenden. Seite aktualisieren:
==========
Willkommen Axel  
- Your Note Location 20 | Added on Thursday, April 25, 2013 11:57:54 PM

en us
why did some books disappear after switching to en us?
==========
Kindle-Benutzerhandbuch (German Edition) (Amazon)
- Your Bookmark Location 447 | Added on Thursday, 25 April 13 23:45:00


==========
The Valley of the Moon (Jack London)
- Note Loc. 6260  | Added on Sunday, February 06, 2011, 10:03 AM

song
==========
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
