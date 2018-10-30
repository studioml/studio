repo_url="{repo_url}"
branch="{studioml_branch}"

if [ ! -d "studio" ]; then
    echo "Installing system packages..."
    sudo apt -y update
    sudo apt install -y wget git jq 
    sudo apt install -y python python-pip python-dev python3 python3-dev python3-pip dh-autoreconf build-essential
    echo "python2 version: " $(python -V)

    sudo python -m pip install --upgrade pip
    sudo python -m pip install --upgrade awscli boto3
       
    echo "python3 version: " $(python3 -V)
   
    sudo python3 -m pip install --upgrade pip
    sudo python3 -m pip install --upgrade awscli boto3

    # Install singularity
    git clone https://github.com/singularityware/singularity.git
    cd singularity
    ./autogen.sh
    ./configure --prefix=/usr/local --sysconfdir=/etc
    time (make && make install)
    cd ..

    time apt-get -y install python3-tk python-tk
    time python -m pip install http://download.pytorch.org/whl/cu80/torch-0.3.0.post4-cp27-cp27mu-linux_x86_64.whl 
    time python3 -m pip install http://download.pytorch.org/whl/cu80/torch-0.3.0.post4-cp35-cp35m-linux_x86_64.whl 

    nvidia-smi
    nvidia_smi_error=$?

    if [ "{use_gpus}" -eq 1 ] && [ "$nvidia_smi_error" -ne 0 ]; then
        cudnn5="libcudnn5_5.1.10-1_cuda8.0_amd64.deb"
        cudnn6="libcudnn6_6.0.21-1_cuda8.0_amd64.deb"
        cuda_base="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1604/x86_64/"
        cuda_ver="cuda-repo-ubuntu1604_8.0.61-1_amd64.deb"

        cuda_driver='nvidia-diag-driver-local-repo-ubuntu1604-384.66_1.0-1_amd64.deb'
        wget $code_url_base/$cuda_driver
        dpkg -i $cuda_driver
        apt-key add /var/nvidia-diag-driver-local-repo-384.66/7fa2af80.pub
        apt-get -y update
        apt-get -y install cuda-drivers
        apt-get -y install unzip

        # install cuda
        cuda_url="https://developer.nvidia.com/compute/cuda/8.0/Prod2/local_installers/cuda_8.0.61_375.26_linux-run"
        cuda_patch_url="https://developer.nvidia.com/compute/cuda/8.0/Prod2/patches/2/cuda_8.0.61.2_linux-run"

        # install cuda
        wget $cuda_url
        wget $cuda_patch_url
        #udo dpkg -i $cuda_ver
        #sudo apt -y update
        #sudo apt install -y "cuda-8.0"
        sh ./cuda_8.0.61_375.26_linux-run --silent --toolkit
        sh ./cuda_8.0.61.2_linux-run --silent --accept-eula

        export PATH=$PATH:/usr/local/cuda-8.0/bin
        export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda-8.0/lib64
    
        # wget $cuda_base/$cuda_ver
        # sudo dpkg -i $cuda_ver
        # sudo apt -y update
        # sudo apt install -y "cuda-8.0"

        # install cudnn
        wget $code_url_base/$cudnn5
        wget $code_url_base/$cudnn6
        sudo dpkg -i $cudnn5
        sudo dpkg -i $cudnn6
    
        # sudo python  -m pip install tf-nightly tf-nightly-gpu --upgrade
        # sudo python3 -m pip install tf-nightly tf-nightly-gpu --upgrade
    else
        sudo apt install -y default-jre
    fi
fi

#if [[ "{use_gpus}" -ne 1 ]]; then
#    rm -rf /usr/lib/x86_64-linux-gnu/libcuda*
#fi

rm -rf studio
git clone $repo_url
if [[ $? -ne 0 ]]; then
    git clone https://github.com/studioml/studio
fi

cd studio
git pull
git checkout $branch

apoptosis() {{
    while :
        do
            date
            shutdown +1
            (nvidia-smi; shutdown -c; echo "nvidia-smi functional, preventing shutdown")&
            sleep 90
        done

}}

if [[ "{use_gpus}" -eq 1 ]]; then
        export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda-8.0/lib64
        # (apoptosis > autoterminate.log)&
fi
    
time python -m pip install -e . --upgrade
time python3 -m pip install -e . --upgrade



