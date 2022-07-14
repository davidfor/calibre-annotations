<!--This document is formatted in GitHub flavored markdown, tweaked for Github's
    presentation of the repo's README.md file. Documentation for GFM is at
    https://help.github.com/articles/github-flavored-markdown
    A semi-useful site for previewing GFM is available at
    http://tmpvar.com/markdown.html
-->
## Support

Support for this plugin is in the [MobileRead  Forums](https://www.mobileread.com/forums/index.php). There is a thread dedicated to the plugin, https://www.mobileread.com/forums/showthread.php?t=241206. Please post any problems and requests there.



## Developer notes

### Table of Contents
1. [OVERVIEW](#1-overview)
2. [DEVELOPING SUPPORT FOR A NEW DEVICE OR READER APP](#2-developing-support-for-a-new-device-or-reader-app)
3. [ADDING A NEW DEVICE OR READER APP TO THE RELEASED PLUGIN](#3-adding-a-new-device-or-reader-app-to-the-released-plugin)
4. [MODIFYING AN EXISTING DEVICE OR READER APP](#4-modifying-an-existing-device-or-reader-app)
5. [DEVELOPER MODE](#5-developer-mode)
6. [PROGRAM FLOW](#6-program-flow)

---

#### [1. OVERVIEW](#table-of-contents)
The Annotations plugin is designed for extensibility. Classes supporting reader apps and devices are contained in individual files loaded at runtime.

The plugin architecture provides two methods of adding annotations to calibre:

- _Fetching_ annotations from a connected USB device.
- _Importing_ annotations from an app which exports annotations, typically by email or through iTunes.

The file [<samp>reader\_app\_support.py</samp>](reader_app_support.py) contains classes which your code subclasses:

- A USB reader device (Kindle, SONY, etc) subclasses <samp>USBReader()</samp>.
- An iOS reader application (iBooks, Marvin, Kindle for iOS) subclasses <samp>iOSReaderApp()</samp>.
- A reader application which exports annotations (Bluefire Reader, GoodReader) subclasses <samp>ExportingReader()</samp>.

Note that some reader apps may support both methods of annotations (e.g., Marvin). Apps supporting both methods may be declared as subclasses of <samp>USBReader</samp> or <samp>iOSReaderApp</samp>.

Within your class, two class variables declare which methods are supported:

- <samp>SUPPORTS\_EXPORTING</samp>: This class declares a method, <samp>parse\_exported_highlights()</samp>, which parses text or files supplied by the user.

- <samp>SUPPORTS\_FETCHING</samp>: This class declares two methods, <samp>get\_installed\_books()</samp> and <samp>get\_active\_annotations()</samp>, which probe the connected device for the information.

Your class may declare both variables to be true if the reader is capable of both fetching and exporting.

---

#### [2. DEVELOPING SUPPORT FOR A NEW DEVICE OR READER APP](#table-of-contents)
- Save a copy of the appropriate sample class included in the plugin, [<samp>SampleExportingApp.py</samp>](readers/SampleExportingApp.py) or [<samp>SampleFetchingClass.py</samp>](readers/SampleFetchingClass.py) to your machine. Rename the copy appropriately, e.g. <samp>MyAnnotationsClass.py</samp>.
- After installing the Annotations plugin to your installation of calibre, go to the calibre configuration directory. From within calibre, you can open this directory from  _Preferences|Advanced|Miscellaneous|Open calibre configuration directory_.
- Exit calibre.
- Within the calibre configuration directory, open <samp>plugins/annotations.json</samp>.
- Locate the property `additional_readers`.
- Change `path/to/your/reader_class.py` to point to the copy of the sample class you created on your machine.
- Save <samp>annotations.json</samp>.

Your class will be dynamically imported when calibre launches.

Run calibre in debug mode to see diagnostic messages.

 `calibre-debug -g`

If your code cannot be imported, calibre will exit, with the problem reported to the console. When your class loads successfully, you see its name listed during calibre initialization.

To begin developing your code, locate <samp>SUPPORTS\_EXPORTING</samp> or <samp>SUPPORTS\_FETCHING</samp> in your class. Change the applicable variables to <samp>True</samp>. Your class will now be enabled.

After editing your class, save the changes and restart calibre.

Refer to [<samp>readers/Marvin.py</samp>](readers/Marvin.py) or [<samp>readers/GoodReader.py</samp>](readers/GoodReader.py) for functional working code.

---

#### [3. ADDING A NEW DEVICE OR READER APP TO THE RELEASED PLUGIN](#table-of-contents)
After developing and debugging a new reader app class, generate a pull request and I will review it for inclusion with the plugin.

---

#### [4. MODIFYING AN EXISTING DEVICE OR READER APP](#table-of-contents)
To make modifications to an existing reader app class:

- Exit calibre.
- Copy the reader app class source file from the <samp>readers/</samp> folder to your desktop.
- Within the calibre configuration directory, open <samp>plugins/annotations.json</samp>.
- Locate the property `additional_readers`.
- Change `path/to/your/reader_class.py` to point to your local copy.

When the plugin loads, it will now use the reader app class definition in your local copy
instead of the built-in copy. After developing and testing your modifications, generate a pull request and I will review it for inclusion with the plugin.

---

#### [5. DEVELOPER MODE](#table-of-contents)
Within <samp>annotations.json</samp> is an entry `developer_mode`. Setting this variable to `true` enables an additional menu item in the plugin dropdown menu, _Remove all annotations_. This command can be useful while developing your class.

---

#### [6. PROGRAM FLOW](#table-of-contents)
[<samp>action.py</samp>](action.py) contains the <samp>InterfaceAction</samp> subclass implementation.

<samp>action:genesis()</samp> is called when calibre launches. <samp>genesis()</samp> sets up logging, creates an opts object which is used to access global properties throughout the plugin, instantiates the annotatations sqlite database, initializes the <samp>.json</samp> prefs file, loads any external reader classes specified in the prefs file, then inflates the help file.

<samp>InterfaceAction</samp> overrides:

- <samp>initialization\_complete()</samp> listens for <samp>device\_changed</samp> signals at <samp>action:\_on\_device\_connection\_changed()</samp>, so that we are notified when a device recognized by calibre is connected.
- <samp>library\_changed()</samp> is called whenever the user changes libraries.
- <samp>shutting\_down()</samp> is called when calibre is about to exit, giving the plugin a chance to unmount the iDevice and save the log.
- <samp>accept\_enter\_event()</samp>, <samp>accept\_drag\_move\_event()</samp> and <samp>drop\_event()</samp> support drag & drop methods.

After <samp>genesis()</samp> executes, the plugin is ready to respond to user input. There are three user-initiated paths to importing annotations:

- User drags a <samp>.MRV</samp>, <samp>.MRVI</samp> or <samp>.TXT</samp> file to the plugin icon. If the dropped file has the proper mime content, <samp>drop\_event()</samp> fires <samp>do\_drop\_event()</samp>, which passes the dropped file to each of the installed reader classes until it is successfully parsed, or informs the user that no installed class could parse the file.

- User invokes the dropdown menu item _Fetch annotations from \[connected device\]_ (when a supported device is connected).

- User invokes the dropdown menu item _Import annotations from \[reader class\]_.

There are two approaches to processing annotations, _Fetching_ and _Importing_:

- _Fetching_ means probing a connected device to discover annotation content, usually stored in one or more sqlite databases, or some proprietary format.
- _Importing_ means parsing a file containing a proprietary annotations description.

Fetching and importing both result in storing the annotations to <samp>annotations.db</samp>, a sqlite database created and managed by the plugin.

- Fetching classes instantiate <samp>AnnotatedBooksDialog()</samp> from <samp>action:fetch\_device\_annotations()</samp>.

- Importing classes instantiate <samp>AnnotatedBooksDialog()</samp> from <samp>action:present\_annotated\_books()</samp>.

Each reader class stores annotations to <samp>annotations.db</samp> using a standardized schema. After the annotations are processed, the user is shown a summary by instantiating <samp>annotated\_books:AnnotatedBooksDialog()</samp>. This class displays all available annotations, color-coded by metadata quality. The user can preview individual book's annotations, and enable or disable individual books for importation.

<samp>annotated\_books:fetch\_selected\_annotations()</samp> builds a list of selected books.

Once the user approves the import list, <samp>action:process\_selected\_books()</samp> automatically adds annotations from the selected books to the associated library book if the metadata matches completely. For incomplete matches, a confirmation dialog is shown with the plugin's best guess for the receiving book in the library.

#### Additional plugin functionality

_Find annotations_ (dropdown menu): <samp>find\_annotations:FindAnnotationsDialog()</samp>

_Modify appearance_ (configuration dialog): <samp>appearance:AnnotationsAppearance()</samp>

---
Last update June 10, 2013 7:56:25 AM MDT
