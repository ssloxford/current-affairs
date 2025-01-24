from __future__ import annotations
import datetime
import json
import os
from typing import Any, List
import traceback

# Context manager for a part of the output log
class DataSaverTraceContext():
    ctx: "DataSaver"
    data_type: str

    @staticmethod
    def try_str(val) -> str:
        try:
            return(str(val))
        except:
            pass
        return ""
    def __init__(self, ctx: "DataSaver", data_type: str):
        self.ctx = ctx
        self.data_type = data_type

    def __enter__(self):
        return self
    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            self.ctx.log_entry("EXCEPTION", {
                "type": exception_type.__name__,
                "value": DataSaverTraceContext.try_str(exception_value),
                "traceback": traceback.format_tb(exception_traceback)
            })

        self.ctx.trace_leave(self)

# Context manager for the output file
class DataSaverFileContext():
    ctx: "DataSaver"
    data_type: str

    @staticmethod
    def try_str(val) -> str:
        try:
            return(str(val))
        except:
            pass
        return ""
    def __init__(self, ctx: "DataSaver"):
        self.ctx = ctx

    def __enter__(self):
        return self
    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            self.ctx.log_entry("EXCEPTION", {
                "type": exception_type.__name__,
                "value": DataSaverTraceContext.try_str(exception_value),
                "traceback": traceback.format_tb(exception_traceback)
            })

        self.ctx.trace_file_leave()

class DataSaver:
    #Base folder for results
    result_folder: str

    #Folder for this run
    result_subfolder: str
    #Line by line backup file
    backup_file: Any

    #Output data
    trace: List[str]
    results_heads: List[Any]
    results: Any

    def __init__(self, result_folder: str):
        self.result_folder = result_folder
        self.backup_file = None

        self.trace = []
        self.results_heads = []

    def init_backup_file(self):
        if self.backup_file is not None:
            self.backup_file.close()
        self.backup_file = open(os.path.join(self.result_subfolder, "backup.bak.txt"), "a")


    def write_backup(self, time_str, type, data):
        backup_entry = {
            "version": 1,
            "type": type,
            "trace": self.trace.copy(),
            "time": time_str,
            "data": data
        }

        self.backup_file.write(json.dumps(backup_entry, indent=None))
        self.backup_file.write("\n")
        self.backup_file.flush()

    def trace_file_start(self, name):
        self.result_subfolder = self.result_folder + "_" + name
        os.makedirs(self.result_subfolder, exist_ok = True)

        self.init_backup_file()

        return DataSaverFileContext(self)

    def trace_enter(self, entry: str):
        self.trace.append(entry)

        time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        self.write_backup(time_str, "TRACE_ENTER", None)

        new_entry = {
            "version": 1,
            "type": "TRACE",
            "trace": self.trace.copy(),

            "start_time": time_str,
            "end_time": None,
            "data": []
        }

        if len(self.results_heads):
            self.results_heads[-1]["data"].append(new_entry)
        else:
            self.results = new_entry
        self.results_heads.append(new_entry)

        return DataSaverTraceContext(self, entry)

    def log_entry(self, data_type: str, data):
        time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        self.write_backup(time_str, data_type, data)

        new_entry = {
            "version": 1,
            "type": "ENTRY",
            "trace": self.trace.copy(),

            "time": time_str,
            "data_type": data_type,
            "data": data
        }

        self.results_heads[-1]["data"].append(new_entry)

    def trace_leave(self, it: DataSaverTraceContext):
        if self.trace[-1] != it.data_type:
            raise Exception("Logging stack error")
        
        time_val = datetime.datetime.now(datetime.timezone.utc)
        time_str = time_val.strftime("%Y-%m-%d %H:%M:%S")
        self.write_backup(time_str, "TRACE_LEAVE", None)

        self.results_heads[-1]["end_time"] = time_str

        self.results_heads.pop()
        self.trace.pop()

    def trace_file_leave(self):
        with open(os.path.join(self.result_subfolder, "result.json"), "w") as f:
            json.dump(self.results, f, indent=2)
            self.results = []

        if len(self.trace) != 0:
            raise RuntimeError("Closed file without exiting traces")
                

        
      
