import os
import subprocess
import tensorflow as tf
import xml.etree.ElementTree as ET

from .util import sixdecode


def get_available_gpus():
    gpus = _get_gpu_info()

    def check_gpu(gpu):
        return memstr2int(gpu.find('fb_memory_usage').find('used').text) < \
            0.1 * memstr2int(gpu.find('fb_memory_usage').find('total').text)

    return [gpu.find('minor_number').text
            for gpu in gpus if check_gpu(gpu)]


def _get_gpu_info():
    try:
        smi_proc = subprocess.Popen(['nvidia-smi', '-q', '-x'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

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
    gpu_mapping = {}
    for i in range(0, no_gpus):

        loadp = subprocess.Popen([
            'python', '-c',
            ("from studio import gpu_util as gu \n" +
             "import os\n" +
             "os.environ['CUDA_VISIBLE_DEVICES']='{}'\n" +
             "gu._load_gpu()\n" +
             "print('******')\n"
             "print(gu._find_my_gpus()[0])").format(i)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        pstdout, _ = loadp.communicate()
        if loadp.returncode != 0:
            return {str(i): i for i in range(0, no_gpus)}

        gpu_minor_number = sixdecode(pstdout).split('\n')[-2]
        gpu_mapping[gpu_minor_number] = i

    return gpu_mapping


def _find_my_gpus(prop='minor_number'):
    gpu_info = _get_gpu_info()
    my_gpus = [g.find(prop).text for g in gpu_info if os.getpid() in [int(
        p.find('pid').text) for p in
        g.find('processes').findall('process_info')]]

    return my_gpus


def _load_gpu():
    tf.Session()


def memstr2int(string):
    conversion_factors = [
        ('Mb', 2**20), ('MiB', 2**20), ('m', 2**20), ('mb', 2**20),
        ('Gb', 2**30), ('GiB', 2**30), ('g', 2**30), ('gb', 2**30),
        ('kb', 2**10), ('k', 2**10)
    ]

    for k, f in conversion_factors:
        if string.endswith(k):
            return int(float(string.replace(k, '')) * f)

    return int(string)


if __name__ == "__main__":
    print(get_gpu_mapping())
