# This file is part of uac-a-mola
# Author: Pablo Gonzalez (pablo@11paths.com)
#
# DESCRIPTION
# This module search for binaries with 'AutoElevate' Attribute


try:
    from ...module import Module
except ImportError:
    from module import Module
from os import listdir
from os.path import isfile, join


class CustomModule(Module):
    def __init__(self):
        information = {"Name": "AutoElevate Binary Search",
                       "Description": "This module search for binaries with 'AutoElevate' Attribute",
                       "Author": "Pablo Gonzalez"}

        # -----------name-----default_value--description
        options = {"binlist": [r"C:\Users\IEUser\Desktop\uacamola\proof.txt", "Path to a list of binaries for testing", True],
                   "path":  [r"c:\windows\sysnative\\", "Binary's Path", True],
                   "mode": ["0", "Mode path (0) or binlist (1)", True],
                   "output": ["binlist.txt", "Output file for binaries with Autoelevate equal to True", False]}

        # Constructor of the parent class
        super(CustomModule, self).__init__(information, options)

    # This module must be always implemented, it is called by the run option
    def run_module(self):
        if self.args["mode"] == "0":
            self.print_info("[*] Searching binaries in: %s\n" %
                            self.args["path"])
            binaries = self.file_in_directory(self.args["path"])
            f = open(self.args["output"], "w")
            for i in binaries:
                print('[*] Parsing binary: ' + i)
                if self.find_auto_elevate(i):
                    f.write(i.split("\\")[-1] + "\n")
            f.close()
            self.print_info("\nFiles written to file %s\n\n" %
                            self.args["output"])
        elif self.args["mode"] == "1":
            self.print_info("[*] Searching binaries with AutoElevate...\n")
            f = open(self.args["output"], "w")
            for b in self.binaries():
                bin = self.args["path"] + b
                if self.find_auto_elevate(bin):
                    f.write(b + "\n")
            f.close()
            self.print_info("\nFiles written to file %s\n\n" %
                            self.args["output"])
        else:
            self.print_ko("Mode should be 'path' or 'binlist'\n")

    def binaries(self):
        with open(self.args["binlist"], 'r') as binfile:
            return binfile.read().splitlines()

    def find_auto_elevate(self, bin):
        with open(bin, 'rb') as binfile:
            binary_string = binfile.read()
            found = b">true</autoElevate>"
            if binary_string.find(found, 0) != -1:
                self.print_ok("binary: " + bin + " has AutoElevate a true\n")
                return True
            return False

    def file_in_directory(self, path):
        binaries = []
        for f in listdir(path):
            if isfile(join(path, f)):
                if f.find(".exe", 0) != -1:
                    binaries.append(join(path, f))
        return binaries
