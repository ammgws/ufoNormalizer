
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import unittest
import tempfile
import shutil
import datetime
import plistlib
from io import open
from xml.etree import cElementTree as ET
from ufonormalizer import (
    normalizeGLIF, normalizeGlyphsDirectoryNames, normalizeGlyphNames,
    subpathJoin, subpathReadPlist, subpathWriteFile, subpathWritePlist,
    UFONormalizerError, XMLWriter, tobytes, userNameToFileName, handleClash1,
    handleClash2, xmlEscapeText, xmlEscapeAttribute, xmlConvertValue,
    xmlConvertFloat, xmlConvertInt,
    _normalizeGlifAnchor, _normalizeGlifGuideline, _normalizeGlifLib,
    _normalizeGlifNote, _normalizeFontInfoGuidelines, _normalizeGlifUnicode,
    _normalizeGlifAdvance, _normalizeGlifImage, _normalizeDictGuideline,
    _normalizeLayerInfoColor, _normalizeGlifOutlineFormat1,
    _normalizeGlifContourFormat1, _normalizeGlifPointAttributesFormat1,
    _normalizeGlifComponentFormat1, _normalizeGlifComponentAttributesFormat1,
    _normalizeGlifOutlineFormat2, _normalizeGlifContourFormat2,
    _normalizeGlifPointAttributesFormat2,
    _normalizeGlifComponentAttributesFormat2, _normalizeGlifTransformation,
    _normalizeColorString, _convertPlistElementToObject)

# Python 3.4 deprecated readPlistFromBytes and writePlistToBytes
# Python 2 has readPlistFromString and writePlistToString
try:
    from plistlib import loads
except ImportError:
    try:
        from plistlib import readPlistFromBytes as loads
    except ImportError:
        from plistlib import readPlistFromString as loads

GLIFFORMAT1 = '''\
<?xml version="1.0" encoding="UTF-8"?>
<glyph name="period" format="1">
    <unicode hex="002E"/>
    <advance width="268"/>
    <outline>
        <contour>
            <point x="237" y="152"/>
            <point x="193" y="187"/>
            <point x="134" y="187" type="curve" smooth="yes"/>
            <point x="74" y="187"/>
            <point x="30" y="150"/>
            <point x="30" y="88" type="curve" smooth="yes"/>
            <point x="30" y="23"/>
            <point x="74" y="-10"/>
            <point x="134" y="-10" type="curve" smooth="yes"/>
            <point x="193" y="-10"/>
            <point x="237" y="25"/>
            <point x="237" y="88" type="curve" smooth="yes"/>
        </contour>
        <component base="a"/>
        <contour>
            <point name="above" x="236" y="380" type="move"/>
        </contour>
    </outline>
    <lib>
        <dict>
            <key>com.letterror.somestuff</key>
            <string>arbitrary custom data!</string>
        </dict>
    </lib>
</glyph>
'''

GLIFFORMAT2 = '''\
<?xml version="1.0" encoding="UTF-8"?>
<glyph name="period" format="2">
    <unicode hex="002E"/>
    <advance width="268"/>
    <image fileName="period sketch.png" xScale="0.5" yScale="0.5"/>
    <outline>
        <contour>
            <point name="above" x="236" y="380" type="move"/>
        </contour>
        <contour>
            <point x="237" y="152"/>
            <point x="193" y="187"/>
            <point x="134" y="187" type="curve" smooth="yes"/>
            <point x="74" y="187"/>
            <point x="30" y="150"/>
            <point x="30" y="88" type="curve" smooth="yes"/>
            <point x="30" y="23"/>
            <point x="74" y="-10"/>
            <point x="134" y="-10" type="curve" smooth="yes"/>
            <point x="193" y="-10"/>
            <point x="237" y="25"/>
            <point x="237" y="88" type="curve" smooth="yes"/>
        </contour>
        <component base="a"/>
    </outline>
    <anchor name="top" x="74" y="197"/>
    <guideline name="overshoot" y="-12"/>
    <lib>
        <dict>
            <key>com.letterror.somestuff</key>
            <string>arbitrary custom data!</string>
            <key>public.markColor</key>
            <string>1,0,0,0.5</string>
        </dict>
    </lib>
    <note>
        arbitrary text about the glyph
    </note>
</glyph>
'''

INFOPLIST_GUIDELINES = """\
<plist version="1.0">
    <dict>
        <key>guidelines</key>
        <array>
            <dict>
                <key>x</key><integer>1</integer>
                <key>y</key><integer>2</integer>
                <key>angle</key><integer>3</integer>
                <key>color</key><string>1,0,0,.5</string>
            </dict>
            <dict>
                <key>x</key><integer>4</integer>
                <key>y</key><integer>5</integer>
                <key>angle</key><integer>6</integer>
                <key>color</key><string>0,1,0,.5</string>
            </dict>
            <dict>
                <key>x</key><integer>7</integer>
                <key>y</key><integer>8</integer>
                <key>angle</key><integer>9</integer>
                <key>color</key><string>invalid</string>
            </dict>
        </array>
    </dict>
</plist>
"""

INFOPLIST_NO_GUIDELINES = '''\
<plist version="1.0">
    <dict>
        <key>guidelines</key>
        <array/>
    </dict>
</plist>
'''


class UFONormalizerErrorTest(unittest.TestCase):
    def test_str(self):
        err = UFONormalizerError("Testing Error!")
        self.assertEqual(str(err), "Testing Error!")


class UFONormalizerTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)
        # Python 3 renamed assertRaisesRegexp to assertRaisesRegex.
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    def _test_normalizeGlyphsDirectoryNames(self, oldLayers, expectedLayers):
        directory = tempfile.mkdtemp()
        for layerName, subDirectory in oldLayers:
            os.mkdir(os.path.join(directory, subDirectory))
        self.assertEqual(
            sorted(os.listdir(directory)),
            sorted([oldDirectory for oldName, oldDirectory in oldLayers]))
        subpathWritePlist(oldLayers, directory, "layercontents.plist")
        newLayers = normalizeGlyphsDirectoryNames(directory)
        listing = os.listdir(directory)
        listing.remove("layercontents.plist")
        self.assertEqual(
            sorted(listing),
            sorted([newDirectory for newName, newDirectory in newLayers]))
        shutil.rmtree(directory)
        return newLayers == expectedLayers

    def _test_normalizeGlyphNames(self, oldGlyphMapping, expectedGlyphMapping):
        import tempfile
        directory = tempfile.mkdtemp()
        layerDirectory = "glyphs"
        fullLayerDirectory = subpathJoin(directory, layerDirectory)
        os.mkdir(fullLayerDirectory)
        for fileName in oldGlyphMapping.values():
            subpathWriteFile("", directory, layerDirectory, fileName)
        self.assertEqual(sorted(os.listdir(fullLayerDirectory)),
                         sorted(oldGlyphMapping.values()))
        subpathWritePlist(oldGlyphMapping, directory, layerDirectory,
                          "contents.plist")
        newGlyphMapping = normalizeGlyphNames(directory, layerDirectory)
        listing = os.listdir(fullLayerDirectory)
        listing.remove("contents.plist")
        self.assertEqual(sorted(listing), sorted(newGlyphMapping.values()))
        self.assertEqual(
            subpathReadPlist(directory, layerDirectory, "contents.plist"),
            newGlyphMapping)
        shutil.rmtree(directory)
        return newGlyphMapping == expectedGlyphMapping

    def test_normalizeGlyphsDirectoryNames_non_standard(self):
        oldLayers = [
            ("public.default", "glyphs"),
            ("Sketches", "glyphs.sketches"),
        ]
        expectedLayers = [
            ("public.default", "glyphs"),
            ("Sketches", "glyphs.S_ketches"),
        ]
        self.assertTrue(
            self._test_normalizeGlyphsDirectoryNames(
                oldLayers, expectedLayers))

    def test_normalizeGlyphsDirectoryNames_old_same_as_new(self):
        oldLayers = [
            ("public.default", "glyphs"),
            ("one", "glyphs.two"),
            ("two", "glyphs.three")
        ]
        expectedLayers = [
            ("public.default", "glyphs"),
            ("one", "glyphs.one"),
            ("two", "glyphs.two")
        ]
        self.assertTrue(
            self._test_normalizeGlyphsDirectoryNames(
                oldLayers, expectedLayers))

    def test_normalizeLayerInfoPlist_color(self):
        obj = dict(color="1,0,0,.5")
        _normalizeLayerInfoColor(obj)
        self.assertEqual(obj, {'color': '1,0,0,0.5'})

        obj = dict(color="invalid")
        _normalizeLayerInfoColor(obj)
        self.assertEqual(obj, {})

    def test_normalizeGlyphNames_non_standard(self):
        oldNames = {
            "A": "a.glif",
            "B": "b.glif"
        }
        expectedNames = {
            "A": "A_.glif",
            "B": "B_.glif"
        }
        self.assertTrue(
            self._test_normalizeGlyphNames(oldNames, expectedNames))

    def test_normalizeGlyphNames_old_same_as_new(self):
        oldNames = {
            "one": "two.glif",
            "two": "three.glif"
        }
        expectedNames = {
            "one": "one.glif",
            "two": "two.glif"
        }
        self.assertTrue(
            self._test_normalizeGlyphNames(oldNames, expectedNames))

    def test_normalizeFontInfoPlist_guidelines(self):
        test = INFOPLIST_GUIDELINES
        expected = {
            "guidelines": [
                dict(x=1, y=2, angle=3, color="1,0,0,0.5"),
                dict(x=4, y=5, angle=6, color="0,1,0,0.5"),
                dict(x=7, y=8, angle=9),
            ]
        }
        plist = loads(tobytes(test))
        _normalizeFontInfoGuidelines(plist)
        self.assertEqual(plist, expected)

    def test_normalizeFontInfoPlist_no_guidelines(self):
        test = INFOPLIST_NO_GUIDELINES
        plist = loads(tobytes(test))
        self.assertIsNone(_normalizeFontInfoGuidelines(plist))

    def test_normalizeFontInfoPlist_guidelines_everything(self):
        guideline = dict(x=1, y=2, angle=3, name="test", color="1,0,0,.5",
                         identifier="TEST")
        expected = dict(x=1, y=2, angle=3, name="test", color="1,0,0,0.5",
                        identifier="TEST")
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_no_x(self):
        guideline = dict(y=2, name="test", color="1,0,0,.5", identifier="TEST")
        expected = dict(y=2, name="test", color="1,0,0,0.5", identifier="TEST")
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

        guideline = dict(y=2, angle=3, name="test", color="1,0,0,.5",
                         identifier="TEST")
        expected = None
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_invalid_x(self):
        guideline = dict(x="invalid", y=2, angle=3, name="test",
                         color="1,0,0,.5", identifier="TEST")
        expected = None
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_no_y(self):
        guideline = dict(x=1, name="test", color="1,0,0,.5", identifier="TEST")
        expected = dict(x=1, name="test", color="1,0,0,0.5", identifier="TEST")
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

        guideline = dict(x=1, angle=3, name="test", color="1,0,0,.5",
                         identifier="TEST")
        expected = None
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_invalid_y(self):
        guideline = dict(x=1, y="invalid", angle=3, name="test",
                         color="1,0,0,.5", identifier="TEST")
        expected = None
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_no_angle(self):
        guideline = dict(x=1, y=2, name="test", color="1,0,0,.5",
                         identifier="TEST")
        expected = None
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_invalid_angle(self):
        guideline = dict(x=1, y=3, angle="invalid", name="test",
                         color="1,0,0,.5", identifier="TEST")
        expected = None
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_no_name(self):
        guideline = dict(x=1, y=2, angle=3, color="1,0,0,.5",
                         identifier="TEST")
        expected = dict(x=1, y=2, angle=3, color="1,0,0,0.5",
                        identifier="TEST")
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_no_color(self):
        guideline = dict(x=1, y=2, angle=3, name="test", identifier="TEST")
        expected = dict(x=1, y=2, angle=3, name="test", identifier="TEST")
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def test_normalizeFontInfoPlist_guidelines_no_identifier(self):
        guideline = dict(x=1, y=2, angle=3, name="test", color="1,0,0,.5")
        expected = dict(x=1, y=2, angle=3, name="test", color="1,0,0,0.5")
        result = _normalizeDictGuideline(guideline)
        self.assertEqual(result, expected)

    def _test_glifFormat(self):
        glifFormat = {}
        glifFormat[1] = GLIFFORMAT1.strip().replace("    ", "\t")

        glifFormat[2] = GLIFFORMAT2.strip().replace("    ", "\t")
        return glifFormat

    def test_normalizeGLIF_formats_1_and_2(self):
        self.maxDiff = None
        glifFormat = self._test_glifFormat()
        glifFolderPath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'data', 'glif')
        for i in [1, 2]:
            glifFileName = 'format%s.glif' % i
            glifFilePath = os.path.join(glifFolderPath, glifFileName)
            normalizeGLIF(glifFolderPath, glifFileName)
            glifFile = open(glifFilePath, 'r')
            glifFileData = glifFile.read()
            glifFile.close()
            self.assertEqual(glifFileData, glifFormat[i])

    def test_normalizeGLIF_no_formats(self):
        glifFileName = 'formatNone.glif'
        glifFolderPath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'data', 'glif')
        with self.assertRaisesRegex(
                UFONormalizerError,
                r"Undefined GLIF format: .*formatNone.glif"):
            normalizeGLIF(glifFolderPath, glifFileName)

    def test_normalizeGLIF_unicode_without_hex(self):
        element = ET.fromstring("<unicode />")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<unicode hex=''/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<unicode hexagon=''/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<unicode hex='xyz'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_unicode_with_hex(self):
        element = ET.fromstring("<unicode hex='0041'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="0041"/>')

        element = ET.fromstring("<unicode hex='41'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="0041"/>')

        element = ET.fromstring("<unicode hex='ea'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="00EA"/>')

        element = ET.fromstring("<unicode hex='2Af'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="02AF"/>')

        element = ET.fromstring("<unicode hex='0000fFfF'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="FFFF"/>')

        element = ET.fromstring("<unicode hex='10000'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="10000"/>')

        element = ET.fromstring("<unicode hex='abcde'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifUnicode(element, writer)
        self.assertEqual(writer.getText(), '<unicode hex="ABCDE"/>')

    def test_normalizeGLIF_advance_undefined(self):
        element = ET.fromstring("<advance />")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_advance_defaults(self):
        element = ET.fromstring("<advance width='0'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<advance height='0'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<advance width='0' height='0'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<advance width='1' height='0'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance width="1"/>')

        element = ET.fromstring('<advance width="0" height="1"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance height="1"/>')

    def test_normalizeGLIF_advance_width(self):
        element = ET.fromstring('<advance width="325.0"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance width="325"/>')

        element = ET.fromstring('<advance width="325.1"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance width="325.1"/>')

        element = ET.fromstring('<advance width="-325.0"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance width="-325"/>')

    def test_normalizeGLIF_advance_height(self):
        element = ET.fromstring('<advance height="325.0"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance height="325"/>')

        element = ET.fromstring('<advance height="325.1"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance height="325.1"/>')

        element = ET.fromstring('<advance height="-325.0"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '<advance height="-325"/>')

    def test_normalizeGLIF_advance_invalid_values(self):
        element = ET.fromstring('<advance width="a" height="_"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring('<advance width="60" height="_"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring('<advance width="a" height="50"/>')
        writer = XMLWriter(declaration=None)
        _normalizeGlifAdvance(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_image_everything(self):
        element = ET.fromstring(
            "<image fileName='Sketch 1.png' xOffset='100' yOffset='200' "
            "xScale='.75' yScale='.75' color='1,0,0,.5'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifImage(element, writer)
        self.assertEqual(
            writer.getText(),
            '<image fileName="Sketch 1.png" xScale="0.75" yScale="0.75" '
            'xOffset="100" yOffset="200" color="1,0,0,0.5"/>')

    def test_normalizeGLIF_image_empty(self):
        element = ET.fromstring("<image />")
        writer = XMLWriter(declaration=None)
        _normalizeGlifImage(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_image_no_file_name(self):
        element = ET.fromstring(
            "<image xOffset='100' yOffset='200' xScale='.75' yScale='.75' "
            "color='1,0,0,.5'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifImage(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_image_no_transformation(self):
        element = ET.fromstring(
            "<image fileName='Sketch 1.png' color='1,0,0,.5' />")
        writer = XMLWriter(declaration=None)
        _normalizeGlifImage(element, writer)
        self.assertEqual(
            writer.getText(),
            '<image fileName="Sketch 1.png" color="1,0,0,0.5"/>')

    def test_normalizeGLIF_image_no_color(self):
        element = ET.fromstring(
            "<image fileName='Sketch 1.png' xOffset='100' yOffset='200' "
            "xScale='.75' yScale='.75'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifImage(element, writer)
        self.assertEqual(
            writer.getText(),
            '<image fileName="Sketch 1.png" xScale="0.75" yScale="0.75" '
            'xOffset="100" yOffset="200"/>')

    def test_normalizeGLIF_anchor_everything(self):
        element = ET.fromstring(
            "<anchor name='test' x='230' y='4.50' color='1,0,0,.5' "
            "identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(
            writer.getText(),
            '<anchor name="test" x="230" y="4.5" color="1,0,0,0.5" '
            'identifier="TEST"/>')

    def test_normalizeGLIF_anchor_no_name(self):
        element = ET.fromstring(
            "<anchor x='230' y='4.50' color='1,0,0,.5' "
            "identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(
            writer.getText(),
            '<anchor x="230" y="4.5" color="1,0,0,0.5" '
            'identifier="TEST"/>')

    def test_normalizeGLIF_anchor_no_x(self):
        element = ET.fromstring(
            "<anchor name='test' y='4.50' color='1,0,0,.5' "
            "identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring(
            "<anchor name='test' x='invalid' y='4.50' color='1,0,0,.5' "
            "identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_anchor_no_y(self):
        element = ET.fromstring(
            "<anchor name='test' x='230' color='1,0,0,.5' identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring(
            "<anchor name='test' x='230' y='invalid' color='1,0,0,.5' "
            "identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_anchor_no_color(self):
        element = ET.fromstring(
            "<anchor name='test' x='230' y='4.50' identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(
            writer.getText(),
            '<anchor name="test" x="230" y="4.5" identifier="TEST"/>')

    def test_normalizeGLIF_anchor_no_identifier(self):
        element = ET.fromstring(
            "<anchor name='test' x='230' y='4.50' color='1,0,0,.5'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifAnchor(element, writer)
        self.assertEqual(
            writer.getText(),
            '<anchor name="test" x="230" y="4.5" color="1,0,0,0.5"/>')

    def test_normalizeGLIF_guideline_everything(self):
        element = ET.fromstring(
            "<guideline x='1' y='2' angle='3' name='test' color='1,0,0,.5' "
            "identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifGuideline(element, writer)
        self.assertEqual(
            writer.getText(),
            '<guideline name="test" x="1" y="2" angle="3" color="1,0,0,0.5" '
            'identifier="TEST"/>')

    def test_normalizeGLIF_guideline_invalid(self):
        element = ET.fromstring(
            "<guideline name='test' color='1,0,0,.5' identifier='TEST'/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifGuideline(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_lib_defined(self):
        e = '''
        <lib>
            <dict>
                <key>foo</key>
                <string>bar</string>
            </dict>
        </lib>
        '''.strip()
        element = ET.fromstring(e)
        writer = XMLWriter(declaration=None)
        _normalizeGlifLib(element, writer)
        self.assertEqual(
            writer.getText(),
            '<lib>\n\t<dict>\n\t\t<key>foo</key>\n\t\t<string>bar</string>'
            '\n\t</dict>\n</lib>')

    def test_normalizeGLIF_lib_undefined(self):
        element = ET.fromstring("<lib></lib>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifLib(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<lib><dict></dict></lib>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifLib(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_note_defined(self):
        element = ET.fromstring("<note>Blah</note>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(writer.getText(), "<note>\n\tBlah\n</note>")

        element = ET.fromstring("<note>   Blah  \t\n\t  </note>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(writer.getText(), "<note>\n\tBlah\n</note>")

        element = ET.fromstring(
            tobytes("<note>Don't forget to check the béziers!!</note>",
                    encoding="utf8"))
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(
            writer.getText(),
            "<note>\n\tDon't forget to check the b\xe9ziers!!\n</note>")

        element = ET.fromstring(
            tobytes("<note>A quick brown fox jumps over the lazy dog.\n"
                    "Příliš žluťoučký kůň úpěl ďábelské ódy.</note>",
                    encoding="utf-8"))
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(
            writer.getText(),
            "<note>\n\tA quick brown fox jumps over the lazy dog.\n\t"
            "P\u0159\xedli\u0161 \u017elu\u0165ou\u010dk\xfd k\u016f\u0148 "
            "\xfap\u011bl \u010f\xe1belsk\xe9 \xf3dy.\n</note>")

        element = ET.fromstring(
            "<note>   Line1  \t\n\n    Line3\t  </note>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(
            writer.getText(),
            "<note>\n\tLine1\n\t\n\t    Line3\n</note>")

    def test_normalizeGLIF_note_undefined(self):
        element = ET.fromstring("<note></note>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<note>   </note>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<note>\n\n</note>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(writer.getText(), '')

        element = ET.fromstring("<note/>")
        writer = XMLWriter(declaration=None)
        _normalizeGlifNote(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_outline_format1_empty(self):
        outline = "<outline/>"
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat1(element, writer)
        self.assertEqual(writer.getText(), '')

        outline = "<outline>\n</outline>"
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat1(element, writer)
        self.assertEqual(writer.getText(), '')

        outline = "<outline>\n\t<contour/>\n\t<component/>\n</outline>"
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat1(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGLIF_outline_format1_element_order(self):
        outline = '''\
            <outline>
                <contour>
                    <point type="move" y="0" x="0" name="anchor1"/>
                </contour>
                <contour>
                    <point type="line" y="1" x="1"/>
                </contour>
                <component base="2"/>
                <contour>
                    <point type="line" y="3" x="3"/>
                </contour>
                <component base="4"/>
                <contour>
                    <point type="move" y="0" x="0" name="anchor2"/>
                </contour>
            </outline>
            '''.strip().replace(" "*12, "")
        expected = '''\
            <outline>
                <contour>
                    <point x="1" y="1" type="line"/>
                </contour>
                <component base="2"/>
                <contour>
                    <point x="3" y="3" type="line"/>
                </contour>
                <component base="4"/>
                <contour>
                    <point name="anchor1" x="0" y="0" type="move"/>
                </contour>
                <contour>
                    <point name="anchor2" x="0" y="0" type="move"/>
                </contour>
            </outline>
            '''.strip().replace(" "*12, "").replace("    ", "\t")
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat1(element, writer)
        self.assertEqual(writer.getText(), expected)

    def test_normalizeGlif_contour_format1_empty(self):
        contour = '''
        <contour/>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat1(element))

        contour = '''
        <contour>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat1(element))

    def test_normalizeGlif_contour_format1_point_without_attributes(self):
        contour = '''
        <contour>
           <point/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat1(element))

    def test_normalizeGlif_contour_format1_unkown_child_element(self):
        contour = '''
        <contour>
           <piont type="line" y="0" x="0"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat1(element))

    def test_normalizeGlif_contour_format1_unkown_point_type(self):
        contour = '''
        <contour>
           <point type="invalid" y="0" x="0"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat1(element))

    def test_normalizeGlif_contour_format1_implied_anchor(self):
        contour = '''
        <contour>
           <point type="move" y="0" x="0" name="anchor1"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertEqual(
            sorted(_normalizeGlifContourFormat1(element).items()),
            [('name', 'anchor1'), ('type', 'anchor'), ('x', 0.0), ('y', 0.0)])

    def test_normalizeGlif_contour_format1_implied_anchor_with_empty_name(self):
        contour = '''
        <contour>
           <point type="move" y="0" x="0" name=""/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertEqual(
            sorted(_normalizeGlifContourFormat1(element).items()),
            [('name', ''), ('type', 'anchor'), ('x', 0.0), ('y', 0.0)])

    def test_normalizeGlif_contour_format1_implied_anchor_without_name(self):
        contour = '''
        <contour>
           <point type="move" y="0" x="0"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertEqual(
            sorted(_normalizeGlifContourFormat1(element).items()),
            [('type', 'anchor'), ('x', 0.0), ('y', 0.0)])

    def test_normalizeGlif_contour_format1_normal(self):
        contour = '''
        <contour>
           <point type="line" y="0" x="0"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        result = _normalizeGlifContourFormat1(element)
        result["type"]
        'contour'
        self.assertEqual(len(result["points"]), 1)
        self.assertEqual(
            sorted(result["points"][0].items()),
            [('type', 'line'), ('x', 0.0), ('y', 0.0)])

        contour = '''
        <contour>
           <point type="move" y="0" x="0"/>
           <point type="line" y="1" x="1"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        result = _normalizeGlifContourFormat1(element)
        result["type"]
        'contour'
        self.assertEqual(len(result["points"]), 2)
        self.assertEqual(
            sorted(result["points"][0].items()),
            [('type', 'move'), ('x', 0.0), ('y', 0.0)])
        self.assertEqual(
            sorted(result["points"][1].items()),
            [('type', 'line'), ('x', 1.0), ('y', 1.0)])

    def test_normalizeGlif_point_attributes_format1_everything(self):
        point = "<point x='1' y='2.5' type='line' name='test' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('name', 'test'), ('smooth', 'yes'),
             ('type', 'line'), ('x', 1.0), ('y', 2.5)])

    def test_normalizeGlif_point_attributes_format1_no_x(self):
        point = "<point y='2.5' type='line' name='test' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [])

    def test_normalizeGlif_point_attributes_format1_no_y(self):
        point = "<point x='1' type='line' name='test' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [])

    def test_normalizeGlif_point_attributes_format1_invalid_x(self):
        point = "<point x='a' y='30'/>"
        element = ET.fromstring(point)
        self.assertIsNone(_normalizeGlifPointAttributesFormat1(element))

    def test_normalizeGlif_point_attributes_format1_invalid_y(self):
        point = "<point x='20' y='b'/>"
        element = ET.fromstring(point)
        self.assertIsNone(_normalizeGlifPointAttributesFormat1(element))

    def test_normalizeGlif_point_attributes_format1_no_name(self):
        point = "<point x='1' y='2.5' type='line' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('smooth', 'yes'), ('type', 'line'), ('x', 1.0), ('y', 2.5)])

    def test_normalizeGlif_point_attributes_format1_empty_name(self):
        point = "<point x='1' y='2.5' type='line' name='' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('name', ''), ('smooth', 'yes'), ('type', 'line'), ('x', 1.0), ('y', 2.5)])

    def test_normalizeGlif_point_attributes_format1_type_and_smooth(self):
        point = "<point x='1' y='2.5' type='move' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('smooth', 'yes'), ('type', 'move'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='move' smooth='no'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'move'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='move'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'move'), ('x', 1.0), ('y', 2.5)])

        point = "<point x='1' y='2.5' type='line' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('smooth', 'yes'), ('type', 'line'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='line' smooth='no'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'line'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='line'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'line'), ('x', 1.0), ('y', 2.5)])

        point = "<point x='1' y='2.5' type='curve' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('smooth', 'yes'), ('type', 'curve'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='curve' smooth='no'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'curve'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='curve'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'curve'), ('x', 1.0), ('y', 2.5)])

        point = "<point x='1' y='2.5' type='qcurve' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('smooth', 'yes'), ('type', 'qcurve'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='qcurve' smooth='no'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'qcurve'), ('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='qcurve'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('type', 'qcurve'), ('x', 1.0), ('y', 2.5)])

        point = "<point x='1' y='2.5' type='offcurve' smooth='yes'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='offcurve' smooth='no'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('x', 1.0), ('y', 2.5)])
        point = "<point x='1' y='2.5' type='offcurve'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('x', 1.0), ('y', 2.5)])

        point = "<point x='1' y='2.5'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('x', 1.0), ('y', 2.5)])

        point = "<point x='1' y='2.5' type='invalid'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [])

    def test_normalizeGlif_point_attributes_format1_subelement(self):
        point = "<point x='1' y='2.5'><invalid/></point>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat1(element).items()),
            [('x', 1.0), ('y', 2.5)])

    def test_normalizeGlif_component_format1_everything(self):
        component = "<component base='test' xScale='10' xyScale='2.2' "\
                    "yxScale='3' yScale='4.4' xOffset='5' yOffset='6.6'/>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentFormat1(element).items()),
            [('base', 'test'), ('type', 'component'),
             ('xOffset', 5.0), ('xScale', 10.0), ('xyScale', 2.2),
             ('yOffset', 6.6), ('yScale', 4.4), ('yxScale', 3.0)])

    def test_normalizeGlif_component_format1_no_base(self):
        component = "<component xScale='1' xyScale='2.2' yxScale='3' "\
                    "yScale='4.4' xOffset='5' yOffset='6.6'/>"
        element = ET.fromstring(component)
        _normalizeGlifComponentFormat1(element)

    def test_normalizeGlif_component_format1_subelement(self):
        component = "<component base='test'><foo/></component>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentFormat1(element).items()),
            [('base', 'test'), ('type', 'component')])

    def test_normalizeGlif_component_attributes_format1_everything(self):
        component = "<component base='test' xScale='10' xyScale='2.2' "\
                    "yxScale='3' yScale='4.4' xOffset='5' yOffset='6.6'/>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentAttributesFormat1(element).items()),
            [('base', 'test'),
             ('xOffset', 5.0), ('xScale', 10.0), ('xyScale', 2.2),
             ('yOffset', 6.6), ('yScale', 4.4), ('yxScale', 3.0)])

    def test_normalizeGlif_component_attributes_format1_no_base(self):
        component = "<component xScale='10' xyScale='2.2' yxScale='3' "\
                    "yScale='4.4' xOffset='5' yOffset='6.6'/>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentAttributesFormat1(element).items()),
            [])

    def test_normalizeGlif_component_attributes_format1_no_transformation(self):
        component = "<component base='test'/>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentAttributesFormat1(element).items()),
            [('base', 'test')])

    def test_normalizeGlif_component_attributes_format1_defaults(self):
        component = "<component base='test' xScale='1' xyScale='0' "\
                    " yxScale='0' yScale='1' xOffset='0' yOffset='0'/>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentAttributesFormat1(element).items()),
            [('base', 'test')])

    def test_normalizeGlif_outline_format2_empty(self):
        outline = '''
        <outline>
        </outline>
        '''
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat2(element, writer)
        self.assertEqual(writer.getText(), '')

        outline = '''
        <outline>
            <contour />
            <component />
        </outline>
        '''
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat2(element, writer)
        self.assertEqual(writer.getText(), '')

    def test_normalizeGlif_outline_format2_element_order(self):
        outline = '''
        <outline>
            <contour>
                <point type="line" y="1" x="1"/>
            </contour>
            <component base="2"/>
            <contour identifier='test'>
                <point type="line" y="3" x="3"/>
            </contour>
            <component base="4"/>
        </outline>
        '''.strip()
        expected = '<outline>\n'\
                   '\t<contour>\n'\
                   '\t\t<point x="1" y="1" type="line"/>\n'\
                   '\t</contour>\n'\
                   '\t<component base="2"/>\n'\
                   '\t<contour identifier="test">\n'\
                   '\t\t<point x="3" y="3" type="line"/>\n'\
                   '\t</contour>\n'\
                   '\t<component base="4"/>\n'\
                   '</outline>'
        element = ET.fromstring(outline)
        writer = XMLWriter(declaration=None)
        _normalizeGlifOutlineFormat2(element, writer)
        self.assertEqual(writer.getText(), expected)


    def test_normalizeGlif_contour_format2_empty(self):
        contour = '''
        <contour>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat2(element))

    def test_normalizeGlif_contour_format2_point_without_attributes(self):
        contour = '''
        <contour>
        <point/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat2(element))

    def test_normalizeGlif_contour_format2_unknown_child_element(self):
        contour = '''
        <contour>
        <piont type="line" y="0" x="0"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        self.assertIsNone(_normalizeGlifContourFormat2(element))

    def test_normalizeGlif_contour_format2_normal(self):
        contour = '''
        <contour identifier="test">
        <point type="line" y="0" x="0"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        result = _normalizeGlifContourFormat2(element)
        self.assertEqual(result["type"], 'contour')
        self.assertEqual(result["identifier"], 'test')
        self.assertEqual(len(result["points"]), 1)
        self.assertEqual(sorted(result["points"][0].items()),
                         [('type', 'line'), ('x', 0.0), ('y', 0.0)])

        contour = '''
        <contour identifier="test">
        <point type="move" y="0" x="0"/>
        <point type="line" y="1" x="1"/>
        </contour>
        '''
        element = ET.fromstring(contour)
        result = _normalizeGlifContourFormat2(element)
        self.assertEqual(result["type"], 'contour')
        self.assertEqual(result["identifier"], 'test')
        self.assertEqual(len(result["points"]), 2)
        self.assertEqual(sorted(result["points"][0].items()),
                         [('type', 'move'), ('x', 0.0), ('y', 0.0)])
        self.assertEqual(sorted(result["points"][1].items()),
                         [('type', 'line'), ('x', 1.0), ('y', 1.0)])

    def test_normalizeGlif_point_attributes_format2_everything(self):
        point = "<point x='1' y='2.5' type='line' name='test' smooth='yes' identifier='TEST'/>"
        element = ET.fromstring(point)
        self.assertEqual(
            sorted(_normalizeGlifPointAttributesFormat2(element).items()),
            [('identifier', 'TEST'), ('name', 'test'), ('smooth', 'yes'),
             ('type', 'line'), ('x', 1.0), ('y', 2.5)])

    def test_normalizeGlif_component_attributes_format2_everything(self):
        component = "<component base='test' xScale='10' xyScale='2.2' "\
                    "yxScale='3' yScale='4.4' xOffset='5' yOffset='6.6' "\
                    "identifier='test'/>"
        element = ET.fromstring(component)
        self.assertEqual(
            sorted(_normalizeGlifComponentAttributesFormat2(element).items()),
            [('base', 'test'), ('identifier', 'test'),
             ('xOffset', 5.0), ('xScale', 10.0), ('xyScale', 2.2),
             ('yOffset', 6.6), ('yScale', 4.4), ('yxScale', 3.0)])

    def test_normalizeGlif_transformation_empty(self):
        element = ET.fromstring("<test/>")
        self.assertEqual(_normalizeGlifTransformation(element), {})

    def test_normalizeGlif_transformation_default(self):
        element = ET.fromstring("<test xScale='1' xyScale='0' yxScale='0' "
                                "yScale='1' xOffset='0' yOffset='0'/>")
        self.assertEqual(_normalizeGlifTransformation(element), {})

    def test_normalizeGlif_transformation_non_default(self):
        element = ET.fromstring("<test xScale='2' xyScale='3' yxScale='4' "
                                "yScale='5' xOffset='6' yOffset='7'/>")
        self.assertEqual(
            sorted(_normalizeGlifTransformation(element).items()),
            [('xOffset', 6.0), ('xScale', 2.0), ('xyScale', 3.0),
             ('yOffset', 7.0), ('yScale', 5.0), ('yxScale', 4.0)])

    def test_normalizeGlif_transformation_invalid_value(self):
        element = ET.fromstring("<test xScale='a'/>")
        self.assertEqual(_normalizeGlifTransformation(element), {})

    def test_normalizeGlif_transformation_unknown_attribute(self):
        element = ET.fromstring("<test rotate='1'/>")
        self.assertEqual(_normalizeGlifTransformation(element), {})

    def test_normalize_color_string(self):
        _normalizeColorString("")
        _normalizeColorString("1,1,1")
        self.assertEqual(_normalizeColorString("1,1,1,1"), '1,1,1,1')
        self.assertEqual(_normalizeColorString(".1,.1,.1,.1"),
                         '0.1,0.1,0.1,0.1')
        _normalizeColorString("1,1,1,a")
        _normalizeColorString("1,1,-1,1")
        _normalizeColorString("1,2,1,1")
        _normalizeColorString(",,,")

    def test_convert_plist_Element_to_object(self):
        element = ET.fromstring("<array></array>")
        self.assertEqual(_convertPlistElementToObject(element), [])
        element = ET.fromstring("<array><integer>0</integer><real>.1</real></array>")
        self.assertEqual(_convertPlistElementToObject(element), [0, 0.1])
        element = ET.fromstring("<dict></dict>")
        self.assertEqual(_convertPlistElementToObject(element), {})
        element = ET.fromstring("<dict><key>foo</key><string>bar</string></dict>")
        self.assertEqual(_convertPlistElementToObject(element), {'foo': 'bar'})
        element = ET.fromstring("<string>foo</string>")
        self.assertEqual(_convertPlistElementToObject(element), 'foo')
        element = ET.fromstring("<date>2015-07-05T22:16:18Z</date>")
        self.assertEqual(_convertPlistElementToObject(element),
                         datetime.datetime(2015, 7, 5, 22, 16, 18))
        element = ET.fromstring("<true />")
        self.assertEqual(_convertPlistElementToObject(element), True)
        element = ET.fromstring("<false />")
        self.assertEqual(_convertPlistElementToObject(element), False)
        element = ET.fromstring("<real>1.1</real>")
        self.assertEqual(_convertPlistElementToObject(element), 1.1)
        element = ET.fromstring("<integer>1</integer>")
        self.assertEqual(_convertPlistElementToObject(element), 1)
        element = ET.fromstring("<data>YWJj</data>")
        self.assertEqual(_convertPlistElementToObject(element),
                         plistlib.Data(b'abc'))


class XMLWriterTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)
        # Python 3 renamed assertRaisesRegexp to assertRaisesRegex.
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    def test_propertyListObject_array(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject([])
        self.assertEqual(writer.getText(), '<array>\n</array>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(["a"])
        self.assertEqual(writer.getText(),
                        '<array>\n\t<string>a</string>\n</array>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject([None])
        self.assertEqual(writer.getText(), '<array>\n</array>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject([False])
        self.assertEqual(writer.getText(), '<array>\n\t<false/>\n</array>')

    def test_propertyListObject_dict(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject({})
        self.assertEqual(writer.getText(), '<dict>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({"a": "b"})
        self.assertEqual(
            writer.getText(),
            '<dict>\n\t<key>a</key>\n\t<string>b</string>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({"a&b": "b&a"})
        self.assertEqual(
            writer.getText(),
            '<dict>\n\t<key>a&amp;b</key>\n\t<string>b&amp;a</string>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({"a": 20.2})
        self.assertEqual(
            writer.getText(),
            '<dict>\n\t<key>a</key>\n\t<real>20.2</real>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({"a": 20.0})
        self.assertEqual(
            writer.getText(),
            '<dict>\n\t<key>a</key>\n\t<integer>20</integer>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({"": ""})
        self.assertEqual(
            writer.getText(),
            '<dict>\n\t<key></key>\n\t<string></string>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({None: ""})
        self.assertEqual(
            writer.getText(),
            '<dict>\n\t<key/>\n\t<string></string>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({"": None})
        self.assertEqual(writer.getText(), '<dict>\n\t<key></key>\n</dict>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject({None: None})
        self.assertEqual(writer.getText(), '<dict>\n\t<key/>\n</dict>')

    def test_propertyListObject_string(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject("a")
        self.assertEqual(writer.getText(), '<string>a</string>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject("&")
        self.assertEqual(writer.getText(), '<string>&amp;</string>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject("1.000")
        self.assertEqual(writer.getText(), '<string>1.000</string>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject("")
        self.assertEqual(writer.getText(), '<string></string>')

    def test_propertyListObject_boolean(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject(True)
        self.assertEqual(writer.getText(), '<true/>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(False)
        self.assertEqual(writer.getText(), '<false/>')

    def test_propertyListObject_float(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject(1.1)
        self.assertEqual(writer.getText(), '<real>1.1</real>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(-1.1)
        self.assertEqual(writer.getText(), '<real>-1.1</real>')

    def test_propertyListObject_integer(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject(1.0)
        self.assertEqual(writer.getText(), '<integer>1</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(-1.0)
        self.assertEqual(writer.getText(), '<integer>-1</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(0.0)
        self.assertEqual(writer.getText(), '<integer>0</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(-0.0)
        self.assertEqual(writer.getText(), '<integer>0</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(1)
        self.assertEqual(writer.getText(), '<integer>1</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(-1)
        self.assertEqual(writer.getText(), '<integer>-1</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(+1)
        self.assertEqual(writer.getText(), '<integer>1</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(0)
        self.assertEqual(writer.getText(), '<integer>0</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(-0)
        self.assertEqual(writer.getText(), '<integer>0</integer>')

        writer = XMLWriter(declaration=None)
        writer.propertyListObject(2015-1-1)
        self.assertEqual(writer.getText(), '<integer>2013</integer>')

    def test_propertyListObject_date(self):
        writer = XMLWriter(declaration=None)
        date = datetime.datetime(2012, 9, 1)
        writer.propertyListObject(date)
        self.assertEqual(writer.getText(), '<date>2012-09-01T00:00:00Z</date>')

        writer = XMLWriter(declaration=None)
        date = datetime.datetime(2009, 11, 29, 16, 31, 53)
        writer.propertyListObject(date)
        self.assertEqual(writer.getText(), '<date>2009-11-29T16:31:53Z</date>')

    def test_propertyListObject_data(self):
        writer = XMLWriter(declaration=None)
        data = plistlib.Data(tobytes("abc"))
        writer.propertyListObject(data)
        self.assertEqual(writer.getText(), '<data>\n\tYWJj\n</data>')

    def test_propertyListObject_none(self):
        writer = XMLWriter(declaration=None)
        writer.propertyListObject(None)
        self.assertEqual(writer.getText(), '')

    def test_propertyListObject_unknown_data_type(self):
        writer = XMLWriter(declaration=None)
        with self.assertRaisesRegex(
                UFONormalizerError,
                r"Unknown data type in property list: <.* 'complex'>"):
            writer.propertyListObject(1.0j)

    def test_attributesToString(self):
        attrs = dict(a="blah", x=1, y=2.1)
        writer = XMLWriter(declaration=None)
        self.assertEqual(
            writer.attributesToString(attrs),
            'x="1" y="2.1" a="blah"')

    def test_xmlEscapeText(self):
        self.assertEqual(xmlEscapeText("&"), "&amp;")
        self.assertEqual(xmlEscapeText("<"), "&lt;")
        self.assertEqual(xmlEscapeText(">"), "&gt;")
        self.assertEqual(xmlEscapeText("a"), "a")
        self.assertEqual(xmlEscapeText("ä"), "ä")
        self.assertEqual(xmlEscapeText("ā"), "ā")
        self.assertEqual(xmlEscapeText("𐐀"), "𐐀")
        self.assertEqual(xmlEscapeText("©"), "©")
        self.assertEqual(xmlEscapeText("—"), "—")
        self.assertEqual(xmlEscapeText("1"), "1")
        self.assertEqual(xmlEscapeText("1.0"), "1.0")
        self.assertEqual(xmlEscapeText("'"), "'")
        self.assertEqual(xmlEscapeText("/"), "/")
        self.assertEqual(xmlEscapeText("\\"), "\\")
        self.assertEqual(xmlEscapeText("\r"), "\r")

    def test_xmlEscapeAttribute(self):
        self.assertEqual(xmlEscapeAttribute('"'), '&quot;')
        self.assertEqual(xmlEscapeAttribute("'"), "'")
        self.assertEqual(xmlEscapeAttribute("abc"), 'abc')
        self.assertEqual(xmlEscapeAttribute("123"), '123')
        self.assertEqual(xmlEscapeAttribute("/"), '/')
        self.assertEqual(xmlEscapeAttribute("\\"), '\\')

    def test_xmlConvertValue(self):
        self.assertEqual(xmlConvertValue(0.0), '0')
        self.assertEqual(xmlConvertValue(-0.0), '0')
        self.assertEqual(xmlConvertValue(2.0), '2')
        self.assertEqual(xmlConvertValue(-2.0), '-2')
        self.assertEqual(xmlConvertValue(2.05), '2.05')
        self.assertEqual(xmlConvertValue(2), '2')
        self.assertEqual(xmlConvertValue(0.2), '0.2')
        self.assertEqual(xmlConvertValue("0.0"), '0.0')
        self.assertEqual(xmlConvertValue(1e-5), '0.00001')
        self.assertEqual(xmlConvertValue(1e-10), '0.0000000001')
        self.assertEqual(xmlConvertValue(1e-11), '0')
        self.assertEqual(xmlConvertValue(1e+5), '100000')
        self.assertEqual(xmlConvertValue(1e+10), '10000000000')

    def test_xmlConvertFloat(self):
        self.assertEqual(xmlConvertFloat(1.0), '1')
        self.assertEqual(xmlConvertFloat(1.01), '1.01')
        self.assertEqual(xmlConvertFloat(1.0000000001), '1.0000000001')
        self.assertEqual(xmlConvertFloat(1.00000000001), '1')
        self.assertEqual(xmlConvertFloat(1.00000000009), '1.0000000001')

    def test_xmlConvertInt(self):
        self.assertEqual(xmlConvertInt(1), '1')
        self.assertEqual(xmlConvertInt(-1), '-1')
        self.assertEqual(xmlConvertInt(- 1), '-1')
        self.assertEqual(xmlConvertInt(0), '0')
        self.assertEqual(xmlConvertInt(-0), '0')
        self.assertEqual(xmlConvertInt(0o01), '1')
        self.assertEqual(xmlConvertInt(- 0o01), '-1')
        self.assertEqual(xmlConvertInt(0o000001), '1')
        self.assertEqual(xmlConvertInt(0o0000000000000001), '1')
        self.assertEqual(xmlConvertInt(1000000000000001), '1000000000000001')
        self.assertEqual(xmlConvertInt(0o000001000001), '262145')
        self.assertEqual(xmlConvertInt(0o00000100000), '32768')
        self.assertEqual(xmlConvertInt(0o0000010), '8')
        self.assertEqual(xmlConvertInt(-0o0000010), '-8')
        self.assertEqual(xmlConvertInt(0o0000020), '16')
        self.assertEqual(xmlConvertInt(0o0000030), '24')
        self.assertEqual(xmlConvertInt(65536), '65536')


class NameTranslationTest(unittest.TestCase):

    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)
        # Python 3 renamed assertRegexpMatches() to assertRegex().
        if not hasattr(self, "assertRegex"):
            self.assertRegex = self.assertRegexpMatches

    def test_userNameToFileName(self):
        self.assertEqual(userNameToFileName("a"), "a")
        self.assertEqual(userNameToFileName("A"), "A_")
        self.assertEqual(userNameToFileName("AE"), "A_E_")
        self.assertEqual(userNameToFileName("Ae"), "A_e")
        self.assertEqual(userNameToFileName("ae"), "ae")
        self.assertEqual(userNameToFileName("aE"), "aE_")
        self.assertEqual(userNameToFileName("a.alt"), "a.alt")
        self.assertEqual(userNameToFileName("A.alt"), "A_.alt")
        self.assertEqual(userNameToFileName("A.Alt"), "A_.A_lt")
        self.assertEqual(userNameToFileName("A.aLt"), "A_.aL_t")
        self.assertEqual(userNameToFileName("A.alT"), "A_.alT_")
        self.assertEqual(userNameToFileName("T_H"), "T__H_")
        self.assertEqual(userNameToFileName("T_h"), "T__h")
        self.assertEqual(userNameToFileName("t_h"), "t_h")
        self.assertEqual(userNameToFileName("F_F_I"), "F__F__I_")
        self.assertEqual(userNameToFileName("f_f_i"), "f_f_i")
        self.assertEqual(userNameToFileName("Aacute_V.swash"),
                         "A_acute_V_.swash")
        self.assertEqual(userNameToFileName(".notdef"), "_notdef")
        self.assertEqual(userNameToFileName("con"), "_con")
        self.assertEqual(userNameToFileName("CON"), "C_O_N_")
        self.assertEqual(userNameToFileName("con.alt"), "_con.alt")
        self.assertEqual(userNameToFileName("alt.con"), "alt._con")
        self.assertEqual(userNameToFileName("a*"), "a_")
        self.assertEqual(userNameToFileName("a", ["a"]), "a000000000000001")
        self.assertEqual(userNameToFileName("Xy", ["x_y"]),
                         "X_y000000000000001")

    def test_handleClash1(self):
        prefix = ("0" * 5) + "."
        suffix = "." + ("0" * 10)
        existing = ["a" * 5]

        e = list(existing)
        self.assertEqual(
            handleClash1(userName="A" * 5, existing=e,
                         prefix=prefix, suffix=suffix),
            '00000.AAAAA000000000000001.0000000000')

        e = list(existing)
        e.append(prefix + "aaaaa" + "1".zfill(15) + suffix)
        self.assertEqual(
            handleClash1(userName="A" * 5, existing=e,
                         prefix=prefix, suffix=suffix),
            '00000.AAAAA000000000000002.0000000000')

        e = list(existing)
        e.append(prefix + "AAAAA" + "2".zfill(15) + suffix)
        self.assertEqual(
            handleClash1(userName="A" * 5, existing=e,
                         prefix=prefix, suffix=suffix),
            '00000.AAAAA000000000000001.0000000000')

    def test_handleClash1_max_file_length(self):
        prefix = ("0" * 5) + "."
        suffix = "." + ("0" * 10)
        self.assertRegex(
            handleClash1(userName="ABCDEFGHIJKLMNOPQRSTUVWX_" * 10,
                         prefix=prefix, suffix=suffix),
            r'00000.ABCDEFGHIJKLM.*NOPQRSTUVW000000000000001.0000000000'
        )

    def test_handleClash2(self):
        prefix = ("0" * 5) + "."
        suffix = "." + ("0" * 10)
        existing = [prefix + str(i) + suffix for i in range(100)]

        e = list(existing)
        self.assertEqual(
            handleClash2(existing=e, prefix=prefix, suffix=suffix),
            '00000.100.0000000000')

        e = list(existing)
        e.remove(prefix + "1" + suffix)
        self.assertEqual(
            handleClash2(existing=e, prefix=prefix, suffix=suffix),
            '00000.1.0000000000')

        e = list(existing)
        e.remove(prefix + "2" + suffix)
        self.assertEqual(
            handleClash2(existing=e, prefix=prefix, suffix=suffix),
            '00000.2.0000000000')

if __name__ == "__main__":
    unittest.main()