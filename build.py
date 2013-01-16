#!/usr/bin/env python

import os
import os.path
from HTMLParser import HTMLParser
from argparse import ArgumentParser


def fileOfTypeInDir(type, dir):
    fileOfType = []
    for root, dirs, files in os.walk(dir):
        for filename in files:
            if os.path.splitext(filename)[1].lower() == type:
                fileOfType.append(os.path.join(root, filename))
    return fileOfType


class FileBuilder:
    """
    FileBuilder builds the concatenated file from a list of dependencies.
    """

    fingerprint = '/*! <Generated by builder> !*/'
    buildStatus = None

    def __init__(self, filename, debug=False, overwrite=False):
        self.filename = filename
        self.cssFilename = convertJSPathToCSSPath(filename)
        self.debug_mode = debug
        self.overwrite = overwrite
        self.cssFile = None
        self.outputFile = None

    def build(self, depList):
        self.outputFile = self.createFile(self.filename)
        if self.outputFile == None:
            return
        for dep in depList:
            print ' - %(part)-40s' % {'part': dep},
            if self.debug_mode:
                self.buildDebugPart(dep)
            else:
                self.buildProductionPart(dep)
            self.buildCSSPart(convertJSPathToCSSPath(dep))
            print ''
        if self.cssFile != None:
            self.cssFile.close()
        self.outputFile.close()

    def createFile(self, path):
        if os.path.exists(path) and not self.overwrite:
            with open(path) as outputFile:
                firstLine = outputFile.readline()
            if not firstLine.startswith(FileBuilder.fingerprint):
                FileBuilder.buildStatus = 'File "' + path + '" already exists.'
                return None
        outputFile = open(path, 'w')
        outputFile.write(FileBuilder.fingerprint + '\n')
        return outputFile

    def buildDebugPart(self, part):
        self.outputFile.write("document.write('<script type=\"text/javascript\" src=\"" + part + "\" charset=\"utf-8\"></script>');\n")

    def buildProductionPart(self, part):
        with open(part) as filePart:
            for line in filePart:
                if not line.startswith('//=>') and not line.startswith('//<='):
                    self.outputFile.write(line)
        self.outputFile.write('\n\n')

    def buildCSSPart(self, part):
        if os.path.exists(part):
            cssFile = self.getCSSFile()
            if cssFile is None:
                FileBuilder.buildStatus = 'CSS file already exists'
                return
            if self.debug_mode:
                relpath = os.path.relpath(part, os.path.dirname(self.cssFilename))
                cssFile.write('@import \'%s\';\n' % relpath)
                cssFile = self.getCSSFile()
            else:
                with open(part) as cssBlock:
                    cssFile.write(cssBlock.read() + '\n\n')

            print ' + ' + part,

    def getCSSFile(self):
        if self.cssFile == None:
            self.cssFile = self.createFile(self.cssFilename)
        return self.cssFile

    def __del__(self):
        if self.cssFile != None:
            self.cssFile.close()


class ScriptParser(HTMLParser):
    """
    ScriptParser parses HTML to find all <script> tags with data-src attribute. The list of such <script> tags can be
    fetched from ScriptParser.getScriptURLs() method
    """

    def __init__(self):
        HTMLParser.__init__(self)
        self.scriptTags = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            src = dest = ''
            for key, value in attrs:
                if key == 'src':
                    dest = value
                elif key == 'data-src':
                    src = value
            if src != '' and dest != '':
                self.scriptTags.append((src, dest))

    def getScriptURLs(self):
        return self.scriptTags

    def clear(self):
        self.scriptTags = []


class PackageAnalyzer:
    """
    PackageAnalyzer analyzes the JavaScript files in the directory and gives information about dependencies of files
    """

    DIRECTIVE_PROVIDE = '//<='
    DIRECTIVE_REQUIRE = '//=>'

    def __init__(self, directory):
        self.baseDir = directory
        self.packageMap = None
        # cache for the calculated dependencies so that we won't recalculate every time
        self.dependencyTree = {}

    def getPackageMap(self):
        if self.packageMap == None:
            jsFiles = fileOfTypeInDir(".js", self.baseDir)
            self.packageMap = self.buildJSMap(jsFiles)
        return self.packageMap

    def getPathForPackage(self, package):
        packageMap = self.getPackageMap()
        return packageMap[package]

    def getProvide(self, jsPath):
        with open(jsPath) as jsFile:
            for line in jsFile:
                # We are only concerned about the first provide
                if line.startswith(PackageAnalyzer.DIRECTIVE_PROVIDE):
                    return line.strip()[4:].split()
        return []

    def buildJSMap(self, jsFiles):
        #print '\nCreating package name mapping'
        jsMap = {}
        for jsFile in jsFiles:
            for packageName in self.getProvide(jsFile):
                # record package name if explicitly defined
                if packageName not in jsMap:
                    jsMap[packageName] = jsFile
            # File name as package name
            filename = os.path.splitext(os.path.basename(jsFile))[0]
            if filename not in jsMap:
                jsMap[filename] = jsFile
        return jsMap

    def getDependentPackages(self, jsPath):
        directives = []
        with open(jsPath) as jsFile:
            for line in jsFile:
                if line.startswith(PackageAnalyzer.DIRECTIVE_REQUIRE):
                    directives.extend(line.strip()[4:].split())
        return directives

    def getDependentFiles(self, jsPath):
        if (jsPath in self.dependencyTree):
            return self.dependencyTree[jsPath]
        packages = self.getDependentPackages(jsPath)
        files = []
        for package in packages:
            files.append(self.getPathForPackage(package))
        self.dependencyTree[jsPath] = files
        return files

    def getDependenciesRecursive(self, jsPath):
        depFiles = self.getDependentFiles(jsPath)
        deps = [jsPath]
        for path in depFiles:
            deps.extend(self.getDependenciesRecursive(path))
        return deps

    def getAllDependencies(self, jsPath):
        print '\nCalculating dependencies for "' + jsPath + '"'
        deps = self.getDependenciesRecursive(jsPath)
        deps.reverse()
        return uniqify(deps)


# Remove duplicates from a list while maintaining order. The first seen element will be retained.
def uniqify(seq):
    seen = set()
    return [x for x in seq if x not in seen and not seen.add(x)]


def splitPath(path):
    folders = []
    while True:
        path, folder = os.path.split(path)
        if folder != '':
            folders.append(folder)
            continue
        if path != '':
            folders.append(path)
        break
    folders.reverse()
    return folders


def convertJSPathToCSSPath(jsPath):
    cssPathComponents = []
    for component in splitPath(jsPath):
        if component == 'js':
            cssPathComponents.append('css')
        else:
            cssPathComponents.append(component)
    cssPath = ''
    for component in cssPathComponents:
        cssPath = os.path.join(cssPath, component)
    cssPath = os.path.splitext(cssPath)[0] + '.css'
    return cssPath


def getEntryPointsFromHTML(htmlPaths):
    scriptURLs = []
    parser = ScriptParser()
    for html in htmlPaths:
        #print 'Parsing "' + html + '" files for entry points'
        with open(html) as htmlFile:
            parser.feed(htmlFile.read())
        htmlLocation = os.path.dirname(html)
        for entryPoint, outputPath in parser.getScriptURLs():
            scriptURLs.append((os.path.join(htmlLocation, entryPoint), os.path.join(htmlLocation, outputPath)))
        parser.clear()

    return scriptURLs

COMPRESSOR_PATH = os.path.join(os.path.dirname(__file__), 'buildtools', 'yuicompressor-2.4.7.jar')


def minifyjs(path):
    print 'Minifying ' + path
    pathNoExtension = os.path.splitext(path)[0]
    os.system('cp ' + path + ' ' + pathNoExtension + '.src.js')
    os.system("java -jar " + COMPRESSOR_PATH + " --type js --line-break 256 " + path + " -o " + pathNoExtension + ".js")


def minifycss(path):
    print 'Minifying ' + path
    pathNoExtension = os.path.splitext(path)[0]
    os.system('cp ' + path + ' ' + pathNoExtension + '.src.css')
    os.system("java -jar " + COMPRESSOR_PATH + " --type css --line-break 256 " + path + " -o " + pathNoExtension + ".css")


def main():
    # Configure parser
    parser = ArgumentParser()
    parser.add_argument("-d", "--debug", help="Turn on debug mode", action="store_true", default=False)
    parser.add_argument("-f", "--force", help="Force overwrite files", action="store_true", default=False)
    parser.add_argument("-o", help="Open HTML file on success", action="store_true", default=False)
    parser.add_argument("files", help="Directory or HTML files to build", nargs='*')
    arg = parser.parse_args()

    baseDir = "."

    htmlFiles = arg.files
    if len(htmlFiles) == 0:
        htmlFiles = fileOfTypeInDir(".html", baseDir)
    elif os.path.isdir(htmlFiles[0]):
        baseDir = htmlFiles[0]
        htmlFiles = fileOfTypeInDir(".html", htmlFiles[0])

    print '\n== Building ', htmlFiles

    entryPoints = getEntryPointsFromHTML(htmlFiles)

    packageAnalyzer = PackageAnalyzer(baseDir)

    failureCount = 0

    if len(htmlFiles) == 0:
        print '\nNo HTML files found to build upon\n'

    for entryPoint, outputPath in entryPoints:
        builder = FileBuilder(outputPath, arg.debug, arg.force)
        builder.build(packageAnalyzer.getAllDependencies(entryPoint))
        print ''
        if FileBuilder.buildStatus is not None:
            print '===== Build "' + outputPath + '": ' + FileBuilder.buildStatus + ' ====='
            failureCount += 1
        elif arg.debug:
            print 'Build "' + outputPath + '" complete',
        else:
            minifyjs(outputPath)
            minifycss(convertJSPathToCSSPath(outputPath))
            print ''
            print 'Build "' + outputPath + '" complete'

    print ''

    if failureCount == 0:
        if arg.o:
            os.system("open " + htmlFiles[0])
        print '\nBuild completed for all files\n'
    else:
        print '\n===== ' + failureCount + ' files failed to build =====\n'

if __name__ == "__main__":
    main()
