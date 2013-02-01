#TODO: probably best to always include the symbol in the url & match the
#      fetched data keying by symbol rather than hoping the fetched
#      string has the correct newlines to match the selected symbols

#TODO: a cancel button for some requests that take a long time

#TODO: split out url/yahoo specific stuff into separate module

import sys
import collections
import urllib2
import string

from PyQt4 import QtCore
from PyQt4 import QtGui

FLAGS = collections.OrderedDict( \
            [ ("a",  "Ask"),
              ("a2", "Average Daily Volume"),
              ("a5", "Ask Size"),
              ("b",  "Bid"),
              ("b2", "Ask (Real-time)"),
              ("b3", "Bid (Real-time)"),
              ("b4", "Book Value"),
              ("b6", "Bid Size"),
              ("c",  "Change & Percent Change"),
              ("c1", "Change"),
              ("c3", "Commission"),
              ("c6", "Change (Real-time)"),
              ("c8", "After Hours Change (Real-time)"),
              ("d",  "Dividend/Share"),
              ("d1", "Last Trade Date"),
              ("d2", "Trade Date"),
              ("e",  "Earnings/Share"),
              ("e1", "Error Indication (returned for symbol changed / invalid)"),
              ("e7", "EPS Estimate Current Year"),
              ("e8", "EPS Estimate Next Year"),
              ("e9", "EPS Estimate Next Quarter"),
              ("f6", "Float Shares"),
              ("g",  "Day's Low"),
              ("h",  "Day's High"),
              ("j",  "52-week Low"),
              ("k",  "52-week High"),
              ("g1", "Holdings Gain Percent"),
              ("g3", "Annualized Gain"),
              ("g4", "Holdings Gain"),
              ("g5", "Holdings Gain Percent (Real-time)"),
              ("g6", "Holdings Gain (Real-time)"),
              ("i",  "More Info"),
              ("i5", "Order Book (Real-time)"),
              ("j1", "Market Capitalization"),
              ("j3", "Market Cap (Real-time)"),
              ("j4", "EBITDA"),
              ("j5", "Change From 52-week Low"),
              ("j6", "Percent Change From 52-week Low"),
              ("k1", "Last Trade (Real-time) With Time"),
              ("k2", "Change Percent (Real-time)"),
              ("k3", "Last Trade Size"),
              ("k4", "Change From 52-week High"),
              ("k5", "Percebt Change From 52-week High"),
              ("l",  "Last Trade (With Time)"),
              ("l1", "Last Trade (Price Only)"),
              ("l2", "High Limit"),
              ("l3", "Low Limit"),
              ("m",  "Day's Range"),
              ("m2", "Day's Range (Real-time)"),
              ("m3", "50-day Moving Average"),
              ("m4", "200-day Moving Average"),
              ("m5", "Change From 200-day Moving Average"),
              ("m6", "Percent Change From 200-day Moving Average"),
              ("m7", "Change From 50-day Moving Average"),
              ("m8", "Percent Change From 50-day Moving Average"),
              ("n",  "Name"),
              ("n4", "Notes"),
              ("o",  "Open"),
              ("p",  "Previous Close"),
              ("p1", "Price Paid"),
              ("p2", "Change in Percent"),
              ("p5", "Price/Sales"),
              ("p6", "Price/Book"),
              ("q",  "Ex-Dividend Date"),
              ("r",  "P/E Ratio"),
              ("r1", "Dividend Pay Date"),
              ("r2", "P/E Ratio (Real-time)"),
              ("r5", "PEG Ratio"),
              ("r6", "Price/EPS Estimate Current Year"),
              ("r7", "Price/EPS Estimate Next Year"),
              ("s",  "Symbol"),
              ("s1", "Shares Owned"),
              ("s7", "Short Ratio"),
              ("t1", "Last Trade Time"),
              ("t6", "Trade Links"),
              ("t7", "Ticker Trend"),
              ("t8", "1 yr Target Price"),
              ("v",  "Volume"),
              ("v1", "Holdings Value"),
              ("v7", "Holdings Value (Real-time)"),
              ("w",  "52-week Range"),
              ("w1", "Day's Value Change"),
              ("w4", "Day's Value Change (Real-time)"),
              ("x",  "Stock Exchange"),
              ("y",  "Dividend Yield") ] )

app = None

ui_win = None
ui_url = None
ui_table = None
ui_symbols = None
ui_flags = None


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self):
        super(TableModel, self).__init__()

        self.flags = []
        self.values = collections.OrderedDict()

    def rowCount(self, parent):
        return len(self.values)

    def columnCount(self, parent):
        return len(self.flags)

    def data(self, index, role):
        if not index.isValid():
            ret = QtCore.QVariant()
        elif role == QtCore.Qt.DisplayRole:
            ret = QtCore.QVariant(self.values.values()[index.row()][index.column()])
        else:
            ret = QtCore.QVariant()

        return ret

    def headerData(self, section, orientation, role):
        if (orientation, role) == (QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole):
            ret = QtCore.QVariant(FLAGS[self.flags[section]])
        elif (orientation, role) == (QtCore.Qt.Vertical, QtCore.Qt.DisplayRole):
            ret = QtCore.QVariant(self.values.keys()[section])
        else:
            ret = QtCore.QVariant()

        return ret


def activeFlags():
    rows = [ui_flags.indexFromItem(lwi).row() for lwi in ui_flags.selectedItems()]
    keys = FLAGS.keys()
    return [keys[idx] for idx in sorted(rows)]


def activeSymbols():
    return str(ui_symbols.toPlainText()).split()


def splitCSVLine(line):
    """
    Some entries in the csv can have commas in a quoted string, so we
    can't simply do a .split(",")
    """

    ret = []
    idx = 0
    while idx < len(line):
        # skip white spaces
        while idx < len(line) and line[idx] in string.whitespace:
            idx += 1

        if idx == len(line):
            # end of line
            break
        elif line[idx] == "\"":
            # the entry is a quoted string
            idx += 1
            start = idx
            while idx < len(line) and line[idx] != "\"":
                idx += 1
            if idx == len(line):
                raise Exception("non-terminated quoted string")
            ret.append(line[start:idx])
            idx += 1

            # skip the comma if it's there
            while idx < len(line) and line[idx] != ",":
                idx += 1
            if idx < len(line):
                idx += 1
        else:
            # non-quoted column
            start = idx
            while idx < len(line) and line[idx] != ",":
                idx += 1
            ret.append(line[start:idx])
            if idx < len(line):
                # skip the comma
                idx += 1

    return ret


def formatURL(symbols, flags):
    syms_str = ",".join(symbols)
    flags_str = "".join(flags)
    return "http://finance.yahoo.com/d/quotes.csv?s=%s&f=%s" % (syms_str, flags_str)


def runFetch():
    try:
        ui_win.setCursor(QtCore.Qt.WaitCursor)
        _runFetch()
    finally:
        ui_win.setCursor(QtCore.Qt.ArrowCursor)


def _runFetch():
    symbols = activeSymbols()
    if not symbols:
        return None

    flags = activeFlags()
    if not flags:
        return None

    try:
        r = urllib2.urlopen(formatURL(symbols, flags))
    except Exception, e:
        QtGui.QErrorMessage(parent=ui_win).showMessage(str(e))
        return

    if r.code != 200:
        QtGui.QErrorMessage(parent=ui_win).showMessage("%d - %s" % (r.code, r.msg))
        return

    lines = r.read().strip().split("\r\n")
    if len(lines) != len(symbols):
        QtGui.QErrorMessage(parent=ui_win).showMessage("line/symbol mismatch")
        return

    values = collections.OrderedDict()
    for sym, line in zip(symbols, lines):
        values[sym] = splitCSVLine(line)

    ui_table.model().beginResetModel()
    ui_table.model().flags = flags
    ui_table.model().values = values
    ui_table.model().endResetModel()


def setURLText():
    ui_url.setText(formatURL(activeSymbols(), activeFlags()))


def setupUI():
    global ui_win
    global ui_url
    global ui_table
    global ui_symbols
    global ui_flags

    b = QtGui.QPushButton("Fetch")
    b.clicked.connect(runFetch)

    ui_url = QtGui.QLineEdit()
    ui_url.setReadOnly(True)

    ui_table = QtGui.QTableView()
    ui_table.setModel(TableModel())

    ui_symbols = QtGui.QTextEdit()
    ui_symbols.textChanged.connect(setURLText)

    ui_flags = QtGui.QListWidget()
    ui_flags.setSelectionMode(QtGui.QListWidget.MultiSelection)
    ui_flags.itemSelectionChanged.connect(setURLText)
    for f in FLAGS.iteritems():
        ui_flags.addItem("%s - %s" % f)

    hbox = QtGui.QHBoxLayout()
    hbox.addWidget(b)
    hbox.addWidget(ui_url)

    splitter = QtGui.QSplitter()
    splitter.addWidget(ui_table)
    splitter.addWidget(ui_symbols)
    splitter.addWidget(ui_flags)

    vbox = QtGui.QVBoxLayout()
    vbox.addLayout(hbox)
    vbox.addWidget(splitter)

    w = QtGui.QWidget()
    w.setLayout(vbox)

    ui_win = QtGui.QMainWindow()
    m = ui_win.menuBar().addMenu("&File")
    m.addAction("E&xit", ui_win.close)
    m = ui_win.menuBar().addMenu("&Edit")
    m.addAction("&Fetch", runFetch)

    ui_win.setCentralWidget(w)
    ui_win.setWindowTitle("Yahoo Finance Grabber")
    ui_win.setWindowIcon(QtGui.QIcon(":/trolltech/qmessagebox/images/qtlogo-64.png"))
    ui_win.show()
    ui_win.resize(1024, 768)

    setURLText()
    splitter.setSizes([450, 100, 250])


app = QtGui.QApplication(sys.argv)
setupUI()
sys.exit(app.exec_())
