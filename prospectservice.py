import sys
import time
import hashlib
import json
import os
import platform
import re
import subprocess
import urllib.request
import winreg
import win32api
import win32serviceutil
import win32service
import servicemanager
import win32evtlog
import win32evtlogutil

url='http://prospector.api.local:8888/api/devices/profiles'

class ProspectService:
    def stop(self):
        self.running = False

    def snake(self, str: str):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', str).lower()


    def open_key(self, hive, path):
        return winreg.OpenKey(
            winreg.ConnectRegistry(None, hive),
            path,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ) 


    def get_bios(self):
        reg_key = self.open_key(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System")
        reg_key_b = self.open_key(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
        version = winreg.QueryValueEx(reg_key, "SystemBiosVersion")
        model = [
            winreg.QueryValueEx(reg_key_b, "BaseBoardManufacturer")[0],
            winreg.QueryValueEx(reg_key_b, "BaseBoardProduct")[0]
        ]
        
        return {
            'model': ' '.join(model),
            'firmware': ' '.join(version[0]),
        }


    def get_software(self, hive, flag):
        reg_key = winreg.OpenKey(
            winreg.ConnectRegistry(None, hive),
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            0,
            winreg.KEY_READ | flag
        )
        count_subkey = winreg.QueryInfoKey(reg_key)[0]
        software_list = []
        for i in range(count_subkey):
            software = {}
            try:
                sub_key = winreg.OpenKey(reg_key, winreg.EnumKey(reg_key, i))
                software['name'] = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                try:
                    software['version'] = winreg.QueryValueEx(sub_key, "DisplayVersion")[0]
                except EnvironmentError:
                    software['version'] = 'n/a'
                try:
                    software['publisher'] = winreg.QueryValueEx(sub_key, "Publisher")[0]
                except EnvironmentError:
                    software['publisher'] = 'n/a'
                software_list.append(software)
            except EnvironmentError:
                continue

        return software_list  


    def get_memory(self):
        wmic = subprocess.check_output(
            'wmic memorychip get DeviceLocator, Capacity, ConfiguredClockSpeed, DataWidth, Manufacturer, PartNumber'
        )

        memory = str(wmic, 'utf-8').split()

        devices = []
        multi = 1
        offset = 6
        num_devices = round(len(memory[offset:]) / offset)
        try:
            for d in range(num_devices):
                output = {}
                for o in range(offset):
                    output[self.snake(memory[o])] = ''
                
                if d != 0 and d % 1 == 0:
                    multi = multi + 1
                    
                values = memory[offset*multi:]
                
                for v in range(offset):
                    key = self.snake(memory[v])
                    if key in ['capacity', 'configured_clock_speed', 'data_width']:
                        value = int(values[v])
                        if key == 'capacity': value = round(int(values[v]) / (1024.0 ** 3))
                    else:
                        value = values[v]
                    output[key] = value

                devices.append(output)
        except:
            pass
        
        return devices


    def get_distribution(self):
        os = subprocess.Popen('systeminfo', stdout=subprocess.PIPE).communicate()[0]
        try:
            os = str(os, "latin-1")
        except:
            pass

        return re.search("OS Name:\s*(.*)", os).group(1).strip()


    def get_hwid(self):
        id = str(subprocess.check_output('wmic csproduct get uuid'), 'utf-8').split('\n')[1].strip()
        
        return hashlib.sha256(id.encode('utf-8'))


    def get_profile(self):
        installed_software = self.get_software(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY)
            
        profile = {
            'hwid': self.get_hwid().hexdigest(),
            'hostname': platform.node(),
            'os': {
                'platform': platform.system(),
                'distribution': self.get_distribution(),
                'arch': platform.architecture()[0],
                'kernel': platform.version(),
            },
            'software': {
                'programs': installed_software,
                'num_installed': len(installed_software)
            },
            'hardware': {
                'bios': self.get_bios(),
                'cpu': {
                    'name': platform.processor(),
                    'cores': os.cpu_count(),
                },
                'ram': self.get_memory()
            }    
        }

        return profile


    def write_profile(self, profile: dict):
        filename = 'prospect-profile-' + profile.get('hwid')[:8] + '.json'
        filepath = os.path.join('C:\\', 'ProspectService')

        if not os.path.isdir(filepath):
            os.mkdir(filepath)

        content = json.dumps(profile, sort_keys=False, indent=4)
        destination = os.path.join(filepath, filename)

        with open(destination, 'w') as prospectfile:
            prospectfile.write(content)
            print('device profile written to ' + destination)


    def send_profile(self, profile: dict):
        try:
            content = json.dumps(profile, sort_keys=False, indent=4)
            request = urllib.request.Request(url)
            request.add_header('Content-Type', 'application/json; charset=utf-8')
            request.add_header('Authorization', 'Bearer c2VjcmV0')
            data = content.encode('utf-8')
            request.add_header('Content-Length', len(data))

            urllib.request.urlopen(request, data)
        except:
            servicemanager.LogWarningMsg("Unable to connect to prospect device profiling API.")


    def log_profile_event(self, profile):
        event_strs = []
        for key, value in profile.items():
            event_strs.append(str(key) + ': ' + str(value))

        event_data = str.encode(profile['hwid'])

        PROSPECT_EVENT_NAME = "ProspectService"
        PROSPECT_EVENT_ID = 100
        PROSPECT_EVENT_CATEGORY = 1000
        PROSPECT_EVENT_STRINGS = event_strs
        PROSPECT_EVENT_DATA = event_data

        win32evtlogutil.ReportEvent(
            PROSPECT_EVENT_NAME,
            PROSPECT_EVENT_ID,
            eventCategory=PROSPECT_EVENT_CATEGORY,
            eventType=win32evtlog.EVENTLOG_INFORMATION_TYPE,
            strings=PROSPECT_EVENT_STRINGS,
            data=PROSPECT_EVENT_DATA
        )


    def profile_device(self):
        profile = self.get_profile()
        print(json.dumps(profile, sort_keys=False, indent=4))
        self.write_profile(profile)
        self.log_profile_event(profile)
        self.send_profile(profile)


    def run(self):
        self.running = True
        while self.running:
            time.sleep(300)
            self.profile_device()


class ProspectServiceFramework(win32serviceutil.ServiceFramework):
    _svc_name_ = 'ProspectService'
    _svc_display_name_ = 'Prospect Device Profiler'

    def SvcStop(self):
        servicemanager.LogInfoMsg("Shutting down prospect device profiler...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service_impl.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Starting prospect device profiler...")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service_impl = ProspectService()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.service_impl.run()


def init():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ProspectServiceFramework)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ProspectServiceFramework)


if __name__ == '__main__':
    init()