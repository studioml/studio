import psutil

g = 2**30 + 0.0
meminfo = psutil.virtual_memory()
diskinfo = psutil.disk_usage('/')
print("Cpu count = {}".format(psutil.cpu_count()))
print("RAM: total {}g, free {}g".format(meminfo.total / g, meminfo.free / g))
print("HDD: total {}g, free {}g".format(diskinfo.total / g, diskinfo.free / g))
