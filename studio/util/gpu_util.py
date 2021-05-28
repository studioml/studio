import os
import subprocess
import xml.etree.ElementTree as ET

from studio.util.util import sixdecode


def memstr2int(string):
    conversion_factors = [
        ('Mb', 2**20), ('MiB', 2**20), ('m', 2**20), ('mb', 2**20),
        ('Gb', 2**30), ('GiB', 2**30), ('g', 2**30), ('gb', 2**30),
        ('kb', 2**10), ('k', 2**10)
    ]

    for key, factor in conversion_factors:
        if string.endswith(key):
            return int(float(string.replace(key, '')) * factor)

    return int(string)


def get_available_gpus(gpu_mem_needed=None, strict=False):
    gpus = _get_gpu_info()

    def check_gpu_nomem_strict(gpu):
        return memstr2int(gpu.find('fb_memory_usage').find('used').text) < \
            memstr2int(gpu.find('fb_memory_usage').find('free').text)
    if gpu_mem_needed is None:
        if strict:
            return [gpu.find('minor_number').text for gpu in gpus if
                    check_gpu_nomem_strict(gpu)]
        return [gpu.find('minor_number').text for gpu in gpus]

    gpu_mem_needed = memstr2int(gpu_mem_needed)

    def check_gpu_mem_strict(gpu):
        return gpu_mem_needed < \
            memstr2int(gpu.find('fb_memory_usage').find('free').text)

    def check_gpu_mem_loose(gpu):
        return (gpu_mem_needed <
                memstr2int(gpu.find('fb_memory_usage').find('total').text)) \
            and check_gpu_nomem_strict(gpu)

    if strict:
        return [gpu.find('minor_number').text
                for gpu in gpus if check_gpu_mem_strict(gpu)]
    return [gpu.find('minor_number').text
            for gpu in gpus if check_gpu_mem_loose(gpu)]


def _get_gpu_info():
    try:
        with subprocess.Popen(['nvidia-smi', '-q', '-x'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT) as smi_proc:
            smi_output, _ = smi_proc.communicate()
            xmlroot = ET.fromstring(sixdecode(smi_output))
            return xmlroot.findall('gpu')
    except Exception:
        return []


def get_gpus_summary():
    info = _get_gpu_info()

    def info_to_summary(gpuinfo):
        util = gpuinfo.find('utilization').find('gpu_util').text
        mem = gpuinfo.find('fb_memory_usage').find('used').text

        return "util: {}, mem {}".format(util, memstr2int(mem))

    return " ".join([
        "gpu {} {}".format(
            gpuinfo.find('minor_number').text,
            info_to_summary(gpuinfo)) for gpuinfo in info])


def get_gpu_mapping():
    no_gpus = len(_get_gpu_info())
    return {str(i): i for i in range(no_gpus)}


def _find_my_gpus(prop='minor_number'):
    gpu_info = _get_gpu_info()
    my_gpus = [g.find(prop).text for g in gpu_info if os.getpid() in [int(
        p.find('pid').text) for p in
        g.find('processes').findall('process_info')]]

    return my_gpus


if __name__ == "__main__":
    print(get_gpu_mapping())
